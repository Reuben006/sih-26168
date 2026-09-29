import json
from pathlib import Path
from app.algorithms.data import read_drive
from app.algorithms.iovnbd_parser import run_outage
import numpy as np
ROOT=Path(__file__).parent
out=ROOT/'reports/expanded-calibration';out.mkdir(exist_ok=True)
manifest=json.loads((ROOT/'reports/expanded_split.json').read_text())
drives=[read_drive(ROOT/'app/datasets/expanded'/e['name']) for e in manifest['recordings'] if e['split']=='validation']
for name,folder in [('drive-balanced','expanded'),('window-weighted','expanded-window-weighted')]:
    model=json.loads((ROOT/'reports'/folder/'candidate_model.json').read_text());model['forward_acceleration_mode']='speed-update-only'
    path=out/(name+'.json');path.write_text(json.dumps(model,separators=(',',':')))
    runs=[]
    for d in drives:
        for duration in [10.,30.,60.]:runs.append(run_outage(d,max(30.,round(float(d['t'][-1])*.35,1)),duration,model_path=path))
    summary=dict(passing=sum(r['sih_target_met'] for r in runs),runs=len(runs),median_drift_pct=float(np.median([r['drift_percentage'] for r in runs])),mean_endpoint_m=float(np.mean([r['final_error_m'] for r in runs])))
    (out/(name+'-validation.json')).write_text(json.dumps(dict(summary=summary,runs=runs)))
    print(name,summary,flush=True)
