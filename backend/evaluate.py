"""Generate reproducible measured artifacts, including unsuccessful runs."""
import json
from pathlib import Path
from datetime import datetime,timezone
from app.algorithms.data import read_drive
from app.algorithms.iovnbd_parser import run_outage
ROOT=Path(__file__).parent
runs=[]
rejected=[]
for name in ['S-S1.csv','S-M.csv','S-Vw4.csv','S-Vw1.csv']:
    try:
        drive=read_drive(ROOT/'app/datasets'/name)
    except ValueError as error:
        rejected.append(dict(recording=name,reason=('Stationary sensor-bias recording (source paper Table A4-1); moving-distance drift is not applicable.' if name=='S-Vw1.csv' else str(error))))
        print(name,'REJECTED:',error,flush=True)
        continue
    fractions=[.2,.35,.65] if name=='S-S1.csv' else [.35]
    for fraction in fractions:
        for duration in [10.,30.,60.]:
            start=round(float(drive['t'][-1])*fraction,1)
            result=run_outage(drive,start,duration)
            runs.append(result)
            print(name,start,duration,result['drift_percentage'],flush=True)
report=dict(created_at=datetime.now(timezone.utc).isoformat(),protocol='Fixed fractions 20/35/65% of S-S1 development holdout; 35% of training drives. S-Vw1 is a stationary calibration control, excluded from moving-distance scores. 10/30/60 second blackouts. All outcomes retained.',runs=runs,rejected_recordings=rejected)
(ROOT/'reports').mkdir(exist_ok=True)
(ROOT/'reports/benchmark_summary.json').write_text(json.dumps(report,indent=2))
(ROOT.parent/'frontend/public/benchmark_summary.json').write_text(json.dumps(report,separators=(',',':')))
# Self-contained SVG plots preserve equal horizontal/vertical scale.
for i,r in enumerate(runs):
    pts=r['trajectory']; allp=[p[k] for p in pts for k in ('reference','estimated','baseline')]
    xs=[p[0] for p in allp];ys=[p[1] for p in allp]
    cx=(min(xs)+max(xs))/2;cy=(min(ys)+max(ys))/2
    scale=min(800/max(10,max(xs)-min(xs)),420/max(10,max(ys)-min(ys)))
    paths=''
    for key,color in [('baseline','#c68581'),('reference','#86b6e9'),('estimated','#53dfba')]:
        coords=' '.join(f'{460+(p[key][0]-cx)*scale:.2f},{290-(p[key][1]-cy)*scale:.2f}' for p in pts)
        paths+=f'<polyline points="{coords}" stroke="{color}" stroke-width="2" fill="none"/>'
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="920" height="580" viewBox="0 0 920 580"><rect width="920" height="580" fill="#101c24"/><g font-family="sans-serif" fill="#dce9e5"><text x="30" y="35" font-size="20">KinematiX / ORIGIN X / 134028 | {r["track_name"]} | {r["outage_duration_s"]:g}s outage</text><text x="30" y="58" font-size="12">{r["split"]} · endpoint drift {r["drift_percentage"]}% · RMSE {r["rmse_m"]}m</text>{paths}<text x="30" y="550" font-size="12">Green: estimated · Blue: GPS reference · Coral: constant-speed baseline | Equal ENU scale, metres</text></g></svg>'
    (ROOT/'reports'/f'trajectory-{i+1:02}.svg').write_text(svg,encoding='utf-8')
print(f'Wrote {len(runs)} measured runs and SVG trajectory plots.')
