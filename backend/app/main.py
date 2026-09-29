from pathlib import Path
import asyncio
import json
import tempfile
from functools import lru_cache
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from .algorithms.simulation_engine import SimulationEngine
from .algorithms.iovnbd_parser import IOVNBDParser
from .algorithms.ai_speed_model import MODEL_PATH

ROOT = Path(__file__).parent
app = FastAPI(title='KinematiX Navigation Engine',version='1.0.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173','https://appassets.androidplatform.net'],allow_methods=['GET','POST'],allow_headers=['*'])
PRESETS = {'held_out':'S-S1.csv','motorway':'S-Vw4.csv','mixed':'S-M.csv','test':'S-Vw1.csv'}

@app.get('/')
def index():
    return {'project': 'KinematiX', 'service': 'Evaluation API', 'web_app': 'http://localhost:5173/', 'alternative_web_app': 'http://127.0.0.1:5173/', 'health': '/api/health', 'api_docs': '/docs'}

@app.get('/api/health')
def health():
    return dict(status='ready',project='KinematiX',team_name='ORIGIN X',team_id='134028',model_available=MODEL_PATH.exists(),benchmark='SIH 26168',update_hz=10)

@app.get('/api/model')
def model_info():
    p = ROOT.parent/'reports/model_training.json'
    return json.loads(p.read_text()) if p.exists() else {'status':'not trained'}

@lru_cache(maxsize=24)
def evaluate(name,duration,start):
    path = ROOT/'datasets'/name
    if not path.exists(): raise FileNotFoundError('Dataset not installed')
    return IOVNBDParser.process_dataset(path,duration,start)

@app.get('/api/evaluation/preset')
def preset(preset_id:str='held_out',duration:float=Query(30,ge=5,le=120),start:float|None=Query(None,ge=20)):
    if preset_id not in PRESETS: raise HTTPException(404,'Unknown recording')
    try: return evaluate(PRESETS[preset_id],duration,start)
    except (ValueError,FileNotFoundError) as e: raise HTTPException(422,str(e))

@app.post('/api/evaluation/upload')
async def upload(file:UploadFile=File(...)):
    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise HTTPException(422,'Select an IO-VNBD smartphone CSV.')
    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.csv',delete=False) as f:
            path = Path(f.name); size = 0
            while chunk := await file.read(1024*1024):
                size += len(chunk)
                if size>80*1024*1024: raise HTTPException(413,'Maximum upload is 80 MB.')
                f.write(chunk)
        result = await asyncio.to_thread(IOVNBDParser.process_dataset,path)
        result['track_name'] = Path(file.filename).name
        return result
    except ValueError as e: raise HTTPException(422,str(e))
    finally:
        if path is not None: path.unlink(missing_ok=True)

@app.websocket('/ws/telemetry')
async def telemetry(ws:WebSocket):
    await ws.accept()
    sim = SimulationEngine()  # Every visitor has an independent simulation.
    try:
        while True:
            try:
                command = await asyncio.wait_for(ws.receive_json(),timeout=.1)
                if command.get('action')=='outage': sim.set_outage(bool(command.get('enabled')))
                elif command.get('action')=='reset': sim.reset()
                elif command.get('action')=='shock': sim.shock_pending = True
            except asyncio.TimeoutError: pass
            await ws.send_json(sim.step())
    except WebSocketDisconnect: pass
