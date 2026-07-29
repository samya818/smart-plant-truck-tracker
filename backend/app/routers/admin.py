from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import Settings, get_settings
from app.models import Cycle, Event, Truck

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
