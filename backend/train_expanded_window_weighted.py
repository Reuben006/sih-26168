"""Driver-grouped experiment; freeze candidate on validation before reading test results."""
import json,hashlib,shutil
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from app.algorithms.data import read_drive,windows
from app.algorithms.iovnbd_parser import run_outage
ROOT=Path(__file__).parent
OUT=ROOT/'reports/expanded-window-weighted';OUT.mkdir(exist_ok=True)
BASE=OUT/'baseline_model.json'
if not BASE.exists():shutil.copy2(ROOT/'app/algorithms/speed_model.json',BASE)
manifest=json.loads((ROOT/'reports/expanded_split.json').read_text())
sets={'train':[],'validation':[],'test':[]};audit=[]
for entry in manifest['recordings']:
    try:
        d=read_drive(ROOT/'app/datasets/expanded'/entry['name'])
        audit.append(dict(name=entry['name'],split=entry['split'],duration_s=float(d['t'][-1]),fix_interval_s=d['fix_interval_s'],rows=d['retained_rows'],data_sha256=d['data_sha256']))
        sets[entry['split']].append(d)
    except ValueError as e:audit.append(dict(name=entry['name'],split=entry['split'],excluded=str(e)))
(OUT/'audit.json').write_text(json.dumps(audit,indent=2))
# Prevent duplicate streams across roles, even under renamed files.
role={}
for split,drives in sets.items():
    for d in drives:
        key=d['data_sha256']
        if key in role and role[key]!=split:raise ValueError('Cross-split duplicate')
        role[key]=split
print('Usable drives:',{k:len(v) for k,v in sets.items()},flush=True)
features=[];labels=[];weights=[]
for d in sets['train']:
    x,y,_=windows(d,stride=10)
    features.append(x);labels.append(y);weights.append(np.full(len(y),1/len(y)))
X=np.vstack(features);y=np.concatenate(labels);w=np.concatenate(weights)
model=ExtraTreesRegressor(n_estimators=32,max_depth=10,min_samples_leaf=12,random_state=26168,n_jobs=2)
model.fit(X,y)
result=dict(format='kinematix-forest-v1',sample_hz=10,window_samples=20,feature_version='gravity-invariant-v1',trees=[],training_protocol=manifest['protocol'])
for split,prefix in [('train','train'),('validation','held_out'),('test','test')]:
    result[prefix+'_recordings']=[d['name'] for d in sets[split]]
    result[prefix+'_sha256']=[d['sha256'] for d in sets[split]]
    result[prefix+'_data_sha256']=[d['data_sha256'] for d in sets[split]]
for estimator in model.estimators_:
    t=estimator.tree_;result['trees'].append(dict(left=t.children_left.tolist(),right=t.children_right.tolist(),feature=t.feature.tolist(),threshold=t.threshold.round(9).tolist(),value=t.value[:,0,0].round(9).tolist()))
CAND=OUT/'candidate_model.json';CAND.write_text(json.dumps(result,separators=(',',':')))
def evaluate(drives,path):
    runs=[];excluded=[]
    for d in drives:
        for duration in [10.,30.,60.]:
            try:
                r=run_outage(d,max(30.,round(float(d['t'][-1])*.35,1)),duration,model_path=path)
                runs.append(r)
            except (ValueError,IndexError) as e:excluded.append(dict(name=d['name'],duration=duration,reason=str(e)))
    return runs,excluded
def summary(runs):
    drift=[r['drift_percentage'] for r in runs if r['drift_percentage'] is not None]
    return dict(runs=len(runs),passing=sum(r['sih_target_met'] for r in runs),median_drift_pct=float(np.median(drift)),mean_endpoint_m=float(np.mean([r['final_error_m'] for r in runs])))
comparisons={};details={}
for label,path in [('baseline',BASE),('candidate',CAND)]:
    runs,excluded=evaluate(sets['validation'],path);comparisons[label]=summary(runs);details[label]=dict(runs=runs,excluded=excluded)
    print('VALIDATION',label,comparisons[label],flush=True)
# Gate defined before test: more passing windows, or equal passes and lower median drift.
a,b=comparisons['baseline'],comparisons['candidate']
selected='candidate' if (b['passing']>a['passing'] or (b['passing']==a['passing'] and b['median_drift_pct']<a['median_drift_pct'])) else 'baseline'
freeze=dict(selected=selected,validation=comparisons,selection_rule='More validation passes, breaking ties with median drift; no test-driven selection.',model_sha256=hashlib.sha256((CAND if selected=='candidate' else BASE).read_bytes()).hexdigest())
(OUT/'selection.json').write_text(json.dumps(freeze,indent=2))
(OUT/'validation.json').write_text(json.dumps(details))
print('SELECTED',selected,flush=True)
