import numpy as np

class ESEKF:
    # 15-State Error-State Kalman Filter for INS/GNSS Integration
    def __init__(self):
        # States: pos(3), vel(3), att(3), acc_bias(3), gyro_bias(3)
        self.p = np.zeros(3)
        self.v = np.zeros(3)
        self.q = np.array([1.0, 0.0, 0.0, 0.0])
        self.ba = np.zeros(3)
        self.bg = np.zeros(3)
        self.P = np.eye(15) * 0.01

    def predict_imu(self, acc: np.ndarray, gyro: np.ndarray, dt: float):
        acc_corr = acc - self.ba
        gyro_corr = gyro - self.bg
        
        self.p += self.v * dt + 0.5 * acc_corr * (dt**2)
        self.v += acc_corr * dt
        
        F = np.eye(15)
        F[0:3, 3:6] = np.eye(3) * dt
        Q = np.eye(15) * 1e-4
        self.P = F @ self.P @ F.T + Q

    def update_nhc(self, v_lateral: float = 0.0, v_vertical: float = 0.0):
        # Non-Holonomic Constraints: Lateral and vertical velocities approach zero
        H = np.zeros((2, 15))
        H[0, 4] = 1.0
        H[1, 5] = 1.0
        
        R = np.eye(2) * 0.05
        z = np.array([v_lateral, v_vertical])
        y = z - np.array([self.v[1], self.v[2]])
        
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)
        dx = K @ y
        
        self.p += dx[0:3]
        self.v += dx[3:6]
        self.P = (np.eye(15) - K @ H) @ self.P

    def update_gnss(self, gnss_pos: np.ndarray):
        H = np.zeros((3, 15))
        H[0:3, 0:3] = np.eye(3)
        R = np.eye(3) * 2.0
        
        y = gnss_pos - self.p
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)
        dx = K @ y
        
        self.p += dx[0:3]
        self.v += dx[3:6]
        self.P = (np.eye(15) - K @ H) @ self.P
