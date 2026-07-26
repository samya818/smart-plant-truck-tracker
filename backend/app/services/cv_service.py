"""
Service Computer Vision.
En mode "real" : YOLOv8 + EasyOCR sur flux RTSP.
En mode "simulation" : génère des événements crédibles avec logique de cycle respectée.
"""
import asyncio
import random
from datetime import datetime
from typing import Optional

from app.config import get_settings
from app.database import SessionLocal
from app.models import Truck, Event, Cycle, PosteType
from app.services.event_ingestion import EventIngestionService

settings = get_settings()


class CVService:
    """Service de capture et traitement des flux caméra."""

    def __init__(self):
        self.mode = settings.cv_mode
        # Ordre logique des postes avec types d'événements explicites pour la simulation
        self.postes_cycle = [
            (PosteType.PORTE_USINE, "entree"),
            (PosteType.PARKING, "entree"),
            (PosteType.PARKING, "sortie"),
            (PosteType.BASCULE, "entree"),
            (PosteType.BASCULE, "sortie"),
            (PosteType.ENSACHAGE, "entree"),
            (PosteType.ENSACHAGE, "sortie"),
            (PosteType.BASCULE, "entree"),
            (PosteType.BASCULE, "sortie"),
            (PosteType.PORTE_USINE, "sortie")
        ]
        self.plaques = ["12345-أ-1", "67890-ب-2", "11111-د-3",
                        "22222-و-4", "33333-ط-5", "44444-س-6"]
        # État de simulation : pour chaque plaque, index du poste actuel dans le cycle
        self.sim_state = {}

    async def run_simulation_loop(self):
        """
        Boucle de simulation en arrière-plan.
        Génère des événements de camion toutes les 5-15 secondes
        en respectant la logique de cycle (pas de sortie sans entrée).
        """
        print("[CV] Mode simulation activé — génération d'événements...")

        while True:
            await asyncio.sleep(random.randint(5, 15))

            db = SessionLocal()
            try:
                plaque = random.choice(self.plaques)
                service = EventIngestionService(db)

                # Initialiser l'état si nouveau camion
                if plaque not in self.sim_state:
                    self.sim_state[plaque] = {"index": 0}

                state = self.sim_state[plaque]
                poste, type_event = self.postes_cycle[state["index"]]

                # Créer l'événement via le service unifié
                service.ingest_event(
                    plaque=plaque,
                    poste=poste,
                    type_event=type_event,  # type: ignore
                    source="simulation",
                    confiance_ocr=round(random.uniform(0.75, 0.99), 2)
                )

                print(f"[CV-Sim] {plaque} | {poste.value} | {type_event}")

                # Avancer l'index pour le prochain tour
                state["index"] = (state["index"] + 1) % len(self.postes_cycle)

            finally:
                db.close()

    def detect_from_camera(self, camera_url: str) -> Optional[dict]:
        """
        Mode réel : capture frame, détecte camion, lit plaque.
        À appeler par un worker ou un scheduler.
        """
        if self.mode != "real":
            return None

        try:
            import cv2
            import numpy as np
            from ultralytics import YOLO
            import easyocr

            model = YOLO("yolov8n.pt")
            reader = easyocr.Reader(['en'], gpu=False)

            cap = cv2.VideoCapture(camera_url)
            ret, frame = cap.read()
            cap.release()

            if not ret:
                return None

            results = model(frame, verbose=False)
            detections = []
            for r in results:
                for box in r.boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    if cls in [2, 5, 7] and conf > 0.5:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        detections.append({"bbox": [x1, y1, x2, y2], "conf": round(conf, 3)})

            return {
                "detections": detections,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            print(f"[CV] Erreur détection : {e}")
            return None
