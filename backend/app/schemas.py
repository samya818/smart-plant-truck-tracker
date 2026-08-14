"""
Schémas Pydantic — Validation et sérialisation API.
Séparation stricte Create / Read / Update.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from app.models import PosteType, TruckStatus, CaptureMode


class TransporteurBase(BaseModel):
    nom: str = Field(..., min_length=2, max_length=100)
    contact: Optional[str] = None
    est_whitelist: bool = False

class TransporteurCreate(TransporteurBase):
    pass

class TransporteurRead(TransporteurBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True


class TruckBase(BaseModel):
    immatriculation: str = Field(..., pattern=r"^[\w\u0600-\u06FF-]+$", max_length=20)
    type_camion: str = "standard"

class TruckCreate(TruckBase):
    transporteur_id: Optional[int] = None

class TruckRead(TruckBase):
    id: int
    transporteur: Optional[TransporteurRead] = None
    class Config:
        from_attributes = True


class DelayCauseBase(BaseModel):
    nom: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    poste_concerne: Optional[PosteType] = None

class DelayCauseCreate(DelayCauseBase):
    created_by: str = "system"

class DelayCauseRead(DelayCauseBase):
    id: int
    usage_count: int
    is_active: bool
    created_by: str
    created_at: datetime
    class Config:
        from_attributes = True


class PosteConfigRead(BaseModel):
    poste: PosteType
    capture_mode: CaptureMode
    camera_url: Optional[str] = None
    camera_active: bool
    agent_pin: Optional[str] = None
    seuil_attente_max: int
    is_active: bool
    class Config:
        from_attributes = True


class PosteConfigUpdate(BaseModel):
    capture_mode: CaptureMode
    camera_url: Optional[str] = None
    agent_pin: Optional[str] = None


class EventBase(BaseModel):
    poste: PosteType
    type_event: str = Field(..., pattern=r"^(entree|sortie)$")

class EventCreate(EventBase):
    truck_id: int
    cause_retard: Optional[str] = None

class EventRead(EventBase):
    id: int
    client_event_id: Optional[str] = None
    truck_id: int
    horodatage: datetime
    received_at: Optional[datetime] = None
    sync_status: Optional[str] = "realtime"
    source: str
    agent_id: Optional[str] = None
    confiance_detection: Optional[float] = None
    confiance_ocr: Optional[float] = None
    necesita_confirmacion: bool = False
    cause: Optional[DelayCauseRead] = None
    minutes_retard: Optional[int] = None
    image_path: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    gps_accuracy_m: Optional[float] = None
    cycle_id: Optional[int] = None
    truck: Optional[TruckRead] = None
    class Config:
        from_attributes = True


class CycleRead(BaseModel):
    id: int
    truck_id: int
    immatriculation: str
    entree_porte: datetime
    sortie_porte: Optional[datetime] = None
    duree_total: float
    duree_parking: float
    duree_ensachage: float
    status: TruckStatus
    est_anomalie: bool
    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    camions_en_cours: int
    camions_aujourdhui: int
    temps_moyen_cycle: float
    poste_bloquant: Optional[str] = None
    alertes_actives: int
    top_cause_retard: Optional[str] = None


class PredictionETA(BaseModel):
    truck_id: int
    immatriculation: str
    poste_actuel: PosteType
    eta_sortie_minutes: float
    niveau_confiance: str  # "faible", "moyenne", "élevée"
    methode: str           # "regles_metier", "ewma", "prophet", "xgboost_experimental"
