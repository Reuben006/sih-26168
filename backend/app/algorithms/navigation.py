"""ENU planar vehicle EKF: x,y,forward speed,yaw,yaw-rate bias; SI units."""
import math
import numpy as np

def wrap(a):
    return (a+np.pi)%(2*np.pi)-np.pi

class NavigationEngine:
    def __init__(self,xy=(0.,0.),speed=0.,heading=0.):
        self.x = np.array([*xy,speed,heading,0.],float)
        self.P = np.diag([4.,4.,1.,.03,.0004])
        self.elapsed = self.last_fix = 0.
        self.mode = 'GNSS_FUSION'
        self.rejected_fixes = 0
        self.shock = False
        self.recovery_candidate = None
        self.recovery_count = 0
    def update(self,z,H,R,angle_index=None,gate=None):
        residual = np.asarray(z)-H@self.x
        if angle_index is not None:
            residual[angle_index] = wrap(residual[angle_index])
        S = H@self.P@H.T+R
        if gate is not None and float(residual@np.linalg.solve(S,residual))>gate:
            return False
        K = np.linalg.solve(S,H@self.P).T
        self.x += K@residual
        self.x[3] = wrap(self.x[3])
        I = np.eye(5)-K@H
        self.P = I@self.P@I.T+K@R@K.T
        self.P = (self.P+self.P.T)*.5
        return True
    def step(self,dt,yaw_rate,forward_acc=0.,ai_speed=None,ai_sigma=5.,gnss=None,shock=False):
        if not np.isfinite([dt,yaw_rate,forward_acc,ai_sigma]).all() or not 0<dt<=1:
            raise ValueError('Finite SI inputs and 0 < dt <= 1 second required.')
        self.elapsed += dt
        self.shock = shock or abs(forward_acc)>8
        a = 0. if self.shock else float(np.clip(forward_acc,-6,4))
        h = self.x[3]+(yaw_rate-self.x[4])*dt*.5
        v = max(0.,self.x[2]+a*dt*.5)
        F = np.eye(5)
        F[0,2],F[1,2] = math.cos(h)*dt,math.sin(h)*dt
        F[0,3],F[1,3] = -v*math.sin(h)*dt,v*math.cos(h)*dt
        F[3,4] = -dt
        self.x[:2] += v*dt*np.array([math.cos(h),math.sin(h)])
        self.x[2] = max(0.,self.x[2]+a*dt)
        self.x[3] = wrap(self.x[3]+(yaw_rate-self.x[4])*dt)
        self.P = F@self.P@F.T+np.diag([.02,.02,.25,.0004,.000001])*dt
        if ai_speed is not None and np.isfinite(ai_speed) and not self.shock:
            H = np.zeros((1,5)); H[0,2] = 1
            self.update([np.clip(ai_speed,0,60)],H,np.array([[max(ai_sigma,1.)**2]]),gate=9.)
        self.mode = 'DEAD_RECKONING' if self.elapsed-self.last_fix>1.5 else 'GNSS_FUSION'
        if gnss is not None:
            pos,speed,heading,accuracy = gnss
            if not np.isfinite([*pos,speed,accuracy]).all() or (heading is not None and not np.isfinite(heading)):
                self.rejected_fixes += 1
                return self.x.copy()
            outage = self.elapsed-self.last_fix>5.
            candidate = self.recovery_candidate
            if outage:
                consistent = candidate is not None and 0<self.elapsed-candidate[1]<=2. and np.linalg.norm(np.asarray(pos)-candidate[0])<max(15.,(self.elapsed-candidate[1])*max(speed,1.)*1.8+10.)
                self.recovery_count = self.recovery_count+1 if consistent else 1
                self.recovery_candidate = (np.asarray(pos).copy(),self.elapsed)
                if self.recovery_count>=3:
                    # Three mutually consistent fixes permit recovery after a long outage.
                    residual = np.linalg.norm(np.asarray(pos)-self.x[:2])
                    self.P[:2,:2] += np.eye(2)*(residual/3.)**2
            else:
                self.recovery_count=0
                self.recovery_candidate=None
            H = np.zeros((2,5)); H[:,:2] = np.eye(2)
            if self.update(pos,H,np.eye(2)*max(accuracy,2.)**2,gate=25.):
                recovering = self.elapsed-self.last_fix>1.5
                self.last_fix = self.elapsed
                self.mode = 'RECOVERING' if recovering else 'GNSS_FUSION'
                H = np.zeros((1,5)); H[0,2] = 1
                self.update([speed],H,np.array([[.5**2]]))
                if speed>2 and heading is not None:
                    H = np.zeros((1,5)); H[0,3] = 1
                    self.update([heading],H,np.array([[.12**2]]),angle_index=0)
            else:
                self.rejected_fixes += 1
        self.x[2] = max(0.,self.x[2])
        return self.x.copy()
    @property
    def uncertainty(self):
        return float(2.448*np.sqrt(max(np.linalg.eigvalsh(self.P[:2,:2]))))
