import numpy as np
import time
from app.algorithms.es_ekf import ESEKF

class SimulationEngine:
    def __init__(self):
        self.state = "GNSS_AVAILABLE"
        self.gnss_available = True
        self.ekf = ESEKF()
        self.t = 0.0
        self.ref_pos = np.array([0.0, 0.0, 0.0])
        self.raw_dr_pos = np.array([0.0, 0.0, 0.0])
        self.raw_dr_vel = np.array([12.5, 0.0, 0.0])
        self.distance_travelled = 0.0

    def start(self, scenario="tunnel"):
        self.t = 0.0
        self.ref_pos = np.array([0.0, 0.0, 0.0])
        self.raw_dr_pos = np.array([0.0, 0.0, 0.0])
        self.raw_dr_vel = np.array([12.5, 0.0, 0.0])
        self.distance_travelled = 0.0
        self.gnss_available = True
        self.state = "GNSS_AVAILABLE"
        self.ekf = ESEKF()

    def set_gnss_outage(self, outage: bool):
        self.gnss_available = not outage
        self.state = "DEAD_RECKONING" if outage else "FUSION_RECOVERY"

    def step(self):
        dt = 0.05
        self.t += dt
        
        speed = 12.5
        yaw_rate = 0.02 * np.sin(0.2 * self.t)
        self.distance_travelled += speed * dt
        
        self.ref_pos[0] += speed * dt * np.cos(yaw_rate * self.t)
        self.ref_pos[1] += speed * dt * np.sin(yaw_rate * self.t)
        
        bias_acc = 0.25
        noise_acc = np.random.normal(0, 0.08, 3)
        acc_meas = np.array([speed * 0.01 + noise_acc[0] + bias_acc, noise_acc[1], 9.81 + noise_acc[2]])
        gyro_meas = np.array([0.0, 0.0, yaw_rate + np.random.normal(0, 0.01)])

        # Divergent unconstrained double-integration
        self.raw_dr_vel[0] += (acc_meas[0] - 0.05) * dt
        self.raw_dr_pos[0] += self.raw_dr_vel[0] * dt
        self.raw_dr_pos[1] += 0.5 * (acc_meas[1] * (dt**2)) + self.t * 0.18

        # Filtered ES-EKF integration
        self.ekf.predict_imu(acc_meas, gyro_meas, dt)
        if not self.gnss_available:
            self.ekf.update_nhc(v_lateral=0.0, v_vertical=0.0)
            self.state = "DEAD_RECKONING"
        else:
            self.ekf.update_gnss(self.ref_pos)
            self.state = "GNSS_AVAILABLE"

        pos_error = float(np.linalg.norm(self.ekf.p[0:2] - self.ref_pos[0:2]))
        drift_pct = (pos_error / max(self.distance_travelled, 1.0)) * 100.0

        return {
            "timestamp": time.time(),
            "state": self.state,
            "gnss_available": self.gnss_available,
            "distance_travelled": round(self.distance_travelled, 1),
            "ref_pos": {"x": round(self.ref_pos[0], 2), "y": round(self.ref_pos[1], 2)},
            "corrected_pos": {"x": round(self.ekf.p[0], 2), "y": round(self.ekf.p[1], 2)},
            "raw_dr_pos": {"x": round(self.raw_dr_pos[0], 2), "y": round(self.raw_dr_pos[1], 2)},
            "position_error_m": round(pos_error, 2),
            "drift_percentage": round(drift_pct, 2),
            "sih_target_met": bool(drift_pct < 10.0),
            "imu": {
                "ax": round(float(acc_meas[0]), 3),
                "ay": round(float(acc_meas[1]), 3),
                "az": round(float(acc_meas[2]), 3),
                "gz": round(float(gyro_meas[2]), 4)
            }
        }
