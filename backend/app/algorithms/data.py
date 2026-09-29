"""Strict IO-VNBD adapter: SI units, continuous segment, causal 10 Hz sampling."""
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd

def read_drive(path):
    with open(path,'rb') as handle:
        if handle.readline().startswith(b'version https://git-lfs.github.com/spec'):
            raise ValueError('This is a Git LFS pointer. Download the actual IO-VNBD CSV first.')
    df = pd.read_csv(path, encoding='latin1', low_memory=False)
    df.columns = [c.strip().lower() for c in df.columns]
    def col(prefix):
        matches = [c for c in df.columns if c.startswith(prefix)]
        if not matches:
            raise ValueError(f'Missing {prefix}. Supply an IO-VNBD S-* smartphone recording.')
        return pd.to_numeric(df[matches[0]], errors='coerce').to_numpy(float)
    t = col('time since start') / 1000.
    acc = np.column_stack([col('accelerometer '+a) for a in 'xyz'])
    gyro = np.column_stack([col('gyroscope '+a) for a in ('roll','pitch','yaw')])
    gravity = np.column_stack([col('gravity '+a) for a in 'xyz'])
    lat, lon, speed = col('gps latitude'), col('gps longitude'), col('gps speed')/3.6
    bearing = col('gps orientation')
    valid = np.isfinite(np.column_stack([t,acc,gyro,gravity,lat,lon,speed])).all(axis=1)
    valid &= (np.abs(lat)<=90)&(np.abs(lon)<=180)&(speed>=0)&(speed<75)
    breaks = np.where((np.diff(t)<=0)|(np.diff(t)>1.)|~valid[1:]|~valid[:-1])[0]+1
    segments = np.split(np.arange(len(t)), breaks)
    ids = max((s for s in segments if len(s) and valid[s].all()), key=len, default=np.array([],int))
    if len(ids)<100:
        raise ValueError('No continuous valid segment of 100 samples.')
    t,acc,gyro,gravity,lat,lon,speed = [v[ids] for v in (t,acc,gyro,gravity,lat,lon,speed)]
    bearing = bearing[ids]
    t -= t[0]
    grid = np.arange(0,t[-1],.1)
    k = np.maximum(0,np.searchsorted(t,grid,side='right')-1)
    acc,gyro,gravity,lat,lon,speed = [v[k] for v in (acc,gyro,gravity,lat,lon,speed)]
    bearing = bearing[k]
    raw_speed = speed*3.6
    xy = np.column_stack([np.radians(lon-lon[0])*6378137*np.cos(np.radians(lat[0])),np.radians(lat-lat[0])*6378137])
    unit_g = gravity/np.maximum(np.linalg.norm(gravity,axis=1,keepdims=True),1e-6)
    linear = acc-gravity
    vertical = np.sum(linear*unit_g,axis=1)
    horizontal = np.sqrt(np.maximum(0,np.sum(linear**2,axis=1)-vertical**2))
    yaw_rate = np.sum(gyro*unit_g,axis=1)
    # These files repeat GNSS fixes for about nine seconds. Separate causal
    # navigation fixes from interpolated scoring/label references explicitly.
    fix_ids = np.r_[0,np.where(np.linalg.norm(np.diff(xy,axis=0),axis=1)>.01)[0]+1]
    if len(fix_ids)<5:
        raise ValueError('Too few distinct GNSS positions for evaluation.')
    fix_t = grid[fix_ids]
    fix_speed = np.r_[0,np.linalg.norm(np.diff(xy[fix_ids],axis=0),axis=1)/np.diff(fix_t)]
    fix_speed = np.clip(fix_speed,0,60)
    speed = fix_speed[np.maximum(0,np.searchsorted(fix_t,grid,side='right')-1)]
    reference_xy = np.column_stack([np.interp(grid,fix_t,xy[fix_ids,j]) for j in range(2)])
    label_speed = np.r_[np.linalg.norm(np.diff(reference_xy,axis=0),axis=1)/.1,0.]
    label_speed = np.clip(label_speed,0,60)
    # Stable identity across header encoding/whitespace changes. Versioned canonical SI sensor stream.
    identity = np.column_stack([grid,acc,gyro,gravity,lat,lon]).astype('<f8').tobytes()
    data_sha256 = hashlib.sha256(b'kinematix-sensor-stream-v1\0'+identity).hexdigest()
    return dict(data_sha256=data_sha256,name=Path(path).name,sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),t=grid,
        acc=acc,gyro=gyro,gravity=gravity,linear=linear,signals=np.column_stack([horizontal,vertical,yaw_rate,np.linalg.norm(gyro,axis=1)]),
        raw_speed=raw_speed,gps_heading=np.radians(90-bearing),yaw_rate=yaw_rate,xy=xy,speed=speed,label_speed=label_speed,reference_xy=reference_xy,fix_ids=fix_ids,fix_interval_s=float(np.median(np.diff(fix_t))),origin=[float(lat[0]),float(lon[0])],source_rows=len(df),retained_rows=len(grid),sample_hz=10)

def features(signals):
    a = np.asarray(signals,float)
    return np.concatenate([a.mean(axis=0),a.std(axis=0),np.sqrt((a*a).mean(axis=0)),np.max(np.abs(a),axis=0)])

def windows(drive,stride=5):
    ids = np.arange(19,len(drive['t']),stride)
    return np.array([features(drive['signals'][i-19:i+1]) for i in ids]),drive['label_speed'][ids],ids
