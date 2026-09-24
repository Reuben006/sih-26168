import numpy as np

class ESEKF:
    def __init__(self, init_velocity: float = 13.88):
        self.p = np.zeros(3)
        self.v = np.array([init_velocity, 0.0, 0.0])
        self.q = np.array([1.0, 0.0, 0.0, 0.0])
        self.ba = np.zeros(3)
        self.bg = np.zeros(3)
        
        # Error Covariance Matrix [delta_p (3), delta_v (3), delta_theta (3), delta_ba (3), delta_bg (3)]
        self.P = np.eye(15) * 0.1
        self.P[0:3, 0:3] *= 0.5
        self.P[3:6, 3:6] *= 0.1
        self.P[6:9, 6:9] *= 0.05
        self.Q = np.eye(15) * 1e-4

    def quat_to_dcm(self, q: np.ndarray) -> np.ndarray:
        w, x, y, z = q
        return np.array([
            [1 - 2*(y**2 + z**2), 2*(x*y - z*w), 2*(x*z + y*w)],
            [2*(x*y + z*w), 1 - 2*(x**2 + z**2), 2*(y*z - x*w)],
            [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x**2 + y**2)]
        ])

    def predict_imu(self, acc: np.ndarray, gyro: np.ndarray, dt: float):
        acc_corr = acc - self.ba
        gyro_corr = gyro - self.bg
        R_b_to_n = self.quat_to_dcm(self.q)
        gravity_n = np.array([0.0, 0.0, 9.80665])
        acc_n = R_b_to_n @ acc_corr - gravity_n
        
        self.p += self.v * dt + 0.5 * acc_n * (dt**2)
        self.v += acc_n * dt
        
        omega_norm = np.linalg.norm(gyro_corr)
        if omega_norm > 1e-8:
            axis = gyro_corr / omega_norm
            angle = omega_norm * dt
            dq = np.array([np.cos(angle/2), *(axis * np.sin(angle/2))])
            w1, x1, y1, z1 = self.q
            w2, x2, y2, z2 = dq
            self.q = np.array([
                w1*w2 - x1*x2 - y1*y2 - z1*z2,
                w1*x2 + x1*w2 + y1*z2 - z1*y2,
                w1*y2 - x1*z2 + y1*w2 + z1*x2,
                w1*z2 + x1*y2 - y1*x2 + z1*w2
            ])
            self.q /= np.linalg.norm(self.q)

        F = np.eye(15)
        F[0:3, 3:6] = np.eye(3) * dt
        F[3:6, 9:12] = -R_b_to_n * dt
        F[6:9, 12:15] = -np.eye(3) * dt
        self.P = F @ self.P @ F.T + self.Q * dt

    def update_nhc(self, v_lateral: float = 0.0, v_vertical: float = 0.0):
        H = np.zeros((2, 15))
        H[0, 4] = 1.0  # Lateral Velocity
        H[1, 5] = 1.0  # Vertical Velocity
        R = np.eye(2) * 0.02
        z = np.array([v_lateral, v_vertical])
        y = z - np.array([self.v[1], self.v[2]])
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)
        dx = K @ y
        self.p += dx[0:3]
        self.v += dx[3:6]
        self.ba += dx[9:12]
        self.bg += dx[12:15]
        self.P = (np.eye(15) - K @ H) @ self.P

    def update_speed_ai(self, v_forward_ai: float, r_variance: float = 0.15):
        H = np.zeros((1, 15))
        H[0, 3] = 1.0
        y = np.array([v_forward_ai - self.v[0]])
        S = H @ self.P @ H.T + r_variance
        K = self.P @ H.T / S[0, 0]
        dx = (K * y[0]).flatten()
        self.p += dx[0:3]
        self.v += dx[3:6]
        self.ba += dx[9:12]
        self.bg += dx[12:15]
        self.P = (np.eye(15) - np.outer(K, H[0])) @ self.P

    def update_gnss(self, gnss_pos: np.ndarray, gnss_vel: np.ndarray):
        H = np.zeros((6, 15))
        H[0:3, 0:3] = np.eye(3)
        H[3:6, 3:6] = np.eye(3)
        
        R = np.eye(6)
        R[0:3, 0:3] *= 0.15
        R[3:6, 3:6] *= 0.05
        
        y = np.concatenate([gnss_pos - self.p, gnss_vel - self.v])
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)
        dx = K @ y
        
        self.p += dx[0:3]
        self.v += dx[3:6]
        self.ba += dx[9:12]
        self.bg += dx[12:15]
        self.P = (np.eye(15) - K @ H) @ self.P