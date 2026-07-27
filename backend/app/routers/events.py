"""Router API pour la gestion des événements."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Event
from app.schemas import EventRead

router = APIRouter(prefix="/api/events", tags=["Événements"])

@router.get("/active", response_model=List[EventRead])
def list_active_events(db: Session = Depends(get_db)):
    """Retourne les événements récents des dernières 48 heures."""
    since = datetime.utcnow() - timedelta(hours=48)
    return db.query(Event).options(joinedload(Event.truck)).filter(Event.horodatage >= since).order_by(Event.horodatage.desc()).all()

