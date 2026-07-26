"""Router API pour les statistiques du dashboard."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Cycle, Event, TruckStatus, DelayCause
from app.schemas import DashboardStats
from app.services.anomaly_detector import AnomalyDetector

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db)):
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    camions_en_cours = db.query(Cycle).filter(Cycle.status == TruckStatus.EN_COURS).count()
    camions_aujourdhui = db.query(Cycle).filter(Cycle.entree_porte >= today).count()
    
    cycles_aujourdhui = db.query(Cycle).filter(
        Cycle.entree_porte >= today, 
        Cycle.status == TruckStatus.TERMINE
    ).all()
    
    temps_moyen = 0.0
    if cycles_aujourdhui:
        temps_moyen = sum(c.duree_total for c in cycles_aujourdhui) / len(cycles_aujourdhui)
        
    detector = AnomalyDetector(db)
    bloquant_info = detector.get_poste_bloquant()
    
    # Récupération dynamique de la cause principale de retard
    top_cause = db.query(DelayCause).filter(DelayCause.is_active == True).order_by(DelayCause.usage_count.desc()).first()
    top_cause_name = top_cause.nom if top_cause else "Aucun retard"
    
    return DashboardStats(
        camions_en_cours=camions_en_cours,
        camions_aujourdhui=camions_aujourdhui,
        temps_moyen_cycle=round(temps_moyen, 1),
        poste_bloquant=bloquant_info.get("poste_bloquant"),
        alertes_actives=db.query(Cycle).filter(Cycle.status == TruckStatus.EN_COURS, Cycle.est_anomalie == True).count(),
        top_cause_retard=top_cause_name
    )
