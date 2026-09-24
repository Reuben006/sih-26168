import os
import glob
import pandas as pd
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
import joblib

def read_official_csv(path: str) -> pd.DataFrame:
    """Reads dataset with encoding fallback and whitespace stripping on column headers."""
    for enc in ['latin1', 'utf-8-sig', 'utf-8', 'cp1252']:
        try:
            df = pd.read_csv(path, encoding=enc, low_memory=False)
            df.columns = [str(c).strip() for c in df.columns]
            return df
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, encoding='utf-8', errors='replace', low_memory=False)

def extract_features_from_df(df: pd.DataFrame, window_size: int = 20):
    cols = {c.lower(): c for c in df.columns}

    # Match official IO-VNBD headers
    ax_col = next((cols[k] for k in cols if 'accelerometer x' in k or k in ['ax', 'acc_x', 'linear_acceleration_x']), None)
    ay_col = next((cols[k] for k in cols if 'accelerometer y' in k or k in ['ay', 'acc_y', 'linear_acceleration_y']), None)
    az_col = next((cols[k] for k in cols if 'accelerometer z' in k or k in ['az', 'acc_z', 'linear_acceleration_z']), None)
    gz_col = next((cols[k] for k in cols if 'gyroscope yaw' in k or k in ['gz', 'gyro_z', 'angular_velocity_z']), None)
    speed_col = next((cols[k] for k in cols if 'speed' in k or 'velocity' in k), None)

    if not (ax_col and ay_col and az_col and gz_col):
        print("  Missing required sensor columns in dataset.")
        return None, None

    # Cast to numeric and drop NaN/corrupted rows
    clean_cols = [ax_col, ay_col, az_col, gz_col]
    if speed_col:
        clean_cols.append(speed_col)
    
    sub = df[clean_cols].apply(pd.to_numeric, errors='coerce').dropna()
    if len(sub) < window_size:
        return None, None

    ax = sub[ax_col].values.astype(float)
    ay = sub[ay_col].values.astype(float)
    az = sub[az_col].values.astype(float)
    gz = sub[gz_col].values.astype(float)

    # Convert km/h to m/s if reading GPS SPEED (Kmh)
    if speed_col:
        raw_speed = sub[speed_col].values.astype(float)
        speed = raw_speed / 3.6 if 'kmh' in speed_col.lower() else raw_speed
    else:
        speed = np.ones(len(sub)) * 13.5

    X, y = [], []
    for i in range(0, len(sub) - window_size, window_size // 2):
        w_ax = ax[i:i+window_size]
        w_ay = ay[i:i+window_size]
        w_az = az[i:i+window_size]
        w_gz = gz[i:i+window_size]

        feat = [
            float(np.mean(w_ax)), float(np.std(w_ax)),
            float(np.mean(w_ay)), float(np.std(w_ay)),
            float(np.mean(w_az)), float(np.std(w_az)),
            float(np.mean(w_gz)), float(np.std(w_gz)),
            float(np.sqrt(np.mean(w_ax**2 + w_ay**2))),
            float(np.std(w_az - 9.80665))
        ]
        X.append(feat)
        y.append(float(np.mean(speed[i:i+window_size])))

    return np.array(X), np.array(y)

def train_official():
    dataset_files = glob.glob("app/datasets/*.csv")
    print(f"Discovered {len(dataset_files)} CSV file(s) in app/datasets/...")

    all_X, all_y = [], []
    for f in dataset_files:
        print(f"Reading: {os.path.basename(f)}...")
        df = read_official_csv(f)
        X_sub, y_sub = extract_features_from_df(df)
        if X_sub is not None and len(X_sub) > 0:
            all_X.append(X_sub)
            all_y.append(y_sub)
            print(f"  Extracted {len(X_sub)} synchronized windows.")

    if not all_X:
        print("No windows extracted. Aborting training.")
        return

    X_train = np.vstack(all_X)
    y_train = np.concatenate(all_y)

    print(f"\nFitting ExtraTreesRegressor on {X_train.shape[0]} windows...")
    model = ExtraTreesRegressor(n_estimators=45, max_depth=12, random_state=42, n_jobs=1)
    model.fit(X_train, y_train)

    os.makedirs("app/algorithms", exist_ok=True)
    out_path = "app/algorithms/ai_speed_model.pkl"
    joblib.dump(model, out_path)
    print(f"Successfully trained and saved model: {out_path}")

if __name__ == "__main__":
    train_official()