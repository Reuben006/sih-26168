"""Train a GNSS-anchored temporal speed-change prior on training drivers only."""
import json,hashlib
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from app.algorithms.data import read_drive,features
from app.algorithms.iovnbd_parser import run_outage
ROOT=Path(__file__).parent;OUT=ROOT/'reports/temporal';OUT.mkdir(exist_ok=True)
manifest=json.loads((ROOT/'reports/expanded_split.json').read_text());X=[];y=[];trained=[]
for entry in manifest['recordings']:
 if entry['split']!='train':continue
 try:d=read_drive(ROOT/'app/datasets/expanded'/entry['name'])
 except ValueError:continue
 f=d['fix_ids'];velocity=np.linalg.norm(np.diff(d['xy'][f],axis=0),axis=1)/np.diff(d['t'][f]);ratios=[]
 for j in range(len(velocity)):
  raw=d['raw_speed'][f[j]:f[j+1]].mean()
  if velocity[j]>3 and raw>1:ratios.append(velocity[j]/raw)
 ratio=np.median(ratios) if ratios else 0
 unit=1. if abs(ratio-1)<.2 else 1/3.6 if abs(ratio-1/3.6)<.06 else None
 if unit is None:continue
 speed=d['raw_speed']*unit
 for i in range(20,len(speed)-20,30):
  anchor=features(d['signals'][i-20:i])
  for horizon in [1,5,10,20,30,60]:
   j=i+horizon*10
   if j>=len(speed):continue
   X.append(np.r_[features(d['signals'][j-19:j+1]),anchor,speed[i-1],horizon]);y.append(speed[j]-speed[i-1])
 trained.append(d)
print('Training',len(trained),'recordings',len(y),'temporal examples',flush=True)
model=ExtraTreesRegressor(n_estimators=32,max_depth=12,min_samples_leaf=16,random_state=26168,n_jobs=2);model.fit(np.asarray(X),np.asarray(y))
m=dict(format='kinematix-forest-v1',feature_version='anchored-temporal-v1',sample_hz=10,window_samples=20,forward_acceleration_mode='speed-update-only',train_recordings=[d['name'] for d in trained],train_sha256=[d['sha256'] for d in trained],train_data_sha256=[d['data_sha256'] for d in trained],trees=[])
for tree in model.estimators_:
 t=tree.tree_;m['trees'].append(dict(left=t.children_left.tolist(),right=t.children_right.tolist(),feature=t.feature.tolist(),threshold=t.threshold.round(9).tolist(),value=t.value[:,0,0].round(9).tolist()))
path=OUT/'candidate.json';path.write_text(json.dumps(m,separators=(',',':')))
runs=[]
for entry in manifest['recordings']:
 if entry['split']!='validation':continue
 d=read_drive(ROOT/'app/datasets/expanded'/entry['name'])
 for duration in [10.,30.,60.]:
  r=run_outage(d,round(d['t'][-1]*.35,1),duration,model_path=path);runs.append(r)
summary=dict(passing=sum(r['sih_target_met'] for r in runs),runs=len(runs),mean_endpoint_m=float(np.mean([r['final_error_m'] for r in runs])),median_drift_pct=float(np.median([r['drift_percentage'] for r in runs])))
(OUT/'validation.json').write_text(json.dumps(dict(summary=summary,runs=runs)));print(summary,flush=True)
