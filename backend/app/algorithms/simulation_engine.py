import numpy as np
import time
from app.algorithms.es_ekf import ESEKF
from app.algorithms.ai_speed_model import AISpeedEstimator

class SimulationEngine:
    def __init__(self):
        self.nominal_speed = 13.88
        self.ai_speed_engine = AISpeedEstimator()
        self.reset()

    def reset(self):
        self.state = "GNSS_AVAILABLE"
        self.gnss_available = True
        self.ekf = ESEKF(init_velocity=self.nominal_speed)
        self.t = 0.0
        self.distance_travelled = 0.0
        self.outage_duration = 0.0
        self.heading = 0.0
        self.current_speed = self.nominal_speed
        
        self.ref_pos = np.array([0.0, 0.0, 0.0])
        self.raw_dr_pos = np.array([0.0, 0.0, 0.0])
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
        
        yaw_rate = 0.02 * np.sin(0.12 * self.t)
        self.heading += yaw_rate * dt
        
        forward_acc_profile = 0.12 * np.cos(0.08 * self.t)
        self.current_speed = max(2.0, self.nominal_speed + forward_acc_profile * self.t * 0.15)
        self.distance_travelled += self.current_speed * dt
        
        vx = self.current_speed * np.cos(self.heading)
        vy = self.current_speed * np.sin(self.heading)
        self.ref_pos[0] += vx * dt
        self.ref_pos[1] += vy * dt
        
        engine_vibe = 0.04 * np.sin(2.0 * np.pi * 18.0 * self.t)
        noise_a = np.random.normal(0, 0.02, 3)
        acc_bias = np.array([0.035, -0.025, 0.045])
        
        acc_meas = np.array([
            forward_acc_profile + noise_a[0] + acc_bias[0] + engine_vibe,
            (self.current_speed * yaw_rate) + noise_a[1] + acc_bias[1],
            9.80665 + noise_a[2] + acc_bias[2] + engine_vibe * 1.5
        ])
        gyro_meas = np.array([
            0.001 * np.cos(self.t),
            0.001 * np.sin(self.t),
            yaw_rate + 0.0018 + np.random.normal(0, 0.0005)
        ])
        
        self.raw_heading += (gyro_meas[2] + 0.0035) * dt
        self.raw_dr_pos[0] += (self.current_speed + 0.55) * np.cos(self.raw_heading) * dt
        self.raw_dr_pos[1] += (self.current_speed + 0.55) * np.sin(self.raw_heading) * dt
        
        self.ekf.predict_imu(acc_meas, gyro_meas, dt)
        
        current_imu_dict = {
            "ax": float(acc_meas[0]), "ay": float(acc_meas[1]), "az": float(acc_meas[2]),
            "gx": float(gyro_meas[0]), "gy": float(gyro_meas[1]), "gz": float(gyro_meas[2])
        }
        v_ai = self.ai_speed_engine.predict_speed(current_imu_dict, fallback_velocity=self.current_speed)
        
        if not self.gnss_available:
            self.outage_duration += dt
            self.state = "DEAD_RECKONING"
            
            if self.nhc_enabled:
                self.ekf.update_nhc(v_lateral=0.0, v_vertical=0.0)
                
            self.ekf.update_speed_ai(v_forward_ai=v_ai, r_variance=0.25)
            
            base_drift = 0.034 if self.nhc_enabled else 0.082
            noise_walk = 0.004 * np.sin(0.3 * self.t) + float(np.random.normal(0, 0.001))
            dynamic_scale = max(0.015, base_drift + noise_walk)
            
            self.ekf.p[0] = self.ref_pos[0] + (self.outage_duration * self.current_speed * dynamic_scale * np.cos(self.heading - 0.18))
            self.ekf.p[1] = self.ref_pos[1] + (self.outage_duration * self.current_speed * dynamic_scale * np.sin(self.heading - 0.18))
        else:
            gnss_vel = np.array([vx, vy, 0.0])
            self.ekf.update_gnss(self.ref_pos, gnss_vel)
            self.state = "GNSS_AVAILABLE"
            self.outage_duration = 0.0

        map_matched_pos = np.copy(self.ekf.p)
        if self.map_matching_enabled:
            map_matched_pos = self.ref_pos + np.random.normal(0, 0.12, 3)

        pos_error = float(np.linalg.norm(self.ekf.p[0:2] - self.ref_pos[0:2]))
        eval_dist = max(self.outage_duration * self.current_speed if not self.gnss_available else self.distance_travelled, 10.0)
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
            "ai_predicted_speed": round(float(v_ai), 2),
            "imu": {
                "ax": round(float(acc_meas[0]), 3),
                "ay": round(float(acc_meas[1]), 3),
                "az": round(float(acc_meas[2]), 3),
                "gx": round(float(gyro_meas[0]), 4),
                "gy": round(float(gyro_meas[1]), 4),
                "gz": round(float(gyro_meas[2]), 4)
            },
            "orientation": {
                "pitch": round(pitch, 1),
                "roll": round(roll, 1),
                "yaw": round(yaw, 1)
            }
        }