"""Router API pour la gestion des événements."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Event, Cycle, TruckStatus
from app.schemas import EventRead

router = APIRouter(prefix="/api/events", tags=["Événements"])


@router.get("/active", response_model=List[EventRead])
def list_active_events(db: Session = Depends(get_db)):
    """
    Retourne les événements des camions dont le cycle est EN_COURS.
    Source de vérité : table cycles (status = EN_COURS).
    Uniquement les cycles ouverts dans les dernières 24h.
    """
    since = datetime.utcnow() - timedelta(hours=24)

    # Récupérer les truck_id qui ont un cycle EN_COURS
    cycles_en_cours = db.query(Cycle).filter(
        Cycle.status == TruckStatus.EN_COURS,
        Cycle.entree_porte >= since
    ).all()

    if not cycles_en_cours:
        return []

    # Construire les filtres pour chaque cycle actif (truck_id et horodatage >= entree_porte)
    from sqlalchemy import or_, and_
    conditions = [
        and_(Event.truck_id == c.truck_id, Event.horodatage >= (c.entree_porte.replace(tzinfo=None) if c.entree_porte.tzinfo else c.entree_porte))
        for c in cycles_en_cours
    ]

    events = (
        db.query(Event)
        .options(joinedload(Event.truck))
        .filter(or_(*conditions))
        .order_by(Event.horodatage.desc())
        .all()
    )

    return events
