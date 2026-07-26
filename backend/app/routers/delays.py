"""Router API pour la gestion des retards."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import DelayCause
from app.schemas import DelayCauseRead

router = APIRouter(prefix="/api/delays", tags=["Retards"])

@router.get("/", response_model=List[DelayCauseRead])
def get_delays(db: Session = Depends(get_db)):
    return db.query(DelayCause).filter(DelayCause.is_active == True).all()
