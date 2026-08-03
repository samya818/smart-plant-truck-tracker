"""
Modèles SQLAlchemy V2 — Bi-mode + Causes dynamiques.
Chaque poste a sa config de capture (caméra, agent, ou hybrid).
Les causes de retard sont créables à la volée.
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Boolean, Text, Enum
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class PosteType(str, enum.Enum):
    PORTE_USINE = "porte_usine"
    PARKING = "parking"
    BASCULE = "bascule"
    ENSACHAGE = "ensachage"


class CaptureMode(str, enum.Enum):
    CAMERA = "camera"
    AGENT = "agent"
    HYBRID = "hybrid"


class TruckStatus(str, enum.Enum):
    EN_COURS = "EN_COURS"
    TERMINE  = "TERMINE"
    ANOMALIE = "ANOMALIE"
    EXPIRE   = "EXPIRE"    # Cycle EN_COURS depuis trop longtemps → watchdog


# ============================================================
# Configuration par poste (bi-mode)
# ============================================================
class PosteConfig(Base):
    __tablename__ = "poste_configs"

    poste = Column(Enum(PosteType), primary_key=True)
    capture_mode = Column(Enum(CaptureMode), default=CaptureMode.CAMERA)
    camera_url = Column(String(255), nullable=True)
    camera_active = Column(Boolean, default=True)
    agent_pin = Column(String(10), nullable=True)
    qr_code_value = Column(String(100), nullable=True)
    seuil_attente_max = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# ============================================================
# Causes de retard dynamiques
# ============================================================
class DelayCause(Base):
    __tablename__ = "delay_causes"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    poste_concerne = Column(Enum(PosteType), nullable=True)
    usage_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_by = Column(String(50), default="system")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    events = relationship("Event", back_populates="cause")


class Transporteur(Base):
    __tablename__ = "transporteurs"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False)
    contact = Column(String(100))
    est_actif = Column(Boolean, default=True)
    est_whitelist = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    trucks = relationship("Truck", back_populates="transporteur")


class Truck(Base):
    __tablename__ = "trucks"
    id = Column(Integer, primary_key=True, index=True)
    immatriculation = Column(String(20), unique=True, index=True, nullable=False)
    transporteur_id = Column(Integer, ForeignKey("transporteurs.id"))
    type_camion = Column(String(50), default="standard")
    transporteur = relationship("Transporteur", back_populates="trucks")
    events = relationship("Event", back_populates="truck")
    cycles = relationship("Cycle", back_populates="truck")


class Event(Base):
    """
    Événement horodaté — créé soit par caméra, soit par agent mobile.
    La source est traçable pour l'audit.
    """
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    truck_id = Column(Integer, ForeignKey("trucks.id"), nullable=False)
    poste = Column(Enum(PosteType), nullable=False)
    type_event = Column(String(10), nullable=False)  # "entree" ou "sortie"
    horodatage = Column(DateTime(timezone=True), server_default=func.now())

    # --- SOURCE DE L'ÉVÉNEMENT (audit) ---
    source = Column(String(20), default="camera")   # "camera" | "agent_mobile" | "manuel" | "hybrid"
    agent_id = Column(String(50), nullable=True)

    # --- CAUSE DE RETARD (lien vers la table dynamique) ---
    delay_cause_id = Column(Integer, ForeignKey("delay_causes.id"), nullable=True)
    cause = relationship("DelayCause", back_populates="events")
    cause_retard_libre = Column(Text, nullable=True)
    minutes_retard = Column(Integer, nullable=True)

    # --- Métadonnées CV ---
    confiance_detection = Column(Float, nullable=True)
    confiance_ocr = Column(Float, nullable=True)
    necesita_confirmacion = Column(Boolean, default=False)
    image_path = Column(String(255), nullable=True)

    # --- Géolocalisation (si agent mobile) ---
    gps_lat = Column(Float, nullable=True)
    gps_lon = Column(Float, nullable=True)

    truck = relationship("Truck", back_populates="events")


class Cycle(Base):
    """
    Un cycle = parcours complet d'un camion (Porte -> ... -> Porte).
    """
    __tablename__ = "cycles"

    id = Column(Integer, primary_key=True, index=True)
    truck_id = Column(Integer, ForeignKey("trucks.id"), nullable=False)
    entree_porte = Column(DateTime(timezone=True), nullable=False)
    sortie_porte = Column(DateTime(timezone=True), nullable=True)
    duree_parking = Column(Float, default=0.0)
    duree_bascule_tare = Column(Float, default=0.0)
    duree_ensachage = Column(Float, default=0.0)
    duree_bascule_brut = Column(Float, default=0.0)
    duree_total = Column(Float, default=0.0)
    status = Column(Enum(TruckStatus), default=TruckStatus.EN_COURS)
    est_anomalie    = Column(Boolean, default=False)
    auto_closed     = Column(Boolean, default=False)   # fermé automatiquement par le système
    gap_applique    = Column(Float,   nullable=True)    # gap route appliqué (minutes)
    truck = relationship("Truck", back_populates="cycles")

    @property
    def immatriculation(self) -> str:
        """Permet de récupérer directement l'immatriculation pour le schéma CycleRead."""
        return self.truck.immatriculation if self.truck else ""


# ============================================================
# Étapes du processus — configurables par le superviseur
# ============================================================
class EtapeConfig(Base):
    """
    Configuration dynamique des étapes du processus camion.
    Le superviseur peut ajouter, renommer, ou désactiver des étapes.
    is_default=True : étape standard (ne peut pas être supprimée, seulement modifiée).
    is_custom=True  : étape ajoutée par le superviseur (peut être supprimée).
    """
    __tablename__ = "etape_configs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    ordre       = Column(Integer, nullable=False, default=0)          # ordre d'affichage
    code        = Column(String(50), unique=True, nullable=False)      # identifiant interne
    nom         = Column(String(100), nullable=False)                  # label affiché
    description = Column(String(255), nullable=True)                   # description courte
    seuil_minutes = Column(Integer, default=30, nullable=False)       # durée max (minutes)
    poste_ref   = Column(String(50), nullable=True)                   # lien optionnel à PosteType
    is_active   = Column(Boolean, default=True)
    is_default  = Column(Boolean, default=False)                      # étape système non supprimable
    is_custom   = Column(Boolean, default=False)                      # étape ajoutée par superviseur
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

