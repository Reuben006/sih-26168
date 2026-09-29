"""Read-only dataset audit and estimator ablations. Never tunes the model."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from app.algorithms.data import read_drive
from app.algorithms.iovnbd_parser import run_outage

ROOT = Path(__file__).parent
SOURCE = 'https://pure.coventry.ac.uk/ws/portalfiles/portal/40741559/Binder8.pdf'


def audit_file(path, archive=None):
    frame = pd.read_csv(path, encoding='latin1', low_memory=False)
    frame.columns = [c.strip().lower() for c in frame.columns]
    def column(prefix):
        key = next(c for c in frame.columns if c.startswith(prefix))
        return pd.to_numeric(frame[key], errors='coerce').to_numpy(float)
    t = column('time since start') / 1000
    delta = np.diff(t)
    date_key = next(c for c in frame.columns if c.startswith('date'))
    dates = pd.to_datetime(frame[date_key], format='%Y-%m-%d %H:%M:%S:%f', errors='coerce')
    date_dt = dates.diff().dt.total_seconds().to_numpy()[1:]
    comparable = np.isfinite(date_dt) & np.isfinite(delta) & (delta > 0)
    resets = np.flatnonzero(delta <= 0) + 1
    segments = np.split(np.arange(len(t)), np.flatnonzero((delta <= 0) | (delta > 1)) + 1)
    segment = max(segments, key=len)
    tt = t[segment]
    lat, lon = column('gps latitude')[segment], column('gps longitude')[segment]
    xy = np.column_stack([np.radians(lon-lon[0])*6378137*np.cos(np.radians(lat[0])), np.radians(lat-lat[0])*6378137])
    changed = np.r_[0, np.flatnonzero(np.linalg.norm(np.diff(xy,axis=0),axis=1) > .01)+1]
    fix_dt = np.diff(tt[changed])
    speed_raw = column('gps speed')[segment]
    step_speed = np.linalg.norm(np.diff(xy[changed],axis=0),axis=1)/fix_dt if len(fix_dt) else np.array([])
    moving = (step_speed > 3) & (step_speed < 50) & (speed_raw[changed[1:]] > 3)
    ratio = step_speed[moving]/speed_raw[changed[1:]][moving]
    acc = np.column_stack([column('accelerometer '+a) for a in 'xyz'])
    gravity = np.column_stack([column('gravity '+a) for a in 'xyz'])
    gyro = np.column_stack([column('gyroscope '+a) for a in ('roll','pitch','yaw')])
    data = dict(recording=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rows=len(frame),
        median_imu_dt_s=float(np.median(delta[delta>0])),clock_reset_rows=resets.tolist(),
        elapsed_vs_date_p99_disagreement_s=float(np.percentile(np.abs(delta[comparable]-date_dt[comparable]),99)),
        longest_segment_rows=len(segment),selected_segment_start_row=int(segment[0]),selected_segment_end_row=int(segment[-1]),
        retained_source_fraction=float(len(segment)/len(frame)),distinct_coordinates=len(changed),
        median_coordinate_change_interval_s=float(np.median(fix_dt)) if len(fix_dt) else None,
        median_displacement_speed_over_raw_speed=float(np.median(ratio)) if len(ratio) else None,
        speed_comparison_intervals=int(moving.sum()),
        gravity_mean_mps2=gravity.mean(0).tolist(),gravity_std_mps2=gravity.std(0).tolist(),
        gyro_column_order=['roll','pitch','yaw'],gyro_mean_radps=gyro.mean(0).tolist(),gyro_std_radps=gyro.std(0).tolist(),
        linear_acceleration_mean_mps2=(acc-gravity).mean(0).tolist(),
        linear_acceleration_std_mps2=(acc-gravity).std(0).tolist(),source_pointer_matches=[])
    if archive:
        for pointer in archive.rglob(path.name):
            if pointer.stat().st_size < 300:
                text=pointer.read_text()
                if data['sha256'] in text:
                    data['source_pointer_matches'].append(str(pointer.relative_to(archive)))
    official = ROOT/'app/datasets/audit-source'/path.name
    if official.exists():
        a,b=path.read_bytes().splitlines(),official.read_bytes().splitlines()
        data['official_copy_comparison']=dict(official_sha256=hashlib.sha256(official.read_bytes()).hexdigest(),
            header_differs=a[0]!=b[0],data_rows_byte_identical=a[1:]==b[1:])
    if path.name=='S-Vw1.csv':
        # Label is established by paper Table A4-1, not inferred from the coordinates.
        n=min(600,len(frame))
        calibrated=gyro[n:]-gyro[:n].mean(0)
        data['role']='stationary calibration (paper Table A4-1)'
        data['stationary_check']=dict(calibration_samples=n,calibration_duration_s=float(t[n-1]-t[0]),
            test_samples=len(calibrated),test_mean_residual_radps=calibrated.mean(0).tolist(),
            residual_integrated_angle_deg=np.degrees(np.sum(calibrated*np.diff(t[n-1:])[:,None],axis=0)).tolist(),
            note='Bias estimated from first 60 s; remaining stationary samples are an independent within-recording check. No moving-drive tuning.')
    return data


def ablations():
    rows=[]
    for name in ['S-S1.csv','S-M.csv','S-Vw4.csv']:
        d=read_drive(ROOT/'app/datasets'/name)
        fractions=[.2,.35,.65] if name=='S-S1.csv' else [.35]
        for fraction in fractions:
            for duration in [10.,30.,60.]:
                start=round(float(d['t'][-1])*fraction,1)
                ai=run_outage(d,start,duration,use_ai=True)
                plain=run_outage(d,start,duration,use_ai=False)
                rows.append(dict(recording=name,start_s=ai['start_s'],duration_s=duration,distance_m=ai['outage_distance_m'],
                    ai_endpoint_m=ai['final_error_m'],no_ai_endpoint_m=plain['final_error_m'],constant_speed_endpoint_m=ai['baseline_final_error_m'],
                    ai_improves_over_no_ai=ai['final_error_m']<plain['final_error_m'],
                    ai_improves_over_constant_speed=ai['final_error_m']<ai['baseline_final_error_m'],
                    gyro_projection_norm=float(np.linalg.norm(ai['calibration']['yaw_axis'])),
                    speed_anchor_offset_mps=ai['calibration']['speed_offset_mps']))
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path)
    args=parser.parse_args()
    report=dict(source_document=SOURCE,method='Read-only diagnostics and fixed-window AI-on/AI-off/constant-speed comparisons; no parameter search.',
        recordings=[audit_file(ROOT/'app/datasets'/n,args.archive) for n in ['S-M.csv','S-S1.csv','S-Vw4.csv','S-Vw1.csv']],ablations=ablations())
    out=ROOT/'reports/dataset_audit.json'
    out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    for d in report['recordings']:
        print(d['recording'],'dt',d['median_imu_dt_s'],'reset rows',d['clock_reset_rows'],'coordinate interval',d['median_coordinate_change_interval_s'],'speed ratio',d['median_displacement_speed_over_raw_speed'])
    a=report['ablations']
    print('AI improves vs no AI:',sum(x['ai_improves_over_no_ai'] for x in a),'/',len(a))
    print('AI improves vs constant speed:',sum(x['ai_improves_over_constant_speed'] for x in a),'/',len(a))
    print('Wrote',out)

if __name__=='__main__':
    main()
