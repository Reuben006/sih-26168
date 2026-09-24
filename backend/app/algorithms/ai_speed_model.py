import os
import warnings
import numpy as np
from typing import List, Dict, Any, Optional

# Suppress scikit-learn parallel thread warnings during batch loops[cite: 24]
warnings.filterwarnings("ignore", category=UserWarning)

try:
    import joblib
except ImportError:
    joblib = None


class AISpeedEstimator:
    """
    Lightweight AI/ML Speed and Vibration Filter.
    Estimates vehicle forward velocity from IMU energy, chassis vibration,
    and road profile characteristics without OBD-II wheel ticks.
    """
    def __init__(self, model_path: Optional[str] = "app/algorithms/ai_speed_model.pkl"):
        self.model = None
        self.window_size = 20  # 20 samples @ 100Hz = 0.2s window
        self.buffer: List[Dict[str, float]] = []
        
        if model_path and os.path.exists(model_path) and joblib:
            try:
                self.model = joblib.load(model_path)
                # CRITICAL: Force single-threaded inference to prevent joblib process spawning overhead[cite: 24]
                if hasattr(self.model, 'n_jobs'):
                    self.model.n_jobs = 1
            except Exception:
                self.model = None

    def extract_features(self, imu_window: List[Dict[str, float]]) -> np.ndarray:
        ax = np.array([pt['ax'] for pt in imu_window])
        ay = np.array([pt['ay'] for pt in imu_window])
        az = np.array([pt['az'] for pt in imu_window])
        gz = np.array([pt['gz'] for pt in imu_window])

        mean_ax = float(np.mean(ax))
        std_ax = float(np.std(ax))
        mean_ay = float(np.mean(ay))
        std_ay = float(np.std(ay))
        mean_az = float(np.mean(az))
        std_az = float(np.std(az))
        mean_gz = float(np.mean(gz))
        std_gz = float(np.std(gz))
        
        horiz_energy = float(np.sqrt(np.mean(ax**2 + ay**2)))
        vert_vibe = float(np.std(az - 9.80665))
        
        return np.array([
            mean_ax, std_ax, mean_ay, std_ay, 
            mean_az, std_az, mean_gz, std_gz, 
            horiz_energy, vert_vibe
        ])

    def predict_speed(self, current_imu: Dict[str, float], fallback_velocity: float = 13.88) -> float:
        self.buffer.append(current_imu)
        if len(self.buffer) > self.window_size:
            self.buffer.pop(0)

        if len(self.buffer) < 5:
            return fallback_velocity

        features = self.extract_features(self.buffer)

        if self.model is not None:
            try:
                pred = float(self.model.predict([features])[0])
                return max(0.0, pred)
            except Exception:
                pass

        horiz_energy = features[8]
        vert_vibe = features[9]
        std_gz = features[7]

        # Zero Velocity Update (ZUPT)
        if horiz_energy < 0.08 and vert_vibe < 0.05 and std_gz < 0.005:
            return 0.0

        v_est = 11.2 * np.sqrt(max(horiz_energy, 0.02)) + 3.8 * np.log1p(vert_vibe * 10) + 2.1 * abs(features[0])
        smoothed = 0.85 * fallback_velocity + 0.15 * v_est
        return float(np.clip(smoothed, 0.0, 45.0))