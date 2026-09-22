from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from app.algorithms.simulation_engine import SimulationEngine

app = FastAPI(title="IDR-X GNSS+INS Fusion Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sim_engine = SimulationEngine()

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "engine": "IDR-X PS168", "mode": sim_engine.state}

@app.post("/api/simulation/start")
def start_sim(scenario: str = "tunnel"):
    sim_engine.start(scenario)
    return {"status": "started", "scenario": scenario}

@app.post("/api/simulation/outage")
def trigger_outage(enable: bool = True):
    sim_engine.set_gnss_outage(enable)
    return {"gnss_available": not enable, "state": sim_engine.state}

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            packet = sim_engine.step()
            await websocket.send_json(packet)
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
