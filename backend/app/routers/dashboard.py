"""Router API pour les statistiques du dashboard."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from datetime import datetime, timedelta, timezone
from typing import Dict
from pydantic import BaseModel

from app.database import get_db
from app.models import Cycle, Event, TruckStatus, DelayCause, PosteType, PosteConfig, EtapeConfig
from app.schemas import DashboardStats
from app.services.anomaly_detector import AnomalyDetector
from app.services.event_ingestion import EventIngestionService

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


# ── Schémas Seuils ───────────────────────────────────────────────────────────
class SeuilsPayload(BaseModel):
    parking: int       # minutes max autorisées au parking
    bascule_tare: int  # minutes max pour la pesée à vide
    ensachage: int     # minutes max pour le chargement
    bascule_brut: int  # minutes max pour la pesée chargé
    cycle_total: int   # durée totale max autorisée (entrée → sortie)


POSTE_TO_FIELD = {
    PosteType.PARKING:    "parking",
    PosteType.BASCULE:    "bascule_tare",
    PosteType.ENSACHAGE:  "ensachage",
    PosteType.PORTE_USINE: "cycle_total",
}


@router.get("/seuils")
def get_seuils(db: Session = Depends(get_db)):
    """
    Retourne les seuils de durée configurés par le superviseur pour chaque zone.
    Fallback sur les valeurs de config si la DB ne les a pas encore.
    """
    from app.config import get_settings
    cfg = get_settings()

    configs = {c.poste: c for c in db.query(PosteConfig).all()}

    def seuil(poste: PosteType, default: int) -> int:
        c = configs.get(poste)
        return c.seuil_attente_max if c else default

    return {
        "parking":     seuil(PosteType.PARKING,    cfg.seuil_attente_parking_max),
        "bascule_tare": seuil(PosteType.BASCULE,   cfg.seuil_bascule_max),
        "ensachage":   seuil(PosteType.ENSACHAGE,  cfg.seuil_ensachage_max),
        "bascule_brut": seuil(PosteType.BASCULE,   cfg.seuil_bascule_max),
        "cycle_total": seuil(PosteType.PORTE_USINE, cfg.seuil_cycle_total_max),
    }


@router.put("/seuils")
def update_seuils(payload: SeuilsPayload, db: Session = Depends(get_db)):
    """
    Met à jour les seuils de durée par zone.
    Persiste en base dans la table poste_configs.
    """
    updates = {
        PosteType.PARKING:     payload.parking,
        PosteType.BASCULE:     payload.bascule_tare,
        PosteType.ENSACHAGE:   payload.ensachage,
        PosteType.PORTE_USINE: payload.cycle_total,
    }
    for poste, valeur in updates.items():
        cfg = db.query(PosteConfig).filter(PosteConfig.poste == poste).first()
        if cfg:
            cfg.seuil_attente_max = valeur
        else:
            db.add(PosteConfig(poste=poste, seuil_attente_max=valeur))
    db.commit()
    return {"status": "ok", "message": "Seuils mis à jour avec succès", "seuils": payload.dict()}


@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db)):
    """
    KPIs calculés depuis la table EVENTS (même source que le frontend).
    Garantit la cohérence avec ce que l'utilisateur voit dans l'interface.
    """
    # Fuseau horaire Maroc (UTC+1)
    tz_maroc = timezone(timedelta(hours=1))
    now_maroc = datetime.now(tz=tz_maroc)
    today_utc = now_maroc.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
    depuis_24h = datetime.utcnow() - timedelta(hours=24)

    # ── Camions en cours ──────────────────────────────────────────────────────
    # Source de vérité : table cycles (status = EN_COURS, entree_porte < 24h)
    # Identique à la logique de /api/events/active pour garantir la cohérence
    camions_en_cours = db.query(func.count(distinct(Cycle.truck_id))).filter(
        Cycle.status == TruckStatus.EN_COURS,
        Cycle.entree_porte >= depuis_24h
    ).scalar() or 0

    # ── Aujourd'hui ───────────────────────────────────────────────────────────
    # Nombre de trucks DISTINCTS ayant eu au moins un événement aujourd'hui
    camions_aujourdhui = db.query(func.count(distinct(Event.truck_id))).filter(
        Event.horodatage >= today_utc
    ).scalar() or 0

    # ── Temps moyen cycle ─────────────────────────────────────────────────────
    # Depuis les cycles TERMINÉS récents (derniers 7 jours) avec duree_total > 0
    sept_jours = datetime.utcnow() - timedelta(days=7)
    cycles_termines = db.query(Cycle).filter(
        Cycle.status == TruckStatus.TERMINE,
        Cycle.entree_porte >= sept_jours,
        Cycle.duree_total > 0
    ).all()
    temps_moyen = (
        sum(c.duree_total for c in cycles_termines) / len(cycles_termines)
        if cycles_termines else 0.0
    )

    # ── Alertes actives ───────────────────────────────────────────────────────
    # Cycles EN_COURS dont l'entrée porte dépasse le seuil max configuré
    from app.config import get_settings
    settings = get_settings()
    seuil_alerte = datetime.utcnow() - timedelta(minutes=settings.seuil_cycle_total_max)

    alertes = db.query(func.count(distinct(Cycle.truck_id))).filter(
        Cycle.status == TruckStatus.EN_COURS,
        Cycle.entree_porte >= depuis_24h,
        Cycle.entree_porte <= seuil_alerte
    ).scalar() or 0

    # ── Poste bloquant & cause de retard ──────────────────────────────────────
    detector = AnomalyDetector(db)
    bloquant_info = detector.get_poste_bloquant()

    top_cause = db.query(DelayCause).filter(
        DelayCause.is_active == True
    ).order_by(DelayCause.usage_count.desc()).first()
    top_cause_name = top_cause.nom if top_cause else None

    return DashboardStats(
        camions_en_cours=camions_en_cours,
        camions_aujourdhui=camions_aujourdhui,
        temps_moyen_cycle=round(temps_moyen, 1),
        poste_bloquant=bloquant_info.get("poste_bloquant"),
        alertes_actives=alertes,
        top_cause_retard=top_cause_name
    )


# ── Schémas Étapes ────────────────────────────────────────────────────────────
from app.models import EtapeConfig

class EtapeCreate(BaseModel):
    nom: str
    description: str = ""
    seuil_minutes: int = 30
    ordre: int = 99

class EtapeUpdate(BaseModel):
    nom: str | None = None
    description: str | None = None
    seuil_minutes: int | None = None
    ordre: int | None = None
    is_active: bool | None = None


@router.get("/etapes")
def list_etapes(db: Session = Depends(get_db)):
    """Retourne toutes les étapes triées par ordre d'affichage."""
    etapes = db.query(EtapeConfig).order_by(EtapeConfig.ordre).all()
    return [
        {
            "id":             e.id,
            "ordre":          e.ordre,
            "code":           e.code,
            "nom":            e.nom,
            "description":    e.description,
            "seuil_minutes":  e.seuil_minutes,
            "poste_ref":      e.poste_ref,
            "is_active":      e.is_active,
            "is_default":     e.is_default,
            "is_custom":      e.is_custom,
        }
        for e in etapes
    ]


@router.post("/etapes", status_code=201)
def create_etape(payload: EtapeCreate, db: Session = Depends(get_db)):
    """Crée une nouvelle étape personnalisée (superviseur)."""
    import re, uuid
    code = "custom_" + re.sub(r"[^a-z0-9]", "_", payload.nom.lower())[:30] + "_" + uuid.uuid4().hex[:4]
    etape = EtapeConfig(
        ordre=payload.ordre,
        code=code,
        nom=payload.nom,
        description=payload.description,
        seuil_minutes=payload.seuil_minutes,
        is_default=False,
        is_custom=True,
    )
    db.add(etape)
    db.commit()
    db.refresh(etape)
    return {"id": etape.id, "code": etape.code, "nom": etape.nom,
            "seuil_minutes": etape.seuil_minutes, "is_custom": True}


@router.put("/etapes/{etape_id}")
def update_etape(etape_id: int, payload: EtapeUpdate, db: Session = Depends(get_db)):
    """Met à jour une étape (nom, description, seuil, ordre). Toutes les étapes sont modifiables."""
    etape = db.query(EtapeConfig).filter(EtapeConfig.id == etape_id).first()
    if not etape:
        raise HTTPException(status_code=404, detail="Étape introuvable")
    if payload.nom is not None:          etape.nom = payload.nom
    if payload.description is not None:  etape.description = payload.description
    if payload.seuil_minutes is not None: etape.seuil_minutes = payload.seuil_minutes
    if payload.ordre is not None:        etape.ordre = payload.ordre
    if payload.is_active is not None:    etape.is_active = payload.is_active
    db.commit()
    return {"status": "ok", "id": etape.id, "nom": etape.nom, "seuil_minutes": etape.seuil_minutes}


@router.delete("/etapes/{etape_id}")
def delete_etape(etape_id: int, db: Session = Depends(get_db)):
    """Supprime une étape personnalisée. Les étapes par défaut sont protégées."""
    etape = db.query(EtapeConfig).filter(EtapeConfig.id == etape_id).first()
    if not etape:
        raise HTTPException(status_code=404, detail="Étape introuvable")
    if etape.is_default:
        raise HTTPException(status_code=403, detail="Les étapes par défaut ne peuvent pas être supprimées")
    db.delete(etape)
    db.commit()
    return {"status": "ok", "message": f"Étape '{etape.nom}' supprimée"}


# ═══════════════════════════════════════════════════════════════════════════
# ANOMALIES & WATCHDOG
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/anomalies")
def get_anomalies(db: Session = Depends(get_db)):
    """
    Rapport des situations anormales :
    - Cycles EN_COURS depuis plus de 4h (camions bloqués)
    - Cycles fermés automatiquement (auto-closed)
    - Cycles EXPIRE (watchdog)
    """
    return EventIngestionService.get_anomalies(db)


@router.post("/watchdog")
def run_watchdog(db: Session = Depends(get_db)):
    """
    Déclenche manuellement le watchdog.
    Marque EXPIRE tout cycle EN_COURS depuis plus de 8h.
    Appelé aussi automatiquement au démarrage via APScheduler.
    """
    count = EventIngestionService.run_watchdog(db)
    return {"status": "ok", "cycles_expires": count, "message": f"{count} cycle(s) marqué(s) EXPIRE"}
