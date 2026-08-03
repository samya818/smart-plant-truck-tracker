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
from app.routers import trucks, events, analytics, dashboard, delays, mobile, admin
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

        # Seed des étapes du processus officiel (modifiables par superviseur)
        from app.models import EtapeConfig
        if db.query(EtapeConfig).count() == 0:
            etapes = [
                EtapeConfig(ordre=1, code="porte_entree",   nom="① Porte Usine — Entrée",              description="Contrôle, badge, sécurité",                    seuil_minutes=10,  poste_ref="porte_usine", is_default=True),
                EtapeConfig(ordre=2, code="parking",        nom="② Parking",                           description="Zone d'attente avant pesage",                  seuil_minutes=30,  poste_ref="parking",     is_default=True),
                EtapeConfig(ordre=3, code="bascule_tare",   nom="③ Agence Logistique — Tare",          description="1er passage bascule · Pesage à vide",          seuil_minutes=15,  poste_ref="bascule",     is_default=True),
                EtapeConfig(ordre=4, code="ensachage",      nom="④ Expéditions / Ensachage",           description="Chargement du camion (sacs de ciment)",        seuil_minutes=45,  poste_ref="ensachage",   is_default=True),
                EtapeConfig(ordre=5, code="bascule_brut",   nom="③ Agence Logistique — Brut (retour)", description="2ème passage bascule · Pesage plein",           seuil_minutes=10,  poste_ref="bascule",     is_default=True),
                EtapeConfig(ordre=6, code="porte_sortie",   nom="⑤ Porte Usine — Sortie",             description="Sortie avec bon de livraison",                 seuil_minutes=10,  poste_ref="porte_usine", is_default=True),
                EtapeConfig(ordre=7, code="cycle_total",    nom="⑤ Cycle Total (① → ⑤)",              description="Durée totale autorisée · entrée→sortie usine", seuil_minutes=120, poste_ref=None,          is_default=True),
            ]
            db.add_all(etapes)
            db.commit()
            print("[Startup] 7 étapes du processus officiel insérées")
    finally:
        db.close()



    cv_service = CVService()
    if settings.cv_mode == "simulation":
        asyncio.create_task(cv_service.run_simulation_loop())
    elif settings.cv_mode == "real":
        asyncio.create_task(cv_service.run_real_loop())
    else:
        print(f"[Startup] Mode CV inconnu : '{settings.cv_mode}' — aucune boucle démarrée")

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
    allow_origins=["*"],  # ⚠️ Développement uniquement
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
app.include_router(admin.router)

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
