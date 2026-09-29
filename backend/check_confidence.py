import json
from pathlib import Path
from app.algorithms.data import read_drive
from app.algorithms.iovnbd_parser import run_outage
runs=[]
for name in ['S-S1.csv','S-S2.csv','S-S3a.csv','S-S3b.csv','S-S3c.csv','S-S4.csv']:
 d=read_drive(Path(__file__).parent/'app/datasets/expanded'/name)
 for duration in [10.,30.,60.]:
  r=run_outage(d,round(d['t'][-1]*.35,1),duration,model_path=Path(__file__).parent/'reports/speed-confidence/candidate.json');runs.append(r);print(name,duration,r['drift_percentage'],r['calibration'],flush=True)
Path('backend/reports/speed-confidence/validation.json').write_text(json.dumps(runs))
