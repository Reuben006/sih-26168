"""JSON Lines adapter for calibrated external IMUs. No phone or FastAPI dependency.
Each sample: {"timestamp":seconds,"yaw_rate":rad/s,"forward_acc":m/s^2,
"gnss":{"east":m,"north":m,"speed":m/s,"heading":rad,"accuracy":m}}.
GNSS and ai_speed are optional. Coordinates are local ENU, never latitude degrees.
"""
import sys,json,argparse
from app.algorithms.navigation import NavigationEngine

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--speed',type=float,default=0.)
    parser.add_argument('--heading',type=float,default=0.)
    args=parser.parse_args();engine=NavigationEngine(speed=args.speed,heading=args.heading);last=None
    for line in sys.stdin:
        sample=json.loads(line);timestamp=float(sample['timestamp'])
        if last is None:last=timestamp;continue
        dt=timestamp-last
        g=sample.get('gnss');fix=None if g is None else ([g['east'],g['north']],g['speed'],g.get('heading'),g.get('accuracy',5.))
        engine.step(dt,float(sample['yaw_rate']),float(sample.get('forward_acc',0.)),sample.get('ai_speed'),gnss=fix,shock=sample.get('shock',False))
        last=timestamp
        print(json.dumps(dict(timestamp=timestamp,east=engine.x[0],north=engine.x[1],speed=engine.x[2],heading=engine.x[3],mode=engine.mode,uncertainty_m=engine.uncertainty)),flush=True)
if __name__=='__main__':main()
