"""
Service Computer Vision — Pipeline OCR complet.

MODE "real"  : YOLOv8 détecte les camions sur flux RTSP
               → crop de la zone de plaque
               → EasyOCR lit le texte
               → fuzzy-match sur les immatriculations en DB
               → ingestion Event si confiance > seuil
               → image sauvegardée dans uploads/

MODE "simulation" : génère des événements crédibles avec logique de cycle.
"""
import asyncio
import os
import re
import random
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.database import SessionLocal
from app.models import Truck, Event, Cycle, PosteType, PosteConfig
from app.services.event_ingestion import EventIngestionService

settings = get_settings()

# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTES PIPELINE RÉEL
# ──────────────────────────────────────────────────────────────────────────────
YOLO_CLASSES_VEHICULES = {2, 5, 7}   # car, bus, truck (COCO)
YOLO_CONFIDENCE_MIN    = 0.40        # seuil détection véhicule
OCR_CONFIDENCE_MIN     = 0.45        # seuil confiance EasyOCR
FUZZY_MATCH_RATIO      = 0.70        # similarité minimale pour accepter une plaque
PLATE_EXPAND_PX        = 30          # pixels d'expansion autour du bbox pour la plaque
CAMERA_POLL_INTERVAL   = 2.0         # secondes entre deux captures par caméra
DEBOUNCE_SECONDS       = 30          # ne pas re-créer un event pour le même camion < 30s

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS OCR
# ──────────────────────────────────────────────────────────────────────────────

def _normalize_plate(text: str) -> str:
    """
    Normalise une chaîne pour comparaison :
    - Supprime accents
    - Majuscules
    - Garde uniquement alphanumérique + tirets
    """
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.upper()
    text = re.sub(r"[^A-Z0-9\-]", "", text)
    return text


def _similarity(a: str, b: str) -> float:
    """Ratio de Jaro-Winkler simplifié (longueur de sous-séquence commune / max)."""
    a, b = _normalize_plate(a), _normalize_plate(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    # Longest Common Subsequence length
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs = dp[m][n]
    return (2 * lcs) / (m + n)


def _match_plate_in_db(ocr_text: str, db) -> Optional[str]:
    """
    Compare le texte OCR avec toutes les immatriculations en DB.
    Retourne l'immatriculation la plus proche si ratio >= FUZZY_MATCH_RATIO.
    Si aucun match n'est trouvé et que le texte est valide, enregistre le nouveau camion en DB.
    """
    norm = _normalize_plate(ocr_text)
    if not norm or len(norm) < 4:
        return None

    trucks = db.query(Truck).all()
    best_ratio = 0.0
    best_plate = None
    for truck in trucks:
        ratio = _similarity(norm, truck.immatriculation)
        if ratio > best_ratio:
            best_ratio = ratio
            best_plate = truck.immatriculation

    if best_ratio >= FUZZY_MATCH_RATIO and best_plate:
        return best_plate

    # Camion inconnu mais texte OCR valide -> Création automatique en DB
    try:
        new_truck = Truck(immatriculation=norm)
        db.add(new_truck)
        db.commit()
        db.refresh(new_truck)
        print(f"[CV-OCR] 🆕 NOUVEAU CAMION ENREGISTRÉ EN DB : {norm}")
        return norm
    except Exception:
        db.rollback()
        return norm


def _save_frame(frame, poste: PosteType, plaque: str) -> Optional[str]:
    """Sauvegarde le frame annoté et retourne le chemin relatif."""
    try:
        import cv2
        upload_dir = Path(settings.upload_dir) / "captures_camera"
        upload_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{poste.value}_{plaque}_{ts}.jpg"
        filepath = upload_dir / filename
        cv2.imwrite(str(filepath), frame)
        return str(filepath)
    except Exception as e:
        print(f"[CV] Impossible de sauvegarder le frame : {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# CLASSE PRINCIPALE
# ──────────────────────────────────────────────────────────────────────────────

class CVService:
    """Service de capture et traitement des flux caméra."""

    def __init__(self):
        self.mode = settings.cv_mode
        self._yolo_model = None
        self._ocr_reader = None

        # Cache anti-doublon : {(poste, plaque): last_event_datetime}
        self._debounce: dict[tuple, datetime] = {}

        # ── Simulation ────────────────────────────────────────────────────────
        self.postes_cycle = [
            (PosteType.PORTE_USINE, "entree"),
            (PosteType.PARKING,     "entree"),
            (PosteType.PARKING,     "sortie"),
            (PosteType.BASCULE,     "entree"),
            (PosteType.BASCULE,     "sortie"),
            (PosteType.ENSACHAGE,   "entree"),
            (PosteType.ENSACHAGE,   "sortie"),
            (PosteType.BASCULE,     "entree"),
            (PosteType.BASCULE,     "sortie"),
            (PosteType.PORTE_USINE, "sortie"),
        ]
        self.plaques = [
            "12345-أ-1", "67890-ب-2", "11111-د-3",
            "22222-و-4", "33333-ط-5", "44444-س-6",
        ]
        self.sim_state: dict[str, dict] = {}

    # ══════════════════════════════════════════════════════════════════════════
    # INITIALISATION LAZY DES MODÈLES (chargé une seule fois)
    # ══════════════════════════════════════════════════════════════════════════

    def _load_yolo(self):
        """Charge YOLOv8n en mémoire (lazy, une seule fois)."""
        if self._yolo_model is not None:
            return self._yolo_model
        from ultralytics import YOLO
        print("[CV] Chargement YOLOv8n...")
        self._yolo_model = YOLO("yolov8n.pt")
        print("[CV] YOLOv8n chargé ✓")
        return self._yolo_model

    def _load_ocr(self):
        """Charge EasyOCR en mémoire (lazy, une seule fois)."""
        if self._ocr_reader is not None:
            return self._ocr_reader
        import easyocr
        # Langues : arabe (pour plaques marocaines) + anglais
        print("[CV] Chargement EasyOCR (ar + en)...")
        self._ocr_reader = easyocr.Reader(["ar", "en"], gpu=False, verbose=False)
        print("[CV] EasyOCR chargé ✓")
        return self._ocr_reader

    # ══════════════════════════════════════════════════════════════════════════
    # PIPELINE RÉEL — capture + détection + OCR
    # ══════════════════════════════════════════════════════════════════════════

    def process_frame(self, frame, poste: PosteType, db) -> Optional[dict]:
        """
        Pipeline complet sur un frame déjà capturé :
        1. YOLO → détecte les véhicules
        2. EasyOCR → lit le texte dans chaque bbox détecté
        3. Fuzzy match → trouve l'immatriculation en DB
        4. Debounce → évite les doublons < DEBOUNCE_SECONDS
        5. Ingestion → crée l'Event en DB

        Retourne un dict de résultat ou None si rien n'est détecté.
        """
        import cv2
        import numpy as np

        model  = self._load_yolo()
        reader = self._load_ocr()

        h, w = frame.shape[:2]
        results = model(frame, verbose=False)

        best_result = None

        for r in results:
            for box in r.boxes:
                cls  = int(box.cls[0])
                conf = float(box.conf[0])

                # Filtrer : seulement camions/bus/voitures avec confiance > seuil
                if cls not in YOLO_CLASSES_VEHICULES or conf < YOLO_CONFIDENCE_MIN:
                    continue

                # ── Crop du véhicule détecté ──────────────────────────────────
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                # Élargir légèrement la ROI pour inclure la plaque
                x1c = max(0, x1 - PLATE_EXPAND_PX)
                y1c = max(0, y1 - PLATE_EXPAND_PX)
                x2c = min(w, x2 + PLATE_EXPAND_PX)
                y2c = min(h, y2 + PLATE_EXPAND_PX)
                roi = frame[y1c:y2c, x1c:x2c]

                if roi.size == 0:
                    continue

                # ── Prétraitement image pour OCR ──────────────────────────────
                gray     = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                # Amélioration contraste via CLAHE
                clahe    = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                enhanced = clahe.apply(gray)
                # Upscale ×2 (améliore lisibilité petite plaque)
                upscaled = cv2.resize(enhanced, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

                # ── EasyOCR ──────────────────────────────────────────────────
                ocr_results = reader.readtext(upscaled, detail=1)
                if not ocr_results:
                    continue

                # Prendre le résultat avec la meilleure confiance
                ocr_results.sort(key=lambda x: x[2], reverse=True)
                _, ocr_text, ocr_conf = ocr_results[0]

                print(f"[CV-OCR] Poste={poste.value} | Texte brut='{ocr_text}' | Conf={ocr_conf:.2f}")

                if ocr_conf < OCR_CONFIDENCE_MIN:
                    print(f"[CV-OCR] Confiance trop faible ({ocr_conf:.2f} < {OCR_CONFIDENCE_MIN}), ignoré")
                    continue

                # ── Fuzzy match DB ───────────────────────────────────────────
                matched_plate = _match_plate_in_db(ocr_text, db)
                if not matched_plate:
                    print(f"[CV-OCR] Aucune plaque en DB correspondant à '{ocr_text}' (ratio < {FUZZY_MATCH_RATIO})")
                    continue

                # ── Debounce anti-doublon ─────────────────────────────────────
                key = (poste, matched_plate)
                last = self._debounce.get(key)
                now  = datetime.utcnow()
                if last and (now - last).total_seconds() < DEBOUNCE_SECONDS:
                    print(f"[CV-OCR] Doublon ignoré ({matched_plate} @ {poste.value} — {(now-last).total_seconds():.0f}s)")
                    continue
                self._debounce[key] = now

                # ── Déduction type_event depuis le poste ─────────────────────
                # La logique : 2 caméras par poste (entrée + sortie) identifiées
                # par la camera_url. Ici, on infère via l'état du dernier cycle.
                type_event = self._infer_event_type(matched_plate, poste, db)

                # ── Sauvegarde frame annoté ───────────────────────────────────
                annotated = frame.copy()
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(annotated, f"{matched_plate} ({ocr_conf:.0%})",
                            (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                image_path = _save_frame(annotated, poste, matched_plate)

                # ── Ingestion en DB ───────────────────────────────────────────
                try:
                    service = EventIngestionService(db)
                    event   = service.ingest_event(
                        plaque=matched_plate,
                        poste=poste,
                        type_event=type_event,
                        source="camera",
                        confiance_ocr=round(ocr_conf, 3),
                        image_path=image_path,
                    )
                    print(f"[CV] ✅ Event créé — {matched_plate} | {poste.value} | {type_event} | conf={ocr_conf:.2f}")
                    best_result = {
                        "plaque": matched_plate,
                        "poste": poste.value,
                        "type_event": type_event,
                        "confiance_ocr": round(ocr_conf, 3),
                        "confiance_yolo": round(conf, 3),
                        "image_path": image_path,
                        "event_id": event.id,
                    }
                except Exception as e:
                    print(f"[CV] Erreur ingestion {matched_plate}: {e}")

        return best_result

    def _infer_event_type(self, plaque: str, poste: PosteType, db) -> str:
        """
        Déduction du type d'événement (entrée/sortie) depuis l'état en DB :
        - Si le camion n'a pas d'entrée au poste dans le cycle en cours → "entree"
        - Sinon → "sortie"
        Pour la PORTE_USINE : si pas de cycle EN_COURS → "entree", sinon → "sortie"
        """
        from app.models import TruckStatus
        truck = db.query(Truck).filter(Truck.immatriculation == plaque).first()
        if not truck:
            return "entree"

        if poste == PosteType.PORTE_USINE:
            cycle = db.query(Cycle).filter(
                Cycle.truck_id == truck.id,
                Cycle.status   == TruckStatus.EN_COURS
            ).first()
            return "sortie" if cycle else "entree"

        # Pour les postes intermédiaires : cherche l'entrée sans sortie dans le cycle courant
        cycle = db.query(Cycle).filter(
            Cycle.truck_id == truck.id,
            Cycle.status   == TruckStatus.EN_COURS
        ).order_by(Cycle.entree_porte.desc()).first()

        if not cycle:
            return "entree"

        entree_event = db.query(Event).filter(
            Event.truck_id   == truck.id,
            Event.poste      == poste,
            Event.type_event == "entree",
            Event.horodatage >= cycle.entree_porte,
        ).first()

        return "sortie" if entree_event else "entree"

    def capture_from_url(self, camera_url: str) -> Optional[object]:
        """
        Capture un frame depuis un flux RTSP ou fichier vidéo.
        Retourne le frame numpy ou None en cas d'échec.
        """
        try:
            import cv2
            cap = cv2.VideoCapture(camera_url)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # pas de buffer : frame le plus récent
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None and frame.size > 0:
                return frame
            print(f"[CV] Impossible de lire le frame depuis {camera_url}")
            return None
        except Exception as e:
            print(f"[CV] Erreur capture {camera_url} : {e}")
            return None

    # ══════════════════════════════════════════════════════════════════════════
    # BOUCLE MODE RÉEL
    # ══════════════════════════════════════════════════════════════════════════

    async def run_real_loop(self):
        """
        Boucle principale mode réel.
        Lit la configuration des caméras depuis la DB (PosteConfig),
        puis poll chaque caméra toutes les CAMERA_POLL_INTERVAL secondes.
        """
        print("[CV] Mode RÉEL activé — démarrage du pipeline YOLO+EasyOCR")

        # Pré-chargement des modèles au démarrage (évite le lag sur la 1ère détection)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_yolo)
        await loop.run_in_executor(None, self._load_ocr)

        # Récupérer les configs caméras actives depuis la DB
        db = SessionLocal()
        try:
            configs = db.query(PosteConfig).filter(
                PosteConfig.is_active == True,
                PosteConfig.camera_url != "",
                PosteConfig.camera_url != None,
            ).all()
            camera_map = {
                cfg.poste: cfg.camera_url
                for cfg in configs
                if cfg.camera_url
            }
        finally:
            db.close()

        # Fallback : variables d'env si DB vide
        if not camera_map:
            env_map = {
                PosteType.PORTE_USINE: settings.camera_porte_usine,
                PosteType.BASCULE:     settings.camera_bascule,
                PosteType.ENSACHAGE:   settings.camera_ensachage,
                PosteType.PARKING:     settings.camera_parking,
            }
            camera_map = {k: v for k, v in env_map.items() if v}

        if not camera_map:
            print("[CV] ⚠️  Aucune URL caméra configurée. Mode réel inactif.")
            print("[CV]     Configurez CAMERA_PORTE_USINE, CAMERA_BASCULE, etc. dans .env")
            return

        print(f"[CV] Caméras configurées : {list(camera_map.keys())}")

        # Lancer une tâche asyncio par caméra
        tasks = [
            asyncio.create_task(self._camera_loop(poste, url))
            for poste, url in camera_map.items()
        ]
        await asyncio.gather(*tasks)

    async def _camera_loop(self, poste: PosteType, camera_url: str):
        """Boucle de polling pour une caméra donnée."""
        loop = asyncio.get_event_loop()
        print(f"[CV] Démarrage caméra {poste.value} → {camera_url}")
        consecutive_errors = 0

        while True:
            try:
                # Capture en thread séparé pour ne pas bloquer l'event loop
                frame = await loop.run_in_executor(None, self.capture_from_url, camera_url)

                if frame is not None:
                    consecutive_errors = 0
                    db = SessionLocal()
                    try:
                        await loop.run_in_executor(None, self.process_frame, frame, poste, db)
                    finally:
                        db.close()
                else:
                    consecutive_errors += 1
                    if consecutive_errors == 5:
                        print(f"[CV] ⚠️  Caméra {poste.value} : 5 échecs consécutifs ({camera_url})")

                await asyncio.sleep(CAMERA_POLL_INTERVAL)

            except Exception as e:
                print(f"[CV] Erreur boucle caméra {poste.value}: {e}")
                await asyncio.sleep(5)  # backoff en cas d'erreur grave

    # ══════════════════════════════════════════════════════════════════════════
    # ENDPOINT API — traitement d'image uploadée
    # ══════════════════════════════════════════════════════════════════════════

    def process_uploaded_image(self, image_bytes: bytes, poste: PosteType, db) -> Optional[dict]:
        """
        Traite une image uploadée via l'API mobile (bytes).
        Utilisé par le router mobile pour l'OCR à la demande.
        Retourne le même format que process_frame().
        """
        try:
            import cv2
            import numpy as np
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return None
            return self.process_frame(frame, poste, db)
        except Exception as e:
            print(f"[CV] Erreur traitement image uploadée : {e}")
            return None

    # ══════════════════════════════════════════════════════════════════════════
    # MODE SIMULATION (inchangé)
    # ══════════════════════════════════════════════════════════════════════════

    def _restore_state_from_db(self, db) -> None:
        """
        Restaure l'état de simulation depuis la DB au démarrage.
        Pour chaque camion avec un cycle EN_COURS, retrouve le dernier événement
        et continue le cycle là où il s'était arrêté.
        """
        from app.models import TruckStatus
        cycles_en_cours = db.query(Cycle).filter(
            Cycle.status == TruckStatus.EN_COURS
        ).all()

        for cycle in cycles_en_cours:
            truck = db.query(Truck).get(cycle.truck_id)
            if not truck or truck.immatriculation not in self.plaques:
                continue

            last_event = db.query(Event).filter(
                Event.truck_id  == cycle.truck_id,
                Event.horodatage >= cycle.entree_porte
            ).order_by(Event.horodatage.desc()).first()

            if not last_event:
                self.sim_state[truck.immatriculation] = {"index": 0}
                continue

            idx = 0
            for i, step in enumerate(self.postes_cycle):
                if step[0] == last_event.poste and step[1] == last_event.type_event:
                    idx = i
            next_idx = (idx + 1) % len(self.postes_cycle)
            self.sim_state[truck.immatriculation] = {"index": next_idx}
            print(f"[CV-Sim] Restauré {truck.immatriculation} → étape {next_idx}")

    async def run_simulation_loop(self):
        """
        Boucle de simulation : chaque camion a sa propre coroutine indépendante.
        """
        print("[CV] Mode simulation activé — génération d'événements...")

        db = SessionLocal()
        try:
            self._restore_state_from_db(db)
        finally:
            db.close()

        tasks = [
            asyncio.create_task(self._simulate_truck(plaque))
            for plaque in self.plaques
        ]
        await asyncio.gather(*tasks)

    async def _simulate_truck(self, plaque: str):
        """Coroutine indépendante par camion simulé."""
        await asyncio.sleep(random.uniform(0, 30))

        if plaque not in self.sim_state:
            self.sim_state[plaque] = {"index": 0}

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

        while True:
            state = self.sim_state[plaque]
            idx   = state["index"]
            poste, type_event = self.postes_cycle[idx]

            await asyncio.sleep(step_delays[idx])

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
                    type_event=type_event,    # type: ignore
                    source="simulation",
                    confiance_ocr=round(random.uniform(0.75, 0.99), 2),
                )
                print(f"[CV-Sim] {plaque} | {poste.value} | {type_event}")
            except Exception as e:
                print(f"[CV-Sim] Erreur {plaque}: {e}")
            finally:
                db.close()

            self.sim_state[plaque]["index"] = (idx + 1) % len(self.postes_cycle)
