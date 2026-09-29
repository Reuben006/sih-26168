"""Leakage-free outage evaluation. Reference data is read only by the scorer."""
from pathlib import Path
import time
import numpy as np
from .data import read_drive
from .ai_speed_model import AISpeedEstimator, MODEL_PATH
from .navigation import NavigationEngine, wrap

def run_outage(d, start_s, duration=30., use_ai=True, model_path=MODEL_PATH):
    t = d['t']
    # Start immediately after a real fix; no interpolated future position initializes the engine.
    if start_s >= t[d['fix_ids'][-1]]:
        raise ValueError('Outage start is beyond the final GNSS fix.')
    fix = int(d['fix_ids'][np.searchsorted(t[d['fix_ids']],start_s)])
    start = fix+1
    end = start+int(round(duration*10))
    if start < 200 or end >= len(t):
        raise ValueError('Need 20 seconds of calibration and a complete outage within the recording.')
    # GNSS segment headings describe interval midpoints. Fit gyro projection on
    # previous turns, then propagate the latest midpoint heading up to the fix.
    fixes = d['fix_ids'][d['fix_ids'] < start]
    fixes = fixes[-80:]
    delta = np.diff(d['xy'][fixes],axis=0)
    headings = np.unwrap(np.arctan2(delta[:,1],delta[:,0]))
    middle = ((fixes[1:]+fixes[:-1])//2).astype(int)
    velocity = np.linalg.norm(delta,axis=1)/np.maximum(.1,np.diff(t[fixes]))
    A=[]; Y=[]
    for j in range(1,len(headings)):
        turn = float(wrap(headings[j]-headings[j-1]))
        if min(velocity[j],velocity[j-1])>3 and abs(turn)<1.5:
            A.append(np.sum(d['gyro'][middle[j-1]:middle[j]],axis=0)*.1)
            Y.append(turn)
    yaw_axis = np.array([0.,0.,1.])
    alignment_quality = 'gravity-axis fallback'
    if len(A)>=8 and np.std(Y)>.05:
        A=np.asarray(A);Y=np.asarray(Y)
        fitted=np.linalg.solve(A.T@A+np.eye(3)*.2,A.T@Y)
        if .1<np.linalg.norm(fitted)<2.:
            yaw_axis=fitted
            alignment_quality='GNSS-calibrated gyro projection'
    # Receiver speed/heading are only read BEFORE the blackout. Infer the ambiguous
    # speed unit from past displacement, and reject incompatible bearing conventions.
    raw=d.get('raw_speed'); gps_h=d.get('gps_heading'); initial_speed=float(d['speed'][start-1])
    receiver_ok=False
    if raw is not None and gps_h is not None:
        moving=velocity>3
        gps_mid=gps_h[middle]
        angular=np.abs(wrap(gps_mid-headings))
        ratios=[]
        for j in range(len(velocity)):
            average=float(np.mean(raw[fixes[j]:fixes[j+1]]))
            if velocity[j]>3 and average>1:ratios.append(velocity[j]/average)
        scale=float(np.median(ratios)) if ratios else 0.
        unit=1. if abs(scale-1)<.2 else 1/3.6 if abs(scale-1/3.6)<.06 else None
        receiver_ok=unit is not None and moving.sum()>=5 and np.median(angular[moving])<.35
        if receiver_ok:
            initial_speed=float(np.clip(raw[start-1]*unit,0,60))
            rows=[]; turns=[]
            for j in range(1,len(fixes)):
                lo,hi=fixes[j-1],fixes[j];dt=float(t[hi]-t[lo])
                turn=float(wrap(gps_h[hi]-gps_h[lo]))
                if raw[lo]*unit>3 and raw[hi]*unit>3 and abs(turn)<1.5:
                    rows.append(np.r_[np.sum(d['gyro'][lo:hi],axis=0)*.1,dt]);turns.append(turn)
            if len(rows)>=8 and np.std(turns)>.05:
                design=np.asarray(rows);target=np.asarray(turns)
                params=np.linalg.solve(design.T@design+np.diag([.2,.2,.2,.2]),design.T@target)
                if .1<np.linalg.norm(params[:3])<2:
                    yaw_axis=params[:3]; alignment_quality='pre-outage receiver heading calibration'
                    bias=-float(params[3])
                else:bias=0.
            else:bias=0.
    yaw_rates = d['gyro']@yaw_axis
    cal=max(0,start-300)
    if not receiver_ok:
        bias=0.
        if len(A)>=8:
            residual=np.asarray(Y)-np.asarray(A)@yaw_axis
            bias=float(np.clip(-np.median(residual)/9.,-.02,.02))
    heading=float(gps_h[start-1]) if receiver_ok else float(headings[-1]+np.sum(yaw_rates[middle[-1]:start])*.1-bias*(start-middle[-1])*.1)
    # Forward axis stays in the plane orthogonal to gravity.
    dv=(d['speed'][10:start]-d['speed'][:start-10])
    lin=np.array([d['linear'][max(0,i-9):i+1].mean(axis=0) for i in range(10,start)])
    direction=np.linalg.lstsq(lin,dv,rcond=None)[0]
    up=d['gravity'][cal:start].mean(axis=0);up/=max(np.linalg.norm(up),1e-6)
    direction-=up*np.dot(direction,up)
    norm=np.linalg.norm(direction)
    direction=direction/norm if norm>.05 else np.zeros(3)
    acc_bias=float(np.mean(d['linear'][cal:start]@direction))
    engine = NavigationEngine(d['xy'][start-1],initial_speed,heading)
    engine.x[4] = bias
    ai = AISpeedEstimator(model_path)
    last_ai = None
    for i in range(max(0,start-20),start):
        last_ai = ai.predict(d['signals'][i])
    temporal=(ai.model or {}).get('feature_version')=='anchored-temporal-v1'
    if temporal:ai.set_anchor(initial_speed)
    # Causal residual calibration ties the learned speed to the last available GNSS fix.
    offset = 0. if temporal else float(initial_speed-(last_ai if last_ai is not None else initial_speed))
    estimates, baseline, sigma, latency = [],[],[],[]
    base_pos = d['xy'][start-1].copy(); base_h = heading; base_v = float(d['speed'][start-1])
    for i in range(start,end):
        begin = time.perf_counter()
        pred = ai.predict(d['signals'][i]) if use_ai else None
        accel = 0. if (ai.model or {}).get('forward_acceleration_mode') == 'speed-update-only' else float(d['linear'][i]@direction-acc_bias)
        shock = abs(d['signals'][i,1])>3.5 or np.linalg.norm(d['linear'][i])>10
        engine.step(.1,float(yaw_rates[i]),accel,
                    ai_speed=max(0.,pred+offset) if pred is not None else None,ai_sigma=ai.sigma,shock=shock)
        latency.append((time.perf_counter()-begin)*1000)
        estimates.append(engine.x[:2].copy()); sigma.append(engine.uncertainty)
        base_h += (yaw_rates[i]-bias)*.1
        base_pos += base_v*.1*np.array([np.cos(base_h),np.sin(base_h)])
        baseline.append(base_pos.copy())
    # Ground truth enters only below this boundary, after estimation is finished.
    ref = d['reference_xy'][start:end]; estimated = np.asarray(estimates)
    errors = np.linalg.norm(estimated-ref,axis=1)
    baseline_errors = np.linalg.norm(np.asarray(baseline)-ref,axis=1)
    distance = float(np.linalg.norm(np.diff(d['reference_xy'][start-1:end],axis=0),axis=1).sum())
    drift = float(errors[-1]/distance*100) if distance>1 else None
    model = ai.model or {}
    split = 'training recording' if (d['sha256'] in model.get('train_sha256',[]) or d.get('data_sha256') in model.get('train_data_sha256',[])) else ('development holdout' if (d['sha256'] in model.get('held_out_sha256',[]) or d.get('data_sha256') in model.get('held_out_data_sha256',[])) else 'unseen recording')
    stride = max(1,len(ref)//600)
    trajectory = [dict(t=round(float(t[start+i]-t[start]),2),reference=ref[i].round(3).tolist(),
        estimated=estimated[i].round(3).tolist(),baseline=np.asarray(baseline)[i].round(3).tolist(),
        error=round(float(errors[i]),3),uncertainty=round(sigma[i],3)) for i in range(0,len(ref),stride)]
    return dict(track_name=d['name'],split=split,source='measured replay',sha256=d['sha256'],data_sha256=d.get('data_sha256'),
        start_s=float(t[start]),outage_duration_s=duration,dataset_points=len(t),source_rows=d['source_rows'],retained_rows=d['retained_rows'],reference_fix_interval_s=d['fix_interval_s'],outage_distance_m=round(distance,2),
        rmse_m=round(float(np.sqrt(np.mean(errors**2))),3),mae_m=round(float(errors.mean()),3),
        max_error_m=round(float(errors.max()),3),final_error_m=round(float(errors[-1]),3),
        drift_percentage=round(drift,3) if drift is not None else None,sih_target_met=drift is not None and drift<10,
        baseline_final_error_m=round(float(baseline_errors[-1]),3),p95_processing_ms=round(float(np.percentile(latency,95)),3),
        ai_enabled=use_ai and ai.model is not None,trajectory=trajectory,origin=d['origin'],
        limitations=[f'GPS fixes are spaced about {d["fix_interval_s"]:.1f}s; scoring interpolates them, not survey-grade truth.','No offline road map applied to this score.',
                      'Training labels use GNSS displacement/time; receiver initialization infers speed units from pre-outage displacement only.','One pre-outage calibration; phone remounts are not validated.','Desktop timing is not smartphone timing.'],
        calibration=dict(receiver_initialization=bool(receiver_ok),receiver_speed_scale=unit if receiver_ok else None,initial_speed_mps=initial_speed,gyro_bias_rad_s=bias,yaw_axis=yaw_axis.tolist(),alignment=alignment_quality,forward_axis=direction.tolist(),speed_offset_mps=offset))

class IOVNBDParser:
    @classmethod
    def process_dataset(cls,file_path,outage_duration_sec=30.,start_s=None):
        d = read_drive(file_path)
        if start_s is None:
            start_s = max(30.,float(d['t'][-1])*.35)
        return run_outage(d,start_s,outage_duration_sec)
