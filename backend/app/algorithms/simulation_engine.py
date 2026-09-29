"""A deterministic synthetic drive. Truth never enters the estimator during blackout."""
import numpy as np
from .navigation import NavigationEngine
class SimulationEngine:
    def __init__(self):
        self.reset()
    def reset(self):
        self.rng = np.random.default_rng(26168)
        self.engine = NavigationEngine(speed=12.)
        self.t = self.heading = self.distance = self.outage_duration = 0.
        self.truth = np.zeros(2)
        self.raw = np.zeros(2)
        self.raw_h = 0.
        self.gnss_available = True
        self.shock_pending = False
    def set_outage(self,enable):
        self.gnss_available = not enable
        if not enable:
            self.outage_duration = 0.
    def step(self):
        dt = .1; self.t += dt
        speed = 12.+2*np.sin(self.t*.04)
        accel = .08*np.cos(self.t*.04)
        yaw = .035*np.sin(self.t*.09)
        self.heading += yaw*dt
        self.truth += speed*dt*np.array([np.cos(self.heading),np.sin(self.heading)])
        self.distance += speed*dt
        gyro = yaw+.002+self.rng.normal(0,.001)
        measured_acc = accel+.008+self.rng.normal(0,.06)
        shock = self.shock_pending; self.shock_pending = False
        if shock: measured_acc += 15
        fix = None
        if self.gnss_available and round(self.t*10)%10==0:
            fix = (self.truth+self.rng.normal(0,1.,2),speed+self.rng.normal(0,.1),self.heading,2.)
        if not self.gnss_available: self.outage_duration += dt
        self.engine.step(dt,gyro,measured_acc,gnss=fix,shock=shock)
        self.raw_h += gyro*dt
        self.raw += 12.*dt*np.array([np.cos(self.raw_h),np.sin(self.raw_h)])
        error = float(np.linalg.norm(self.engine.x[:2]-self.truth))
        return dict(source='synthetic',timestamp=self.t,state=self.engine.mode,gnss_available=self.gnss_available,
            distance_travelled=self.distance,outage_duration_s=self.outage_duration,position_error_m=error,
            speed_mps=float(self.engine.x[2]),heading_deg=float(np.degrees(self.engine.x[3])),uncertainty_m=self.engine.uncertainty,
            ref_pos=dict(zip(('x','y'),self.truth)),corrected_pos=dict(zip(('x','y'),self.engine.x[:2])),
            raw_dr_pos=dict(zip(('x','y'),self.raw)),shock=shock,imu=dict(ax=measured_acc,ay=speed*yaw,az=9.80665,gz=gyro),
            note='Synthetic sensor demonstration; not IO-VNBD benchmark evidence.')
