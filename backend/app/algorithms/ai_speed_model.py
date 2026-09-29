"""Portable JSON forest. Never load untrusted pickle files in the application."""
from pathlib import Path
import json
import numpy as np
from .data import features
MODEL_PATH = Path(__file__).parent/'speed_model.json'
class AISpeedEstimator:
    def __init__(self,model_path=MODEL_PATH):
        self.model = json.loads(Path(model_path).read_text()) if Path(model_path).exists() else None
        self.buffer = []
        self.anchor = None
        self.elapsed = 0.
    def set_anchor(self, speed):
        self.anchor = (float(speed), features(self.buffer)) if len(self.buffer)>=20 else None
        self.elapsed = 0.
    def predict(self,signal,dt=.1):
        self.buffer.append(signal)
        self.buffer = self.buffer[-20:]
        if len(self.buffer)<20 or self.model is None:
            return None
        x = features(self.buffer)
        temporal=self.model.get('feature_version')=='anchored-temporal-v1'
        if temporal:
            if self.anchor is None:return None
            self.elapsed += dt
            x=np.r_[x,self.anchor[1],self.anchor[0],min(self.elapsed,60.)]
        predictions = []
        for tree in self.model['trees']:
            node = 0
            while tree['left'][node]!=-1:
                node = tree['left'][node] if x[tree['feature'][node]]<=tree['threshold'][node] else tree['right'][node]
            predictions.append(tree['value'][node])
        return max(0.,float(np.mean(predictions))+(self.anchor[0] if temporal else 0.))
    @property
    def sigma(self):
        return 5.
