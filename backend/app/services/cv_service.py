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

    def _restore_state_from_db(self, db) -> None:
        """
        Restaure l'état de simulation depuis la DB au démarrage.
        Pour chaque camion avec un cycle EN_COURS, on retrouve
        le dernier événement pour continuer le cycle là où il s'était arrêté.
        """
        from app.models import Cycle, TruckStatus
        cycles_en_cours = db.query(Cycle).filter(
            Cycle.status == TruckStatus.EN_COURS
        ).all()

        for cycle in cycles_en_cours:
            truck = db.query(Truck).get(cycle.truck_id)
            if not truck or truck.immatriculation not in self.plaques:
                continue

            # Trouver le dernier événement de ce camion dans ce cycle
            last_event = db.query(Event).filter(
                Event.truck_id == cycle.truck_id,
                Event.horodatage >= cycle.entree_porte
            ).order_by(Event.horodatage.desc()).first()

            if not last_event:
                self.sim_state[truck.immatriculation] = {"index": 0}
                continue

            # Retrouver l'index correspondant au dernier événement dans postes_cycle
            last_step = (last_event.poste, last_event.type_event)
            idx = 0
            for i, step in enumerate(self.postes_cycle):
                if step[0] == last_event.poste and step[1] == last_event.type_event:
                    idx = i
            # Reprendre à l'étape suivante
            next_idx = (idx + 1) % len(self.postes_cycle)
            self.sim_state[truck.immatriculation] = {"index": next_idx}
            print(f"[CV] Restauré {truck.immatriculation} → étape {next_idx}")

    async def run_simulation_loop(self):
        """
        Boucle de simulation : chaque camion a sa propre coroutine indépendante.
        Ainsi les cycles ne s'entremêlent plus entre camions.
        """
        print("[CV] Mode simulation activé — génération d'événements...")

        # Restaurer l'état depuis la DB au démarrage
        db = SessionLocal()
        try:
            self._restore_state_from_db(db)
        finally:
            db.close()

        # Lancer une coroutine indépendante par plaque
        tasks = [asyncio.create_task(self._simulate_truck(plaque)) for plaque in self.plaques]
        await asyncio.gather(*tasks)

    async def _simulate_truck(self, plaque: str):
        """
        Coroutine indépendante par camion.
        Chaque étape du cycle est jouée dans l'ordre, avec un délai réaliste entre elles.
        """
        # Délai de démarrage aléatoire pour ne pas tous partir en même temps
        await asyncio.sleep(random.uniform(0, 30))

        if plaque not in self.sim_state:
            self.sim_state[plaque] = {"index": 0}

        # Durée entre chaque étape (en secondes) — simuler des temps réalistes
        step_delays = [
            random.randint(5, 10),    # porte_usine entree → parking entree
            random.randint(10, 30),   # parking entree → parking sortie
            random.randint(5, 10),    # parking sortie → bascule entree (tare)
            random.randint(8, 20),    # bascule entree → bascule sortie (tare)
            random.randint(5, 10),    # bascule sortie → ensachage entree
            random.randint(15, 40),   # ensachage entree → ensachage sortie
            random.randint(5, 10),    # ensachage sortie → bascule entree (brut)
            random.randint(5, 15),    # bascule entree → bascule sortie (brut)
            random.randint(5, 10),    # bascule sortie → porte_usine sortie
            random.randint(20, 60),   # porte_usine sortie → prochaine entree (temps hors usine)
        ]

        while True:
            state = self.sim_state[plaque]
            idx = state["index"]
            poste, type_event = self.postes_cycle[idx]

            # Attendre le délai de cette étape
            await asyncio.sleep(step_delays[idx])

            # Régénérer les délais aléatoires pour le prochain cycle
            if idx == len(self.postes_cycle) - 1:
                step_delays = [
                    random.randint(5, 10),
                    random.randint(10, 30),
                    random.randint(5, 10),
                    random.randint(8, 20),
                    random.randint(5, 10),
                    random.randint(15, 40),
                    random.randint(5, 10),
                    random.randint(5, 15),
                    random.randint(5, 10),
                    random.randint(20, 60),
                ]

            db = SessionLocal()
            try:
                service = EventIngestionService(db)
                service.ingest_event(
                    plaque=plaque,
                    poste=poste,
                    type_event=type_event,  # type: ignore
                    source="simulation",
                    confiance_ocr=round(random.uniform(0.75, 0.99), 2)
                )
                print(f"[CV-Sim] {plaque} | {poste.value} | {type_event}")
            except Exception as e:
                print(f"[CV-Sim] Erreur {plaque}: {e}")
            finally:
                db.close()

            # Avancer à l'étape suivante
            self.sim_state[plaque]["index"] = (idx + 1) % len(self.postes_cycle)

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
