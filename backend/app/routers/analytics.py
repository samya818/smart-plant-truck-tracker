"""Router API pour les analyses historiques et prédictions."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.database import get_db
from app.models import Cycle
from app.schemas import CycleRead

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

@router.get("/cycles", response_model=List[CycleRead])
def list_cycles(db: Session = Depends(get_db)):
    """Retourne l'historique des cycles de camions avec eager loading pour éviter le problème N+1."""
    return db.query(Cycle).options(joinedload(Cycle.truck)).order_by(Cycle.entree_porte.desc()).limit(100).all()
