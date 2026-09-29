import unittest
import copy
import tempfile
from pathlib import Path
import numpy as np
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app
from app.algorithms.navigation import NavigationEngine
from app.algorithms.data import read_drive,features
from app.algorithms.iovnbd_parser import run_outage
from app.algorithms.ai_speed_model import AISpeedEstimator
from app.algorithms.simulation_engine import SimulationEngine

ROOT=Path(__file__).resolve().parents[1]
class NavigationTests(unittest.TestCase):
    def test_straight_and_turn(self):
        e=NavigationEngine(speed=10)
        for _ in range(100):e.step(.1,0)
        np.testing.assert_allclose(e.x[:2],[100,0],atol=1e-8)
        e=NavigationEngine(speed=10)
        for _ in range(100):e.step(.1,.1)
        np.testing.assert_allclose(e.x[:2],[100*np.sin(1),100*(1-np.cos(1))],atol=.01)
        self.assertGreater(e.x[1],40) # NHC must not suppress northward motion.
    def test_covariance_and_gnss_gate(self):
        e=NavigationEngine(speed=10)
        for _ in range(200):e.step(.1,.01,ai_speed=10)
        self.assertGreaterEqual(np.linalg.eigvalsh(e.P).min(),0)
        e.step(.1,0,gnss=([100000,100000],10,0,2))
        self.assertEqual(e.rejected_fixes,1)
        self.assertEqual(e.mode,'DEAD_RECKONING')
        e.step(.1,0,gnss=(e.x[:2].copy(),10,e.x[3],2))
        self.assertEqual(e.mode,'RECOVERING')
    def test_long_outage_reacquisition_and_invalid_fix(self):
        e=NavigationEngine(speed=10)
        for _ in range(100):e.step(.1,0)
        e.step(.1,0,gnss=([float('nan'),0],10,0,2))
        self.assertTrue(np.isfinite(e.x).all())
        for i in range(3):
            e.step(1.,0,gnss=([1000+i*10,0],10,0,2))
        self.assertEqual(e.mode,'RECOVERING')
    def test_invalid_and_shock(self):
        e=NavigationEngine(speed=10)
        for dt in [0,-1,2,float('nan')]:
            with self.assertRaises(ValueError):e.step(dt,0)
        e.step(.1,0,forward_acc=100,shock=True)
        self.assertEqual(e.x[2],10)
    def test_simulation_is_reproducible_and_reset(self):
        a,b=SimulationEngine(),SimulationEngine()
        for _ in range(40):self.assertEqual(a.step(),b.step())
        a.reset();b.reset();self.assertEqual(a.step(),b.step())
    def test_feature_and_forest(self):
        f=features(np.ones((20,4)))
        np.testing.assert_allclose(f,np.r_[np.ones(4),np.zeros(4),np.ones(8)])
        model=AISpeedEstimator();self.assertIsNotNone(model.model)
        for _ in range(20):prediction=model.predict([1,0,0,.1])
        self.assertTrue(np.isfinite(prediction))
    def test_reference_does_not_enter_outage_estimator(self):
        d=read_drive(ROOT/'app/datasets/S-S1.csv')
        start=100.;base=run_outage(d,start,10.)
        poisoned=copy.deepcopy(d)
        first=np.searchsorted(d['t'],base['start_s'])
        # Poison every post-start reference, label and reference velocity.
        poisoned['xy'][first:]+=100000
        poisoned['reference_xy'][first:]+=100000
        poisoned['speed'][first:]=55
        poisoned['label_speed'][first:]=55
        poisoned['raw_speed'][first:]=55
        poisoned['gps_heading'][first:]=2.5
        again=run_outage(poisoned,start,10.)
        np.testing.assert_allclose([p['estimated'] for p in base['trajectory']],[p['estimated'] for p in again['trajectory']])
        self.assertGreater(again['final_error_m'],base['final_error_m']+1000)
    def test_header_change_does_not_turn_known_drive_into_unseen(self):
        source=ROOT/'app/datasets/S-S1.csv'
        header,rest=source.read_bytes().split(b'\n',1)
        with tempfile.TemporaryDirectory() as folder:
            changed=Path(folder)/'renamed.csv'
            changed.write_bytes(header.replace(b',',b', ')+b'\n'+rest)
            a,b=read_drive(source),read_drive(changed)
            self.assertNotEqual(a['sha256'],b['sha256'])
            self.assertEqual(a['data_sha256'],b['data_sha256'])
            self.assertEqual(run_outage(b,100.,10.)['split'],'development holdout')
    def test_outage_bounds(self):
        d=read_drive(ROOT/'app/datasets/S-S1.csv')
        with self.assertRaises(ValueError):run_outage(d,1e9,30)
    def test_vehicle_csv_rejected(self):
        with self.assertRaises(ValueError):read_drive(ROOT/'app/datasets/V-S1.csv')
class ApiTests(unittest.TestCase):
    def setUp(self):self.client=TestClient(app)
    def test_health_and_errors(self):
        self.assertEqual(self.client.get('/api/health').json()['project'],'KinematiX')
        self.assertEqual(self.client.get('/api/evaluation/preset?preset_id=unknown').status_code,404)
        self.assertEqual(self.client.get('/api/evaluation/preset?duration=-1').status_code,422)
        self.assertEqual(self.client.post('/api/evaluation/upload',files={'file':('bad.txt',b'x')}).status_code,422)
    def test_ws_sessions_are_independent(self):
        with self.client.websocket_connect('/ws/telemetry') as a,self.client.websocket_connect('/ws/telemetry') as b:
            a.send_json({'action':'outage','enabled':True})
            self.assertFalse(a.receive_json()['gnss_available'])
            self.assertTrue(b.receive_json()['gnss_available'])
    def test_evaluation(self):
        r=self.client.get('/api/evaluation/preset?duration=10')
        self.assertEqual(r.status_code,200)
        d=r.json();self.assertEqual(d['source'],'measured replay')
        self.assertGreaterEqual(d['max_error_m'],d['final_error_m'])
        self.assertEqual(d['split'],'development holdout')
if __name__=='__main__':unittest.main()
