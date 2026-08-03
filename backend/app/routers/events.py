"""Router API pour la gestion des événements."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.models import Event, Cycle, Truck, TruckStatus
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


# ═══════════════════════════════════════════════════════════════════════════
# CIRCUIT DE CONFIRMATION OCR FAIBLE CONFIANCE
# ═══════════════════════════════════════════════════════════════════════════

class ConfirmPayload(BaseModel):
    """Payload pour confirmer ou corriger un event OCR douteux."""
    plaque_corrigee: Optional[str] = None  # Si None → plaque originale confirmée

class RejectPayload(BaseModel):
    """Payload pour rejeter un event (fausse détection)."""
    raison: Optional[str] = None


@router.get("/pending-confirmation", response_model=List[EventRead])
def list_pending_confirmation(db: Session = Depends(get_db)):
    """
    Retourne tous les events OCR en attente de confirmation humaine.
    Ces events ont été créés avec confiance_ocr entre 0.45 et 0.65 —
    assez hauts pour créer un event, mais trop bas pour être fiables
    sans vérification d'un agent.
    """
    events = (
        db.query(Event)
        .options(joinedload(Event.truck), joinedload(Event.cause))
        .filter(Event.necesita_confirmacion == True)
        .order_by(Event.horodatage.desc())
        .limit(50)
        .all()
    )
    return events


@router.get("/pending-confirmation/count")
def count_pending_confirmation(db: Session = Depends(get_db)):
    """Retourne le nombre d'events en attente. Utilisé par le badge nav."""
    count = db.query(Event).filter(Event.necesita_confirmacion == True).count()
    return {"count": count}


@router.patch("/{event_id}/confirm")
def confirm_event(
    event_id: int,
    payload: ConfirmPayload,
    db: Session = Depends(get_db)
):
    """
    Confirme un event OCR douteux.
    - Si plaque_corrigee est fourni : met à jour la plaque du camion lié
    - Marque necesita_confirmacion = False
    - Horodate la confirmation
    """
    event = db.query(Event).options(joinedload(Event.truck)).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, f"Event {event_id} introuvable")
    if not event.necesita_confirmacion:
        raise HTTPException(400, "Cet event ne nécessite pas de confirmation")

    # Correction de plaque si demandée
    if payload.plaque_corrigee and event.truck:
        old_plate = event.truck.immatriculation
        norm = payload.plaque_corrigee.upper().replace(" ", "")
        # Vérifier qu'un autre camion n'a pas déjà cette immatriculation
        existing = db.query(Truck).filter(
            Truck.immatriculation == norm,
            Truck.id != event.truck_id
        ).first()
        if not existing:
            event.truck.immatriculation = norm
            print(f"[Confirmation] Plaque corrigée : {old_plate} → {norm}")

    # Marquer comme confirmé
    event.necesita_confirmacion = False
    event.source = "confirmed_" + event.source  # trace d'audit
    db.commit()

    return {
        "status": "confirmed",
        "event_id": event_id,
        "plaque": event.truck.immatriculation if event.truck else None
    }


@router.patch("/{event_id}/reject")
def reject_event(
    event_id: int,
    payload: RejectPayload,
    db: Session = Depends(get_db)
):
    """
    Rejette un event OCR comme fausse détection.
    L'event est supprimé de la DB et si un cycle est impacté, ses durées sont recalculées.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, f"Event {event_id} introuvable")
    if not event.necesita_confirmacion:
        raise HTTPException(400, "Cet event ne nécessite pas de confirmation")

    raison = payload.raison or "Fausse détection OCR"
    truck_id = event.truck_id
    horodatage = event.horodatage

    # Trouver le cycle actif ou correspondant à cet événement
    cycle = db.query(Cycle).filter(
        Cycle.truck_id == truck_id,
        Cycle.entree_porte <= horodatage
    ).order_by(Cycle.entree_porte.desc()).first()

    # Supprimer l'événement
    print(f"[Rejet] Event {event_id} rejeté — {raison}")
    db.delete(event)
    db.commit()

    # Recalculer les durées du cycle si un cycle existait
    if cycle:
        from app.services.event_ingestion import EventIngestionService
        service = EventIngestionService(db)
        service._recalculate_durations(cycle)
        db.commit()

    return {"status": "rejected", "event_id": event_id, "raison": raison}
