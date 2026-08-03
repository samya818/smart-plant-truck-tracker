from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.config import Settings, get_settings
from app.models import Cycle, Event, Truck, PosteType

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.post("/disable-simulation")
async def disable_simulation(settings: Settings = Depends(get_settings)):
    """Switch application from simulation mode to real mode and persist the change."""
    if settings.cv_mode == "real":
        return {"message": "Simulation already disabled (mode is real)."}
    try:
        with open(".env", "a", encoding="utf-8") as f:
            f.write("\nCV_MODE=real\n")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write .env: {e}")
    get_settings.cache_clear()
    return {"message": "Simulation disabled – application now runs in real mode."}

@router.post("/clean-database")
async def clean_database(db: Session = Depends(get_db)):
    """Remove all runtime data (cycles, events, trucks) while keeping reference tables.
    Used when delivering the system to the Lafarge plant to clear test data.
    """
    try:
        db.query(Cycle).delete()
        db.query(Event).delete()
        db.query(Truck).delete()
        db.commit()
        return {"message": "Database cleaned – cycles, events and trucks removed."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database clean failed: {e}")


@router.post("/ocr-test")
async def test_ocr(
    image: UploadFile = File(...),
    poste: PosteType = Form(default=PosteType.PORTE_USINE),
    db: Session = Depends(get_db),
):
    """
    Endpoint de test OCR : envoie une image, retourne la plaque détectée,
    la confiance YOLO et la confiance OCR.
    N'ingère PAS d'événement en DB — test uniquement.
    """
    from app.services.cv_service import CVService, _normalize_plate, _match_plate_in_db, _similarity

    contents = await image.read()
    if not contents:
        raise HTTPException(400, "Image vide")

    try:
        import cv2
        import numpy as np

        nparr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(422, "Impossible de décoder l'image (format non supporté)")

        cv = CVService()
        model  = cv._load_yolo()
        reader = cv._load_ocr()

        h, w = frame.shape[:2]
        results_yolo = model(frame, verbose=False)

        detections = []
        all_ocr    = []

        for r in results_yolo:
            for box in r.boxes:
                cls  = int(box.cls[0])
                conf = float(box.conf[0])
                if cls not in {2, 5, 7}:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                roi = frame[max(0, y1-30):min(h, y2+30), max(0, x1-30):min(w, x2+30)]
                if roi.size == 0:
                    continue

                gray     = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                clahe    = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                enhanced = clahe.apply(gray)
                upscaled = cv2.resize(enhanced, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

                ocr_results = reader.readtext(upscaled, detail=1)
                for (_, text, ocr_conf) in ocr_results:
                    matched = _match_plate_in_db(text, db)
                    all_ocr.append({
                        "texte_brut": text,
                        "texte_normalise": _normalize_plate(text),
                        "confiance_ocr": round(ocr_conf, 3),
                        "plaque_matchee": matched,
                        "confiance_yolo": round(conf, 3),
                        "bbox": [x1, y1, x2, y2],
                    })
                detections.append({"bbox": [x1, y1, x2, y2], "conf_yolo": round(conf, 3)})

        best = max(all_ocr, key=lambda x: x["confiance_ocr"], default=None) if all_ocr else None

        return {
            "nb_vehicules_detectes": len(detections),
            "nb_textes_lus": len(all_ocr),
            "meilleur_resultat": best,
            "tous_les_resultats": all_ocr,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=f"Erreur OCR : {str(e)}")

