"""Router API pour l'agent mobile et les causes de retard dynamiques."""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.models import DelayCause, PosteType, PosteConfig, CaptureMode
from app.schemas import DelayCauseCreate, DelayCauseRead, PosteConfigRead, PosteConfigUpdate
from app.services.event_ingestion import EventIngestionService

router = APIRouter(prefix="/api/mobile", tags=["Mobile & Causes"])


# ============================================================
# CAUSES DE RETARD DYNAMIQUES
# ============================================================
@router.get("/delay-causes", response_model=List[DelayCauseRead])
def list_causes(
    poste: Optional[PosteType] = None,
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """
    Retourne les causes de retard, triées par fréquence d'utilisation.
    Si 'poste' est fourni, filtre les causes pertinentes pour ce poste.
    """
    query = db.query(DelayCause)
    if active_only:
        query = query.filter(DelayCause.is_active == True)
    if poste:
        query = query.filter(
            (DelayCause.poste_concerne == poste) | (DelayCause.poste_concerne == None)
        )
    return query.order_by(DelayCause.usage_count.desc()).all()


@router.post("/delay-causes", response_model=DelayCauseRead)
def create_cause(cause: DelayCauseCreate, db: Session = Depends(get_db)):
    """Crée une nouvelle cause de retard à la volée."""
    existing = db.query(DelayCause).filter(DelayCause.nom.ilike(cause.nom)).first()
    if existing:
        return existing

    db_cause = DelayCause(**cause.dict())
    db.add(db_cause)
    db.commit()
    db.refresh(db_cause)
    return db_cause


@router.patch("/delay-causes/{cause_id}/deactivate")
def deactivate_cause(cause_id: int, db: Session = Depends(get_db)):
    cause = db.query(DelayCause).get(cause_id)
    if not cause:
        raise HTTPException(404, "Cause non trouvée")
    cause.is_active = False
    db.commit()
    return {"status": "deactivated"}


# ============================================================
# INGESTION MOBILE (Agent scanne avec téléphone)
# ============================================================
@router.post("/events")
async def create_event_mobile(
    plaque: str = Form(...),
    poste: PosteType = Form(...),
    type_event: str = Form(..., pattern="^(entree|sortie)$"),
    agent_id: str = Form(...),
    client_event_id: Optional[str] = Form(None),
    delay_cause_id: Optional[int] = Form(None),
    minutes_retard: Optional[int] = Form(None),
    gps_lat: Optional[float] = Form(None),
    gps_lon: Optional[float] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Point d'entrée pour l'agent mobile.
    Si une photo est fournie, OCR tente de lire la plaque automatiquement.
    La plaque OCR est utilisée si elle est reconnue en DB, sinon la plaque saisie manuellement est conservée.
    """
    config = db.query(PosteConfig).filter(PosteConfig.poste == poste).first()
    if config and config.capture_mode == CaptureMode.CAMERA:
        raise HTTPException(400, f"Poste {poste.value} en mode caméra uniquement")

    image_path = None
    confiance_ocr = None
    plaque_finale = plaque

    if photo:
        import os
        from app.config import get_settings
        from app.services.cv_service import CVService
        settings = get_settings()
        os.makedirs(settings.upload_dir, exist_ok=True)

        contents = await photo.read()
        file_path = os.path.join(settings.upload_dir, photo.filename)
        with open(file_path, "wb") as f:
            f.write(contents)
        image_path = f"/uploads/{photo.filename}"

        # ── Tentative OCR sur la photo ───────────────────────────────────────
        try:
            cv = CVService()
            ocr_result = cv.process_uploaded_image(contents, poste, db)
            if ocr_result:
                plaque_finale = ocr_result["plaque"]
                confiance_ocr = ocr_result["confiance_ocr"]
                # Si OCR a créé l'event directement, on retourne son résultat
                return {
                    "id": ocr_result["event_id"],
                    "plaque": plaque_finale,
                    "poste": poste.value,
                    "type_event": ocr_result["type_event"],
                    "confiance_ocr": confiance_ocr,
                    "source": "hybrid",
                    "image_path": image_path,
                    "ocr_auto": True,
                }
        except Exception as e:
            print(f"[Mobile] OCR optionnel échoué, plaque manuelle conservée: {e}")

    service = EventIngestionService(db)
    event = service.ingest_event(
        plaque=plaque_finale,
        poste=poste,
        type_event=type_event,  # type: ignore
        source="agent_mobile",
        agent_id=agent_id,
        image_path=image_path,
        confiance_ocr=confiance_ocr,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        delay_cause_id=delay_cause_id,
        minutes_retard=minutes_retard,
        client_event_id=client_event_id,
    )
    return event


# ============================================================
# CONFIG POSTES (Admin)
# ============================================================
@router.get("/poste-configs", response_model=List[PosteConfigRead])
def list_poste_configs(db: Session = Depends(get_db)):
    return db.query(PosteConfig).all()


@router.put("/poste-configs/{poste}", response_model=PosteConfigRead)
def update_poste_config(
    poste: PosteType,
    config_update: PosteConfigUpdate,
    db: Session = Depends(get_db)
):
    """
    Permet de changer le mode d'un poste à chaud via un corps JSON.
    Ex: la bascule passe de CAMERA à HYBRID si la caméra tombe en panne.
    """
    config = db.query(PosteConfig).filter(PosteConfig.poste == poste).first()
    if not config:
        config = PosteConfig(poste=poste)
        db.add(config)

    config.capture_mode = config_update.capture_mode
    if config_update.camera_url is not None:
        config.camera_url = config_update.camera_url
    if config_update.agent_pin is not None:
        config.agent_pin = config_update.agent_pin

    db.commit()
    db.refresh(config)
    return config
