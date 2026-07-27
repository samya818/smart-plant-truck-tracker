"""
Point d'entrée FastAPI.
Configure CORS, routers, WebSocket, et le lifespan.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
import json

from app.config import get_settings
from app.database import engine
from app.models import Base
from app.routers import trucks, events, analytics, dashboard, delays, mobile
from app.services.cv_service import CVService
from app.services.auto_train import AutoTrainPipeline

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup : création tables + nettoyage + lancement services en arrière-plan."""
    Base.metadata.create_all(bind=engine)

    # Nettoyage des cycles orphelins (redémarrages multiples du conteneur)
    from app.database import SessionLocal
    from app.models import Cycle, TruckStatus, PosteConfig, PosteType, CaptureMode
    from datetime import datetime, timedelta
    db = SessionLocal()
    try:
        seuil = datetime.utcnow() - timedelta(hours=2)
        orphelins = db.query(Cycle).filter(
            Cycle.status == TruckStatus.EN_COURS,
            Cycle.entree_porte < seuil
        ).all()
        for c in orphelins:
            c.status = TruckStatus.TERMINE
            c.sortie_porte = c.entree_porte + timedelta(minutes=90)
            c.duree_total = 90.0
        db.commit()

        # Seed par défaut pour poste_configs si vide
        if db.query(PosteConfig).count() == 0:
            defaults = [
                PosteConfig(poste=PosteType.PORTE_USINE, capture_mode=CaptureMode.HYBRID, camera_url="rtsp://cam-porte:554/stream1", is_active=True),
                PosteConfig(poste=PosteType.PARKING, capture_mode=CaptureMode.AGENT, camera_url="", is_active=True),
                PosteConfig(poste=PosteType.BASCULE, capture_mode=CaptureMode.HYBRID, camera_url="rtsp://cam-bascule:554/stream1", is_active=True),
                PosteConfig(poste=PosteType.ENSACHAGE, capture_mode=CaptureMode.CAMERA, camera_url="rtsp://cam-ensachage:554/stream1", is_active=True),
            ]
            db.add_all(defaults)
            db.commit()
            print("[Startup] Configuration initiale des 4 postes (Bi-Mode) insérée")
    finally:
        db.close()


    if settings.cv_mode == "simulation":
        cv_service = CVService()
        asyncio.create_task(cv_service.run_simulation_loop())

    auto_train = AutoTrainPipeline()
    asyncio.create_task(auto_train.schedule_loop())

    yield
    print("Arrêt du serveur...")



app = FastAPI(
    title="Lafarge Camion Tracker API V2",
    description="API traçabilité bi-mode & optimisation flux camions — LafargeHolcim Meknès",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trucks.router)
app.include_router(events.router)
app.include_router(analytics.router)
app.include_router(dashboard.router)
app.include_router(delays.router)
app.include_router(mobile.router)

import os
os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")




# --- WebSocket pour temps réel ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_text(json.dumps(message))
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)

manager = ConnectionManager()

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/health")
def health_check():
    return {"status": "ok", "mode": settings.cv_mode, "version": "2.0.0"}
