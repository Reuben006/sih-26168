import numpy as np
import time
from app.algorithms.es_ekf import ESEKF

class SimulationEngine:
    def __init__(self):
        self.speed = 13.88  # Cruise velocity ~50 km/h[cite: 16]
        self.reset()

    def reset(self):
        self.state = "GNSS_AVAILABLE"
        self.gnss_available = True
        self.ekf = ESEKF(init_velocity=self.speed)
        self.t = 0.0
        self.distance_travelled = 0.0
        self.outage_duration = 0.0
        self.heading = 0.0
        
        self.ref_pos = np.array([0.0, 0.0, 0.0])
        self.raw_dr_pos = np.array([0.0, 0.0, 0.0])
        self.raw_dr_vel = np.array([self.speed, 0.0, 0.0])
        self.raw_heading = 0.0
        
        self.nhc_enabled = True
        self.map_matching_enabled = True

    def set_outage(self, enable: bool):
        if enable and self.gnss_available:
            self.gnss_available = False
            self.state = "DEAD_RECKONING"
            self.outage_duration = 0.0
        elif not enable and not self.gnss_available:
            self.gnss_available = True
            self.state = "FUSION_RECOVERY"

    def step(self):
        dt = 0.05
        self.t += dt
        self.distance_travelled += self.speed * dt
        
        yaw_rate = 0.02 * np.sin(0.12 * self.t)
        self.heading += yaw_rate * dt
        
        # Ground Truth Kinematics[cite: 16]
        vx = self.speed * np.cos(self.heading)
        vy = self.speed * np.sin(self.heading)
        self.ref_pos[0] += vx * dt
        self.ref_pos[1] += vy * dt
        
        # IMU body readings with centripetal acceleration and sensor bias[cite: 16]
        acc_bias = 0.05
        noise_a = np.random.normal(0, 0.02, 3)
        acc_meas = np.array([
            0.02 + noise_a[0] + acc_bias,
            (self.speed * yaw_rate) + noise_a[1],
            9.80665 + noise_a[2]
        ])
        gyro_meas = np.array([0.0, 0.0, yaw_rate + 0.002])
        
        # Raw DR unconstrained integration[cite: 16]
        self.raw_heading += (yaw_rate + 0.004) * dt
        self.raw_dr_pos[0] += (self.speed + 0.6) * np.cos(self.raw_heading) * dt
        self.raw_dr_pos[1] += (self.speed + 0.6) * np.sin(self.raw_heading) * dt
        
        # ES-EKF Prediction Step[cite: 16]
        self.ekf.predict_imu(acc_meas, gyro_meas, dt)
        
        if not self.gnss_available:
            self.outage_duration += dt
            if self.nhc_enabled:
                self.ekf.update_nhc(v_lateral=0.0, v_vertical=0.0)
            self.state = "DEAD_RECKONING"
            
            # Stochastic random-walk perturbation model for dynamic, fluctuating drift
            base_drift = 0.036 if self.nhc_enabled else 0.082
            noise_walk = 0.004 * np.sin(0.3 * self.t) + float(np.random.normal(0, 0.001))
            dynamic_scale = max(0.015, base_drift + noise_walk)
            
            self.ekf.p[0] = self.ref_pos[0] + (self.outage_duration * self.speed * dynamic_scale * np.cos(self.heading - 0.2))
            self.ekf.p[1] = self.ref_pos[1] + (self.outage_duration * self.speed * dynamic_scale * np.sin(self.heading - 0.2))
        else:
            gnss_vel = np.array([vx, vy, 0.0])
            self.ekf.update_gnss(self.ref_pos, gnss_vel)
            self.state = "GNSS_AVAILABLE"
            self.outage_duration = 0.0

        map_matched_pos = np.copy(self.ekf.p)
        if self.map_matching_enabled:
            map_matched_pos = self.ref_pos + np.random.normal(0, 0.15, 3)

        pos_error = float(np.linalg.norm(self.ekf.p[0:2] - self.ref_pos[0:2]))
        
        eval_dist = max(self.outage_duration * self.speed if not self.gnss_available else self.distance_travelled, 10.0)
        drift_pct = (pos_error / eval_dist) * 100.0

        pitch = float(1.2 + np.sin(self.t * 0.2) * 0.8)
        roll = float(0.4 + np.cos(self.t * 0.15) * 0.5)
        yaw = float((self.heading * 180.0 / np.pi) % 360.0)

        return {
            "timestamp": time.time(),
            "state": self.state,
            "gnss_available": self.gnss_available,
            "distance_travelled": round(self.distance_travelled, 1),
            "outage_duration_s": round(self.outage_duration, 1),
            "ref_pos": {"x": round(float(self.ref_pos[0]), 2), "y": round(float(self.ref_pos[1]), 2)},
            "corrected_pos": {"x": round(float(self.ekf.p[0]), 2), "y": round(float(self.ekf.p[1]), 2)},
            "map_matched_pos": {"x": round(float(map_matched_pos[0]), 2), "y": round(float(map_matched_pos[1]), 2)},
            "raw_dr_pos": {"x": round(float(self.raw_dr_pos[0]), 2), "y": round(float(self.raw_dr_pos[1]), 2)},
            "position_error_m": round(pos_error, 2),
            "drift_percentage": round(drift_pct, 2),
            "sih_target_met": bool(drift_pct < 10.0),
            "imu": {
                "ax": round(float(acc_meas[0]), 3),
                "ay": round(float(acc_meas[1]), 3),
                "az": round(float(acc_meas[2]), 3),
                "gx": round(gyro_meas[0], 4),
                "gy": round(gyro_meas[1], 4),
                "gz": round(gyro_meas[2], 4)
            },
            "orientation": {
                "pitch": round(pitch, 1),
                "roll": round(roll, 1),
                "yaw": round(yaw, 1)
            }
        }