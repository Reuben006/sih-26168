"""Drive-separated training. S-S1 is excluded from model fitting; it is a development holdout for fusion."""
import json
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from app.algorithms.data import read_drive,windows
ROOT = Path(__file__).parent

def train():
    names = ['S-M.csv','S-Vw4.csv']
    drives = [read_drive(ROOT/'app/datasets'/n) for n in names]
    held = read_drive(ROOT/'app/datasets/S-S1.csv')
    sets = [windows(d) for d in drives]
    X,y = np.vstack([s[0] for s in sets]),np.concatenate([s[1] for s in sets])
    model = ExtraTreesRegressor(n_estimators=24,max_depth=8,min_samples_leaf=12,random_state=26168,n_jobs=1)
    model.fit(X,y)
    Xv,yv,_ = windows(held)
    pred = model.predict(Xv)
    result = dict(format='kinematix-forest-v1',sample_hz=10,window_samples=20,feature_version='gravity-invariant-v1',
        train_recordings=names,train_data_sha256=[d['data_sha256'] for d in drives],held_out_data_sha256=[held['data_sha256']],train_sha256=[d['sha256'] for d in drives],held_out_recordings=[held['name']],held_out_sha256=[held['sha256']],trees=[])
    for estimator in model.estimators_:
        t = estimator.tree_
        result['trees'].append(dict(left=t.children_left.tolist(),right=t.children_right.tolist(),feature=t.feature.tolist(),
            threshold=t.threshold.round(9).tolist(),value=t.value[:,0,0].round(9).tolist()))
    out = ROOT/'app/algorithms/speed_model.json'
    out.write_text(json.dumps(result,separators=(',',':')))
    report = dict(training_recordings=names,held_out_recording=held['name'],training_windows=len(y),held_out_windows=len(yv),
        speed_mae_mps=float(np.abs(pred-yv).mean()),speed_rmse_mps=float(np.sqrt(np.mean((pred-yv)**2))),
        constant_train_mean_mae_mps=float(np.abs(y.mean()-yv).mean()),model_bytes=out.stat().st_size,
        note='GNSS displacement/time supplies training labels only; no CAN inputs. S-S1 is excluded from fitting but used for fusion development. Generalization remains experimental.')
    (ROOT/'reports').mkdir(exist_ok=True)
    (ROOT/'reports/model_training.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=='__main__':
    train()
