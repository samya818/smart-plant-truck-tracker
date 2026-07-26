"""Router API pour la gestion des camions."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Truck
from app.schemas import TruckRead, TruckCreate

router = APIRouter(prefix="/api/trucks", tags=["Camions"])

@router.get("/", response_model=List[TruckRead])
def list_trucks(db: Session = Depends(get_db)):
    return db.query(Truck).all()

@router.post("/", response_model=TruckRead)
def create_truck(truck: TruckCreate, db: Session = Depends(get_db)):
    existing = db.query(Truck).filter(Truck.immatriculation == truck.immatriculation.upper()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Camion déjà enregistré")
    db_truck = Truck(immatriculation=truck.immatriculation.upper(), transporteur_id=truck.transporteur_id)
    db.add(db_truck)
    db.commit()
    db.refresh(db_truck)
    return db_truck
