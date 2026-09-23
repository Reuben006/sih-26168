import os
import asyncio
import shutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from app.algorithms.simulation_engine import SimulationEngine
from app.algorithms.iovnbd_parser import IOVNBDParser

app = FastAPI(title="IDR-X Engine API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sim = SimulationEngine()

@app.get("/api/health")
def health():
    return {"status": "operational", "project": "IDR-X PS168", "state": sim.state}

@app.post("/api/simulation/start")
def start_simulation():
    sim.reset()
    return {"status": "started", "state": sim.state}

@app.post("/api/simulation/outage")
def toggle_outage(enable: bool = True):
    sim.set_outage(enable)
    return {"gnss_available": sim.gnss_available, "state": sim.state}

@app.post("/api/simulation/toggle-nhc")
def toggle_nhc(enable: bool = True):
    sim.nhc_enabled = enable
    return {"nhc_enabled": sim.nhc_enabled}

@app.post("/api/simulation/toggle-map-matching")
def toggle_map_matching(enable: bool = True):
    sim.map_matching_enabled = enable
    return {"map_matching_enabled": sim.map_matching_enabled}

@app.post("/api/evaluation/upload")
async def upload_dataset(file: UploadFile = File(...)):
    temp_dir = "./temp_datasets"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    results = IOVNBDParser.process_dataset(temp_path)
    os.remove(temp_path)
    return results

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            packet = sim.step()
            await websocket.send_json(packet)
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass