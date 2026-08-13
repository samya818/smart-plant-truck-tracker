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
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.database import SessionLocal
from app.models import Truck, Event, Cycle, PosteType, PosteConfig, CaptureMode
from app.services.event_ingestion import EventIngestionService

settings = get_settings()

# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTES PIPELINE RÉEL & SEUILS DE DÉCISION
# ──────────────────────────────────────────────────────────────────────────────
YOLO_CLASSES_VEHICULES   = {2, 5, 7}   # car, bus, truck (classes COCO — les camions bennes sont souvent étiquetés car/bus)
YOLO_CONFIDENCE_MIN      = 0.40        # seuil détection véhicule
OCR_ACCEPT_THRESHOLD     = 0.45        # seuil technique rejet EasyOCR (en-dessous = pur bruit)
HUMAN_REVIEW_THRESHOLD   = 0.65        # seuil confirmation humaine (0.45 <= conf < 0.65 -> nécessite validation agent)
FUZZY_MATCH_RATIO        = 0.85        # similarité minimale stricte (évite les faux rattachements)
AMBIGUITY_MARGIN         = 0.05        # écart minimal requis entre le 1er et le 2e candidat le plus proche
PLATE_EXPAND_PX          = 30          # pixels d'expansion autour du bbox pour la plaque
CAMERA_POLL_INTERVAL     = 2.0         # secondes entre deux captures par caméra
DEBOUNCE_SECONDS         = 30          # ne pas re-créer un event pour le même camion < 30s
MIN_DWELL_TIME_SECONDS   = 45          # durée minimale dans un poste pour valider une sortie physique

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS OCR
# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
# FORMATS DE PLAQUES PAR PAYS (configurable via PLATE_COUNTRY dans .env)
# ──────────────────────────────────────────────────────────────────────────────
# maroc   : 12345-أ-1  (1-5 chiffres — lettre arabe — 1-2 chiffres)
# algerie : 12345-123-16 (chiffres — chiffres — numéro wilaya 01-58)
# tunisie : 123TUN4567 ou 123 TN 4567
# france  : AA-123-AA   (lettre lettre — chiffres — lettre lettre)
# generique: tout texte alphanumérique de 4+ caractères
PLATE_PATTERNS: dict[str, list[str]] = {
    "maroc":    [r"^\d{1,5}-[\u0600-\u06FF]-\d{1,2}$", r"^\d{1,5}-[A-Z]-\d{1,2}$"],
    "algerie":  [r"^\d{4,6}-\d{1,4}-\d{2}$"],
    "tunisie":  [r"^\d{1,4}[A-Z]{2}\d{3,5}$", r"^\d{1,4}TUN\d{3,5}$"],
    "france":   [r"^[A-Z]{2}-\d{3}-[A-Z]{2}$"],
    "generique": [r"^[A-Z0-9\-]{4,15}$"],
}


def _normalize_plate(text: str) -> str:
    """
    Normalise une chaîne pour comparaison :
    - Conserve les lettres arabes telles quelles
    - Supprime les accents latins
    - Majuscules
    - Garde uniquement alphanumérique + tirets + lettres arabes
    """
    result = []
    for c in text:
        if '\u0600' <= c <= '\u06FF':
            result.append(c)
        else:
            normalized = unicodedata.normalize("NFKD", c)
            for nc in normalized:
                if not unicodedata.combining(nc):
                    result.append(nc.upper())
    text = "".join(result)
    text = re.sub(r"[^A-Z0-9\-\u0600-\u06FF]", "", text)
    return text


def _validate_plate_format(plate: str) -> bool:
    """
    Valide que la plaque normalisée correspond au format du pays configuré.
    Permissif : retourne True si aucun pattern ne correspond (pour gérer
    les cas de poussiere/occlusion partielle de plaque).
    """
    country = settings.plate_country.lower().strip()
    patterns = PLATE_PATTERNS.get(country, PLATE_PATTERNS["generique"])
    norm = _normalize_plate(plate)
    for pattern in patterns:
        if re.match(pattern, norm):
            return True
    return len(norm) >= 4  # permissif en cas d'OCR partielle


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


def _match_plate_in_db(ocr_text: str, db) -> Optional[Tuple[str, float, bool]]:
    """
    Compare le texte OCR avec toutes les immatriculations en DB.
    Retourne un tuple: (plaque_retenue, similarite, est_ambigu)
    - Rejette les correspondances si ratio < FUZZY_MATCH_RATIO (0.85)
    - Détecte l'ambiguïté si 2 camions ont une similarité très proche (écart < AMBIGUITY_MARGIN)
    """
    norm = _normalize_plate(ocr_text)
    if not norm or len(norm) < 4:
        return None

    # Validation du format selon le pays configuré
    if not _validate_plate_format(norm):
        print(f"[CV-OCR] Format non standard pour pays='{settings.plate_country}': '{norm}'")

    trucks = db.query(Truck).all()
    if not trucks:
        return (norm, 1.0, False)

    scored = []
    for truck in trucks:
        ratio = _similarity(norm, truck.immatriculation)
        scored.append((ratio, truck.immatriculation))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_ratio, best_plate = scored[0]

    # Vérification d'ambiguïté (ex: 2 plaques presque identiques)
    is_ambiguous = False
    if len(scored) > 1:
        second_ratio, second_plate = scored[1]
        if (best_ratio - second_ratio) < AMBIGUITY_MARGIN and best_ratio >= FUZZY_MATCH_RATIO:
            is_ambiguous = True
            print(f"[CV-OCR] ⚠️ Ambiguité détectée : 1er={best_plate}({best_ratio:.2f}) vs 2e={second_plate}({second_ratio:.2f})")

    if best_ratio >= FUZZY_MATCH_RATIO and best_plate:
        return (best_plate, best_ratio, is_ambiguous)

    # Camion inconnu mais texte OCR valide -> Création automatique en DB
    try:
        new_truck = Truck(immatriculation=norm)
        db.add(new_truck)
        db.commit()
        db.refresh(new_truck)
        print(f"[CV-OCR] 🆕 Nouveau camion enregistré en DB : {norm}")
        return (norm, 1.0, False)
    except Exception:
        db.rollback()
        return (norm, 1.0, False)


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
            "12345-أ-1", "67890-ب-2", "11111-د-3", "22222-و-4", "33333-ط-5",
            "44444-س-6", "55555-ه-7", "66666-ج-8", "77777-ح-9", "88888-خ-10",
            "99999-ر-11", "12346-ز-12", "23456-س-13", "34567-ش-14", "45678-ص-15",
            "56789-ض-16", "67891-ط-17", "78912-ظ-18", "89123-ع-19", "91234-غ-20",
            "13579-ف-21", "24680-ق-22", "35791-ك-23", "46802-ل-24", "57913-م-25",
            "68024-ن-26", "79135-ه-27", "80246-و-28", "91357-ي-29", "10247-أ-30",
            "21358-ب-31", "32469-د-32", "43570-ج-33", "54681-ح-34", "65792-خ-35"
        ]
        self.sim_state: dict[str, dict] = {}

    # ══════════════════════════════════════════════════════════════════════════
    # INITIALISATION LAZY DES MODÈLES (chargé une seule fois)
    # ══════════════════════════════════════════════════════════════════════════

    def _load_yolo(self):
        """Charge YOLOv8n en mémoire (lazy, une seule fois)."""
        if self._yolo_model is not None:
            return self._yolo_model
        import torch
        _orig_torch_load = torch.load
        def _safe_torch_load(*args, **kwargs):
            kwargs['weights_only'] = False
            return _orig_torch_load(*args, **kwargs)
        torch.load = _safe_torch_load
        try:
            from ultralytics import YOLO
            print("[CV] Chargement YOLOv8n...")
            self._yolo_model = YOLO("yolov8n.pt")
            print("[CV] YOLOv8n chargé ✓")
        finally:
            torch.load = _orig_torch_load
        return self._yolo_model

    def _load_ocr(self):
        """Charge EasyOCR en mémoire (lazy, une seule fois)."""
        if self._ocr_reader is not None:
            return self._ocr_reader
        import easyocr
        # Langues OCR selon le pays configuré
        _country_langs: dict[str, list[str]] = {
            "maroc":    ["ar", "en"],
            "algerie":  ["ar", "fr"],
            "tunisie":  ["ar", "fr"],
            "france":   ["fr"],
            "generique": ["ar", "en", "fr"],
        }
        country = settings.plate_country.lower()
        langs = _country_langs.get(country, ["ar", "en"])
        print(f"[CV] Chargement EasyOCR pour pays='{country}' → langues={langs}...")
        self._ocr_reader = easyocr.Reader(langs, gpu=False, verbose=False)
        print("[CV] EasyOCR chargé ✓")
        return self._ocr_reader

    # ══════════════════════════════════════════════════════════════════════════
    # PIPELINE RÉEL — capture + détection + OCR
    # ══════════════════════════════════════════════════════════════════════════

    def process_frame(self, frame, poste: PosteType, db, camera_direction: Optional[str] = None) -> Optional[dict]:
        """
        Pipeline complet sur un frame déjà capturé :
        1. YOLO → détecte les véhicules (classes COCO 2=car, 5=bus, 7=truck car les camions sont parfois étiquetés car/bus)
        2. EasyOCR → lit le texte dans chaque bbox détecté (multilingue)
        3. Fuzzy match durci → seuil 0.85 et alerte d'ambiguïté
        4. Direction caméra explicite ou automate d'états
        5. Debounce → évite les doublons < DEBOUNCE_SECONDS
        6. Ingestion → crée l'Event en DB de façon robuste
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

                if ocr_conf < OCR_ACCEPT_THRESHOLD:
                    print(f"[CV-OCR] Rejet technique : confiance trop faible ({ocr_conf:.2f} < {OCR_ACCEPT_THRESHOLD})")
                    continue

                # ── Fuzzy match DB durci ─────────────────────────────────────
                match_res = _match_plate_in_db(ocr_text, db)
                if not match_res:
                    print(f"[CV-OCR] Aucune plaque en DB correspondant à '{ocr_text}'")
                    continue
                matched_plate, match_score, is_ambiguous = match_res

                # ── Debounce anti-doublon ─────────────────────────────────────
                key = (poste, matched_plate)
                last = self._debounce.get(key)
                now  = datetime.utcnow()
                if last and (now - last).total_seconds() < DEBOUNCE_SECONDS:
                    print(f"[CV-OCR] Doublon ignoré ({matched_plate} @ {poste.value} — {(now-last).total_seconds():.0f}s)")
                    continue
                self._debounce[key] = now

                # ── Déduction type_event (Mapping explicite caméra ou Automate d'états) ──
                if camera_direction in ("entree", "sortie"):
                    type_event = camera_direction
                else:
                    type_event = self._infer_event_type(matched_plate, poste, db)

                # ── Sauvegarde frame annoté ───────────────────────────────────
                annotated = frame.copy()
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(annotated, f"{matched_plate} ({ocr_conf:.0%})",
                            (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                image_path = _save_frame(annotated, poste, matched_plate)

                # Si ambiguïté détectée, réduire artificiellement la confiance pour forcer la confirmation humaine
                adjusted_conf = round(ocr_conf * (0.60 if is_ambiguous else 1.0), 3)

                # ── Ingestion en DB ───────────────────────────────────────────
                try:
                    service = EventIngestionService(db)
                    event   = service.ingest_event(
                        plaque=matched_plate,
                        poste=poste,
                        type_event=type_event,
                        source="camera",
                        confiance_ocr=adjusted_conf,
                        image_path=image_path,
                    )
                    print(f"[CV] ✅ Event créé — {matched_plate} | {poste.value} | {type_event} | conf={adjusted_conf}")
                    best_result = {
                        "plaque": matched_plate,
                        "poste": poste.value,
                        "type_event": type_event,
                        "confiance_ocr": adjusted_conf,
                        "confiance_yolo": round(conf, 3),
                        "image_path": image_path,
                        "event_id": event.id,
                        "est_ambigu": is_ambiguous,
                    }
                except Exception as e:
                    print(f"[CV] Erreur ingestion {matched_plate}: {e}")

        return best_result

    def _infer_event_type(self, plaque: str, poste: PosteType, db) -> str:
        """
        Automate d'États Fini & Validation de Cohérence Physique :
        1. À la PORTE_USINE :
           - Pas de cycle EN_COURS -> "entree"
           - Cycle EN_COURS existant avec entrée > 5 min -> "sortie"
        2. Postes intermédiaires (Parking, Bascule, Ensachage) :
           - Pas d'entrée enregistrée -> "entree"
           - Entrée existante récente (< MIN_DWELL_TIME_SECONDS) -> Rejet ou "entree"
           - Entrée existante avec séjour légitime -> "sortie"
        """
        from app.models import TruckStatus
        truck = db.query(Truck).filter(Truck.immatriculation == plaque).first()
        if not truck:
            return "entree"

        now = datetime.utcnow()

        if poste == PosteType.PORTE_USINE:
            cycle = db.query(Cycle).filter(
                Cycle.truck_id == truck.id,
                Cycle.status   == TruckStatus.EN_COURS
            ).first()
            if not cycle:
                return "entree"
            # Si le camion vient juste d'entrer (< 2 min), ce n'est pas déjà une sortie usine
            dwell_porte = (now - cycle.entree_porte).total_seconds()
            return "sortie" if dwell_porte >= 120 else "entree"

        # Pour les postes intermédiaires
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
        ).order_by(Event.horodatage.desc()).first()

        if not entree_event:
            return "entree"

        # Si l'entrée date de moins de MIN_DWELL_TIME_SECONDS, éviter un faux flip
        dwell = (now - entree_event.horodatage).total_seconds()
        if dwell < MIN_DWELL_TIME_SECONDS:
            return "entree"

        return "sortie"

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
        # Le multiplier est chargé en premier pour calibrer le délai initial
        multiplier = max(1.0, float(settings.sim_speed_multiplier))

        # Décalage échelonné au démarrage : ≈15-40 min réelles entre chaque camion
        truck_num = sum(ord(c) for c in plaque) % 35
        initial_delay_min = truck_num * random.uniform(15, 40)  # minutes
        initial_delay_sec = max(2.0, (initial_delay_min * 60.0) / multiplier)
        await asyncio.sleep(initial_delay_sec)

        if plaque not in self.sim_state:
            self.sim_state[plaque] = {"index": 0}

        def _gen_delays_minutes():
            # Durées d'étape réalistes en minutes
            return [
                random.uniform(1, 3),    # 0. Porte entrée (1-3 min)
                random.uniform(12, 35),  # 1. Parking attente (12-35 min)
                random.uniform(1, 3),    # 2. Parking sortie (1-3 min)
                random.uniform(2, 5),    # 3. Bascule tare entrée (2-5 min)
                random.uniform(6, 18),   # 4. Bascule tare pesage (6-18 min)
                random.uniform(25, 52),  # 5. Ensachage chargement (25-52 min)
                random.uniform(2, 5),    # 6. Ensachage fin (2-5 min)
                random.uniform(6, 18),   # 7. Bascule brut retour (6-18 min)
                random.uniform(1, 3),    # 8. Bascule brut sortie (1-3 min)
                random.uniform(5, 12),   # 9. Porte sortie usine (5-12 min)
            ]

        step_delays_min = _gen_delays_minutes()

        # Cache des modes de capture par poste (recharger toutes les 5 min)
        poste_modes: dict[PosteType, CaptureMode] = {}
        modes_loaded_at: float = 0.0
        import time
        from datetime import timedelta

        while True:
            state = self.sim_state[plaque]
            idx   = state["index"]
            poste, type_event = self.postes_cycle[idx]

            delay_min = step_delays_min[idx]
            sleep_sec = max(1.0, (delay_min * 60.0) / multiplier)

            await asyncio.sleep(sleep_sec)

            # Horodatage réel actuel
            event_time = datetime.utcnow()

            if idx == len(self.postes_cycle) - 1:
                step_delays_min = _gen_delays_minutes()

            # ── Lecture du capture_mode depuis la DB (avec cache 5 min) ─────
            now_ts = time.monotonic()
            if now_ts - modes_loaded_at > 300:
                db_cfg = SessionLocal()
                try:
                    configs = db_cfg.query(PosteConfig).all()
                    poste_modes = {c.poste: c.capture_mode for c in configs}
                    modes_loaded_at = now_ts
                except Exception as e:
                    print(f"[CV-Sim] Impossible de lire PosteConfig: {e}")
                finally:
                    db_cfg.close()

            # ── capture_mode détermine si une confiance OCR est crédible ────
            mode = poste_modes.get(poste, CaptureMode.AGENT)
            if mode == CaptureMode.AGENT:
                confiance = None
                source_tag = "simulation_agent"
            else:
                confiance = round(random.uniform(0.75, 0.99), 2)
                source_tag = "simulation"

            db = SessionLocal()
            success = False
            try:
                # Si c'est un événement de SORTIE d'étape, ajuster l'événement d'ENTRÉE de cette étape
                # dans le passé (event_time - delay_min) pour que la durée enregistrée en DB soit exacte
                if type_event == "sortie":
                    last_entree = db.query(Event).join(Truck).filter(
                        Truck.immatriculation == plaque,
                        Event.poste == poste,
                        Event.type_event == "entree"
                    ).order_by(Event.horodatage.desc()).first()
                    if last_entree and (event_time - last_entree.horodatage).total_seconds() < 60:
                        last_entree.horodatage = event_time - timedelta(minutes=delay_min)
                        db.commit()

                service = EventIngestionService(db)
                service.ingest_event(
                    plaque=plaque,
                    poste=poste,
                    type_event=type_event,    # type: ignore
                    source=source_tag,
                    confiance_ocr=confiance,
                    horodatage=event_time,
                )
                print(
                    f"[CV-Sim] {plaque} | {poste.value} | {type_event} "
                    f"| mode={mode.value} | conf={confiance}"
                )
                success = True
            except Exception as e:
                print(
                    f"[CV-Sim] ⚠️  Échec {plaque} @ {poste.value}/{type_event}: {e} "
                    f"(index conservé à {idx})"
                )
            finally:
                db.close()

            if success:
                self.sim_state[plaque]["index"] = (idx + 1) % len(self.postes_cycle)
                # Quand le camion termine tout le cycle (sortie usine), faire une pause de repos
                if idx == len(self.postes_cycle) - 1:
                    # Pause entre deux passages : 1-3h en temps réel, proportionnel au multiplicateur
                    rest_time_min = random.uniform(60, 180)  # minutes
                    rest_time_sec = max(5.0, (rest_time_min * 60.0) / multiplier)
                    await asyncio.sleep(rest_time_sec)
