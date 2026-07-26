# 🏭 LafargeHolcim Meknès — Camion Tracker V2
## Projet de Stage IA & Data Science — Traçabilité & Optimisation des Flux Camions

> **Philosophie** : Système opérationnel **jour 1 sans aucune donnée réelle**, qui s'améliore automatiquement via une architecture "Zero-to-Hero".
> 
> **Nouveauté V2** : Bi-mode Caméra/Agent Mobile + Causes de retard dynamiques + ML simplifié et pragmatique.

---

## 📋 Table des matières

1. [Stratégie IA & Données](#stratégie-ia--données)
2. [Architecture des dossiers](#architecture-des-dossiers)
3. [Fichiers de configuration](#fichiers-de-configuration)
4. [Backend FastAPI](#backend-fastapi)
5. [Services Backend](#-services-backend)
6. [Routers API Backend](#-routers-api-backend)
7. [Simulation & Génération de données](#simulation--génération-de-données)
8. [Pipeline d'entraînement automatique](#pipeline-dentraînement-automatique)
9. [Frontend React](#frontend-react)
10. [Docker & Déploiement](#docker--déploiement)
11. [Guide d'installation pas à pas](#guide-dinstallation-pas-à-pas)
12. [PWA Agent Mobile](#pwa-agent-mobile)

---

## 🧠 Stratégie IA & Données

### Le problème : Tu pars avant d'avoir des données

Tu ne verras pas le système tourner 1 mois en production. Il faut donc :
1. **Simuler** un historique crédible dès le départ
2. **Coder** des modèles sans poids qui fonctionnent à 0 donnée
3. **Automatiser** le passage au ML avancé pour après ton départ

### Les 3 niveaux du système (simplifiés et pragmatiques)

| Niveau | Nom | Technique | Données | Actif dès |
|--------|-----|-----------|---------|-----------|
| **0** | Règles métier + Simulation | Seuils configurables, distributions empiriques | 0 | Jour 1 |
| **1** | Statistique adaptative | EWMA, Z-score dynamique | ~30 cycles | Semaine 2 |
| **2** | Prophet (production) | Saisonnalité journalière, intervalles de confiance | ~200 cycles | Auto après 3 semaines |
| **2b** | XGBoost (expérimental) | Tree-based avec feature engineering avancé | ~500 cycles | Toggle manuel "Mode Recherche" |

### Pourquoi Prophet en production et XGBoost en expérimental ?

> **Prophet** : robuste au overfitting sur données simulées, interprétable (tendance + saisonnalité visibles), pas de tuning hyperparamètres complexe.
>
> **XGBoost** : potentiellement plus précis sur données réelles, mais nécessite monitoring du data drift et re-entraînement fréquent. Activable via toggle dans le dashboard pour comparaison A/B.

### Pourquoi cette stratégie impressionnera ton jury

> *"J'ai conçu un système robuste par design : il fonctionne pleinement sans historique grâce à la simulation et aux règles métier, puis active automatiquement des modèles statistiques et de machine learning quand suffisamment de données sont accumulées. Prophet assure la stabilité en production, tandis qu'un XGBoost expérimental permet de valider les gains potentiels avant bascule."*

---

## 🗂️ Architecture des dossiers

```
lafarge-camion-tracker/
├── .env                              # Secrets (gitignored)
├── .env.example                      # Template
├── .gitignore
├── docker-compose.yml
├── progress.md
├── README.md
├── Makefile
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI entrypoint + routers
│   │   ├── config.py                 # Pydantic-Settings
│   │   ├── database.py               # PostgreSQL + sessions
│   │   ├── models.py                 # SQLAlchemy ORM (bi-mode + causes dynamiques)
│   │   ├── schemas.py                # Pydantic validation
│   │   ├── dependencies.py
│   │   ├── routers/
│   │   │   ├── trucks.py
│   │   │   ├── events.py
│   │   │   ├── analytics.py
│   │   │   ├── dashboard.py
│   │   │   ├── delays.py
│   │   │   └── mobile.py             # NOUVEAU : API agent mobile + causes
│   │   ├── services/
│   │   │   ├── cv_service.py         # YOLO + EasyOCR (mode réel)
│   │   │   ├── event_ingestion.py  # NOUVEAU : point d'entrée unique caméra/agent
│   │   │   ├── prediction.py         # Niveau 0/1/2 (Prophet + XGBoost toggle)
│   │   │   ├── anomaly_detector.py   # Z-score dynamique
│   │   │   ├── auto_train.py         # Pipeline auto simplifié
│   │   │   └── whitelist.py
│   │   └── simulation/
│   │       └── data_generator.py     # SimPy + Faker (logique de cycle respectée)
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── types/
│   │   ├── components/
│   │   │   ├── mobile/               # NOUVEAU
│   │   │   │   └── AgentCapture.tsx
│   │   │   ├── TruckCard.tsx
│   │   │   ├── DelayForm.tsx
│   │   │   ├── AlertBanner.tsx
│   │   │   └── StatsChart.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   └── MobilePage.tsx        # NOUVEAU
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   └── useCamera.ts          # NOUVEAU
│   │   └── services/
│   │       └── api.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── Dockerfile
│
└── scripts/
    ├── init_db.py
    ├── migrate_bimode.py             # NOUVEAU : migration bi-mode
    └── seed_transporteurs.py
```

---

## ⚙️ Fichiers de configuration

### `.env.example`

```bash
# ============================================
# Lafarge Camion Tracker V2 — Variables d'environnement
# ============================================

# --- Base de données PostgreSQL ---
POSTGRES_USER=lafarge_user
POSTGRES_PASSWORD=change_me_strong_password
POSTGRES_DB=lafarge_tracker
POSTGRES_HOST=db
POSTGRES_PORT=5432

# --- Redis ---
REDIS_HOST=redis
REDIS_PORT=6379

# --- Backend FastAPI ---
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
SECRET_KEY=generate_a_random_secret_key_here
DEBUG=true
ENVIRONMENT=development

# --- Computer Vision ---
CV_MODE=simulation                    # "real" ou "simulation"
CAMERA_PORTE_USINE=rtsp://192.168.1.10:554/stream
CAMERA_PARKING=rtsp://192.168.1.11:554/stream
CAMERA_BASCULE=rtsp://192.168.1.12:554/stream
CAMERA_ENSACHAGE=rtsp://192.168.1.13:554/stream

# --- Simulation ---
SIMULATION_DAYS=30
SIMULATION_TRUCKS_PER_DAY=80

# --- Seuils métier (minutes) ---
SEUIL_ATTENTE_PARKING_MAX=30
SEUIL_BASCULE_MAX=15
SEUIL_ENSACHAGE_MAX=45
SEUIL_CYCLE_TOTAL_MAX=120

# --- Uploads mobiles ---
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE=5242880               # 5MB
```

### `.gitignore`

```gitignore
# Environnement
.env
.env.local

# Python
__pycache__/
*.py[cod]
*.egg-info/
venv/
.venv/
.pytest_cache/
.coverage

# Node
node_modules/
dist/
*.local

# IDEs
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Données / Modèles lourds
*.mp4
*.avi
*.pkl
*.joblib
*.h5
*.onnx
models/
data/videos/
uploads/                                # Photos agent mobile

# Docker volumes
docker-volumes/
```

### `progress.md`

```markdown
# 📊 Suivi de Progression — Stage LafargeHolcim Meknès

## Semaine 1 : Fondations
- [ ] Setup environnement (Python 3.11.9, Node 20, Docker)
- [ ] Architecture + Git init
- [ ] Modélisation DB V2 (PosteConfig, DelayCause, Event.source)
- [ ] API CRUD basique + router mobile
- [ ] Simulation 30 jours de données (logique de cycle respectée)

## Semaine 2 : Ingestion Bi-Mode & Backend Core
- [ ] EventIngestionService (point d'entrée unique)
- [ ] YOLOv8 + EasyOCR (mode simulation par défaut)
- [ ] Logique entrée/sortie par poste avec déduplication
- [ ] WebSocket temps réel (ou polling HTTP fallback)
- [ ] Calcul durées cycle (parking, bascule, ensachage)

## Semaine 3 : Dashboard & PWA Mobile
- [ ] React + TypeScript + Tailwind
- [ ] Dashboard temps réel (liste + barres de progression)
- [ ] Dashboard historique (Recharts) + Top 5 causes retard
- [ ] PWA Agent Mobile (scan photo, formulaire retard, causes dynamiques)
- [ ] Mode offline basique (file d'attente requêtes)

## Semaine 4 : Intelligence & Analytics
- [ ] Niveau 0 : Règles métier opérationnelles
- [ ] Niveau 1 : EWMA + Z-score
- [ ] Niveau 2 : Prophet (production) + toggle XGBoost (expérimental)
- [ ] Analyse horaire/journalière + Heatmap congestion
- [ ] Graphique Pareto des causes de retard

## Semaine 5 : MLOps & Finalisation
- [ ] Pipeline auto-entraînement (CRON) — Prophet prioritaire
- [ ] Docker Compose complet avec volume uploads/
- [ ] Tests + documentation
- [ ] Déploiement test en usine
- [ ] Soutenance

## Notes
- Vérifier RTSP caméras avec OpenCV (si mode real activé)
- Demander accès tickets de pesée pour calibration
- Tester YOLOv8n vs yolov8s sur CPU usine
- **Important** : XGBoost est en mode expérimental uniquement
```

### `backend/requirements.txt`

```
# ============================================
# Backend — Python 3.11.9
# ============================================

# --- Framework Web ---
fastapi==0.111.0
uvicorn[standard]==0.30.0
python-multipart==0.0.9
websockets==12.0

# --- Base de données ---
sqlalchemy==2.0.30
psycopg2-binary==2.9.9
alembic==1.13.1
redis==5.0.4

# --- Validation & Config ---
pydantic==2.7.0
pydantic-settings==2.2.1
python-dotenv==1.0.1

# --- Computer Vision ---
ultralytics==8.2.0
easyocr==1.7.0
opencv-python-headless==4.9.0.80
pillow==10.3.0

# --- Data Science & ML ---
numpy==1.26.4
pandas==2.2.2
scikit-learn==1.5.0
prophet==1.1.5
scipy==1.13.0

# --- Tree-Based Models (Mode EXPÉRIMENTAL uniquement) ---
xgboost==2.0.3
lightgbm==4.3.0
# shap==0.45.0  # Optionnel — décommenter si intégré vraiment

# --- Simulation ---
simpy==4.1.1
faker==25.0.0

# --- Scheduling ---
apscheduler==3.10.4

# --- Tests ---
pytest==8.2.0
pytest-asyncio==0.23.7
httpx==0.27.0
```

### `frontend/package.json`

```json
{
  "name": "lafarge-camion-dashboard",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx --max-warnings 0"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.23.1",
    "recharts": "^2.12.7",
    "axios": "^1.7.2",
    "lucide-react": "^0.390.0",
    "date-fns": "^3.6.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.3.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@typescript-eslint/eslint-plugin": "^7.12.0",
    "@typescript-eslint/parser": "^7.12.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.19",
    "eslint": "^8.57.0",
    "postcss": "^8.4.38",
    "tailwindcss": "^3.4.4",
    "typescript": "^5.4.5",
    "vite": "^5.2.13",
    "vite-plugin-pwa": "^0.20.0"
  }
}
```


---

## 🐍 Backend FastAPI

### `backend/app/config.py`

```python
"""
Configuration centralisée via Pydantic-Settings.
Génère dynamiquement les URLs de connexion pour éviter les bugs d'interpolation Docker.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # --- Variables individuelles DB ---
    postgres_user: str = "lafarge_user"
    postgres_password: str = "change_me_strong_password"
    postgres_db: str = "lafarge_tracker"
    postgres_host: str = "db"
    postgres_port: int = 5432

    # --- Variables individuelles Redis ---
    redis_host: str = "redis"
    redis_port: int = 6379

    # --- Overrides directs optionnels ---
    database_url: Optional[str] = None
    redis_url: Optional[str] = None

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    secret_key: str = "dev-secret"
    debug: bool = True
    environment: str = "development"

    cv_mode: str = "simulation"  # "real" ou "simulation"
    camera_porte_usine: str = ""
    camera_parking: str = ""
    camera_bascule: str = ""
    camera_ensachage: str = ""

    simulation_days: int = 30
    simulation_trucks_per_day: int = 80

    seuil_attente_parking_max: int = 30
    seuil_bascule_max: int = 15
    seuil_ensachage_max: int = 45
    seuil_cycle_total_max: int = 120

    upload_dir: str = "./uploads"
    max_upload_size: int = 5 * 1024 * 1024  # 5MB

    @property
    def get_database_url(self) -> str:
        """Génère dynamiquement l'URL de connexion PostgreSQL."""
        if self.database_url:
            return self.database_url
        return f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def get_redis_url(self) -> str:
        """Génère dynamiquement l'URL de connexion Redis."""
        if self.redis_url:
            return self.redis_url
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Singleton : une seule instance de config en mémoire."""
    return Settings()
```

### `backend/app/models.py`

```python
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
    TERMINE = "TERMINE"
    ANOMALIE = "ANOMALIE"


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
    est_anomalie = Column(Boolean, default=False)
    truck = relationship("Truck", back_populates="cycles")

    @property
    def immatriculation(self) -> str:
        """Permet de récupérer directement l'immatriculation pour le schéma CycleRead."""
        return self.truck.immatriculation if self.truck else ""
```

### `backend/app/schemas.py`

```python
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
    immatriculation: str = Field(..., pattern=r"^[0-9A-Z-]+$", max_length=20)
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
    truck_id: int
    horodatage: datetime
    source: str
    agent_id: Optional[str] = None
    confiance_detection: Optional[float] = None
    cause: Optional[DelayCauseRead] = None
    minutes_retard: Optional[int] = None
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
```

### `backend/app/database.py`

```python
"""
Configuration PostgreSQL avec SQLAlchemy 2.0.
pool_pre_ping=True évite les erreurs de connexion fermée.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.get_database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.debug
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dépendance FastAPI : injecte une session DB par requête."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### `backend/app/main.py`

```python
"""
Point d'entrée FastAPI.
Configure CORS, routers, WebSocket, et le lifespan.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import json

from app.config import get_settings
from app.database import engine
from app.models import Base
from app.routers import trucks, events, analytics, dashboard, delays, mobile
from app.services.cv_service import CVService
from app.services.auto_train import AutoTrainPipeline

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup : création tables + lancement services en arrière-plan."""
    Base.metadata.create_all(bind=engine)

    if settings.cv_mode == "simulation":
        cv_service = CVService()
        asyncio.create_task(cv_service.run_simulation_loop())

    auto_train = AutoTrainPipeline()
    asyncio.create_task(auto_train.schedule_loop())

    yield
    print("Arrêt du serveur...")


app = FastAPI(
    title="Lafarge Camion Tracker API V2",
    description="API traçabilité bi-mode & optimisation flux camions — LafargeHolcim Meknès",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trucks.router, prefix="/api/trucks", tags=["Camions"])
app.include_router(events.router, prefix="/api/events", tags=["Événements"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(delays.router, prefix="/api/delays", tags=["Retards"])
app.include_router(mobile.router, prefix="/api/mobile", tags=["Mobile & Causes"])


# --- WebSocket pour temps réel ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_text(json.dumps(message))
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)

manager = ConnectionManager()

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/health")
def health_check():
    return {"status": "ok", "mode": settings.cv_mode, "version": "2.0.0"}
```


---

## 🔧 Services Backend

### `backend/app/services/event_ingestion.py`

```python
"""
Service d'ingestion unifié — Caméra fixe + Agent mobile coexistent.
Quelle que soit la source, on aboutit au même Event horodaté.
Gère la déduplication (caméra + agent dans les 30s → source="hybrid").
"""
from datetime import datetime, timedelta
from typing import Optional, Literal
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import Event, Truck, Cycle, PosteType, PosteConfig, CaptureMode, DelayCause, TruckStatus


class EventIngestionService:
    """Point d'entrée unique pour TOUT événement (caméra ou agent)."""

    def __init__(self, db: Session):
        self.db = db

    def ingest_event(
        self,
        plaque: str,
        poste: PosteType,
        type_event: Literal["entree", "sortie"],
        source: Literal["camera", "agent_mobile", "manuel", "simulation"],
        agent_id: Optional[str] = None,
        image_path: Optional[str] = None,
        confiance_ocr: Optional[float] = None,
        gps_lat: Optional[float] = None,
        gps_lon: Optional[float] = None,
        delay_cause_id: Optional[int] = None,
        cause_retard_libre: Optional[str] = None,
        minutes_retard: Optional[int] = None,
        horodatage: Optional[datetime] = None,
    ) -> Event:
        """
        Crée un événement de manière idempotente.
        Dédoublonnage : si événement identique dans les 30 dernières secondes,
        on fusionne (source devient "hybrid").
        """
        truck = self._get_or_create_truck(plaque)
        now = horodatage or datetime.utcnow()

        config = self.db.query(PosteConfig).filter(PosteConfig.poste == poste).first()
        if config and not config.is_active:
            raise ValueError(f"Poste {poste.value} désactivé")

        # DÉDUPLICATION — éviter doublon caméra + agent
        recent = self.db.query(Event).filter(
            and_(
                Event.truck_id == truck.id,
                Event.poste == poste,
                Event.type_event == type_event,
                Event.horodatage >= now - timedelta(seconds=30)
            )
        ).first()

        if recent:
            if source == "agent_mobile" and recent.source == "camera":
                recent.source = "hybrid"
                recent.agent_id = agent_id
                if delay_cause_id:
                    recent.delay_cause_id = delay_cause_id
                self.db.commit()
                self.db.refresh(recent)
            return recent

        event = Event(
            truck_id=truck.id,
            poste=poste,
            type_event=type_event,
            horodatage=now,
            source=source,
            agent_id=agent_id,
            image_path=image_path,
            confiance_ocr=confiance_ocr,
            gps_lat=gps_lat,
            gps_lon=gps_lon,
            delay_cause_id=delay_cause_id,
            cause_retard_libre=cause_retard_libre,
            minutes_retard=minutes_retard,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        self._update_cycle(truck.id, poste, type_event, now)

        if delay_cause_id:
            cause = self.db.query(DelayCause).get(delay_cause_id)
            if cause:
                cause.usage_count += 1
                self.db.commit()

        # --- DIFFUSION TEMPS RÉEL VIA WEBSOCKET ---
        try:
            import asyncio
            from app.main import manager
            payload = {
                "type": "NEW_EVENT",
                "poste": poste.value,
                "type_event": type_event,
                "immatriculation": plaque.upper()
            }
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(manager.broadcast(payload))
            except RuntimeError:
                # Pas de boucle d'événement active (ex: script init_db.py)
                pass
        except ImportError:
            pass

        return event

    def _get_or_create_truck(self, plaque: str) -> Truck:
        truck = self.db.query(Truck).filter(Truck.immatriculation == plaque).first()
        if not truck:
            truck = Truck(immatriculation=plaque.upper().strip())
            self.db.add(truck)
            self.db.commit()
            self.db.refresh(truck)
        return truck

    def _update_cycle(self, truck_id: int, poste: PosteType, type_event: str, now: datetime):
        if poste == PosteType.PORTE_USINE and type_event == "entree":
            cycle = Cycle(truck_id=truck_id, entree_porte=now, status=TruckStatus.EN_COURS)
            self.db.add(cycle)
            self.db.commit()

        elif poste == PosteType.PORTE_USINE and type_event == "sortie":
            cycle = self.db.query(Cycle).filter(
                Cycle.truck_id == truck_id,
                Cycle.status == TruckStatus.EN_COURS
            ).order_by(Cycle.entree_porte.desc()).first()
            if cycle:
                cycle.sortie_porte = now
                cycle.status = TruckStatus.TERMINE
                self._recalculate_durations(cycle)
                self.db.commit()

    def _recalculate_durations(self, cycle: Cycle):
        """Recalcule toutes les durées à partir des paires entree/sortie."""
        events = self.db.query(Event).filter(
            Event.truck_id == cycle.truck_id,
            Event.horodatage >= cycle.entree_porte
        ).order_by(Event.horodatage).all()

        poste_times = {}
        for ev in events:
            key = (ev.poste, ev.type_event)
            poste_times[key] = ev.horodatage

        # Parking
        if (PosteType.PARKING, "entree") in poste_times and (PosteType.PARKING, "sortie") in poste_times:
            cycle.duree_parking = (poste_times[(PosteType.PARKING, "sortie")] - poste_times[(PosteType.PARKING, "entree")]).total_seconds() / 60

        # Bascule tare (1er passage)
        bascule_entries = [e for e in events if e.poste == PosteType.BASCULE and e.type_event == "entree"]
        bascule_exits = [e for e in events if e.poste == PosteType.BASCULE and e.type_event == "sortie"]
        if len(bascule_entries) >= 1 and len(bascule_exits) >= 1:
            cycle.duree_bascule_tare = (bascule_exits[0].horodatage - bascule_entries[0].horodatage).total_seconds() / 60
        if len(bascule_entries) >= 2 and len(bascule_exits) >= 2:
            cycle.duree_bascule_brut = (bascule_exits[1].horodatage - bascule_entries[1].horodatage).total_seconds() / 60

        # Ensachage
        if (PosteType.ENSACHAGE, "entree") in poste_times and (PosteType.ENSACHAGE, "sortie") in poste_times:
            cycle.duree_ensachage = (poste_times[(PosteType.ENSACHAGE, "sortie")] - poste_times[(PosteType.ENSACHAGE, "entree")]).total_seconds() / 60

        if cycle.sortie_porte && cycle.entree_porte:
            cycle.duree_total = (cycle.sortie_porte - cycle.entree_porte).total_seconds() / 60
```

### `backend/app/services/prediction.py`

```python
"""
Service de prédiction — Architecture Zero-to-Hero à 3 niveaux.
Prophet en production, XGBoost en mode expérimental (toggle).
"""
from typing import Optional
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
import os

from app.models import Event, Cycle, PosteType, TruckStatus
from app.config import get_settings

settings = get_settings()


class PredictionService:
    """Prédiction unifiée du temps de cycle restant."""

    def __init__(self, db: Session):
        self.db = db
        self.niveau = self._detecter_niveau()

    def _detecter_niveau(self) -> int:
        count = self.db.query(Event).count()
        if count >= 500:
            return 2
        elif count >= 50:
            return 1
        return 0

    def predict_niveau_0(self, poste_actuel: PosteType, est_tare: bool = True) -> dict:
        """Règles métier — fonctionne sans aucune donnée."""
        temps = 0.0
        if poste_actuel == PosteType.PORTE_USINE:
            temps = (settings.seuil_attente_parking_max + settings.seuil_bascule_max +
                     settings.seuil_ensachage_max + settings.seuil_bascule_max + 10)
        elif poste_actuel == PosteType.PARKING:
            temps = (settings.seuil_bascule_max + settings.seuil_ensachage_max +
                     settings.seuil_bascule_max + 10)
        elif poste_actuel == PosteType.BASCULE:
            temps = (settings.seuil_ensachage_max + settings.seuil_bascule_max + 10
                     if est_tare else 10)
        elif poste_actuel == PosteType.ENSACHAGE:
            temps = settings.seuil_bascule_max + 10

        return {
            "eta_minutes": round(temps, 1),
            "niveau": 0,
            "methode": "regles_metier",
            "confiance": "faible",
            "note": "Basé sur les seuils configurés — aucune donnée historique"
        }

    def predict_niveau_1(self, poste_actuel: PosteType) -> dict:
        """EWMA (Exponentially Weighted Moving Average) — s'adapte en ligne."""
        depuis = datetime.utcnow() - timedelta(days=7)
        cycles = self.db.query(Cycle).filter(
            Cycle.entree_porte >= depuis,
            Cycle.status == TruckStatus.TERMINE
        ).all()

        if len(cycles) < 5:
            return self.predict_niveau_0(poste_actuel)

        df = pd.DataFrame([{
            'parking': c.duree_parking,
            'ensachage': c.duree_ensachage,
            'bascule': c.duree_bascule_tare + c.duree_bascule_brut
        } for c in cycles])

        ewma_parking = df['parking'].ewm(span=10).mean().iloc[-1]
        ewma_ensachage = df['ensachage'].ewm(span=10).mean().iloc[-1]
        ewma_bascule = df['bascule'].ewm(span=10).mean().iloc[-1]

        temps = 0.0
        if poste_actuel == PosteType.PORTE_USINE:
            temps = ewma_parking + ewma_bascule + ewma_ensachage + 10
        elif poste_actuel == PosteType.PARKING:
            temps = ewma_bascule + ewma_ensachage + 10
        elif poste_actuel == PosteType.BASCULE:
            temps = ewma_ensachage + ewma_bascule + 10
        elif poste_actuel == PosteType.ENSACHAGE:
            temps = ewma_bascule + 10

        return {
            "eta_minutes": round(temps, 1),
            "niveau": 1,
            "methode": "ewma",
            "confiance": "moyenne",
            "note": f"Basé sur {len(cycles)} cycles des 7 derniers jours"
        }

    def predict_niveau_2(self, poste_actuel: PosteType, modele_prefere: str = "prophet") -> dict:
        """
        Niveau 2 : Prophet par défaut (production).
        XGBoost disponible en mode expérimental via toggle.
        """
        if modele_prefere == "xgboost" and os.path.exists("models/xgboost_champion.pkl"):
            return self._predict_xgboost(poste_actuel)
        return self._predict_prophet(poste_actuel)

    def _predict_prophet(self, poste_actuel: PosteType) -> dict:
        """Prophet — modèle de production robuste et interprétable."""
        model_path = "models/prophet_champion.pkl"

        if not os.path.exists(model_path):
            return self.predict_niveau_1(poste_actuel)

        import pickle
        with open(model_path, 'rb') as f:
            model = pickle.load(f)

        future = model.make_future_dataframe(periods=1, freq='H')
        forecast = model.predict(future)

        return {
            "eta_minutes": round(forecast['yhat'].iloc[-1], 1),
            "niveau": 2,
            "methode": "prophet",
            "confiance": "élevée",
            "note": "Modèle Prophet entraîné automatiquement — production"
        }

    def _predict_xgboost(self, poste_actuel: PosteType) -> dict:
        """XGBoost — mode expérimental, pour comparaison A/B uniquement."""
        import pickle
        with open("models/xgboost_champion.pkl", 'rb') as f:
            artifact = pickle.load(f)

        # Simplifié : retourne la prédiction du modèle
        return {
            "eta_minutes": 0.0,  # À implémenter selon feature engineering
            "niveau": 2,
            "methode": "xgboost_experimental",
            "confiance": "moyenne",
            "note": "Mode expérimental — à valider sur données réelles"
        }

    def predict(self, poste_actuel: PosteType, est_tare: bool = True, modele_prefere: str = "prophet") -> dict:
        """Point d'entrée unique — choisit le meilleur niveau automatiquement."""
        if self.niveau >= 2:
            result = self.predict_niveau_2(poste_actuel, modele_prefere)
        elif self.niveau >= 1:
            result = self.predict_niveau_1(poste_actuel)
        else:
            result = self.predict_niveau_0(poste_actuel, est_tare)
        result["niveau_actif"] = self.niveau
        return result
```

### `backend/app/services/anomaly_detector.py`

```python
"""
Détection d'anomalies par Z-score dynamique.
Identifie les camions qui dépassent significativement la norme.
"""
import numpy as np
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.models import Cycle, TruckStatus
from app.config import get_settings

settings = get_settings()


class AnomalyDetector:
    """Détecteur d'anomalies — Z-score > 2 = anomalie."""

    def __init__(self, db: Session):
        self.db = db

    def detecter_anomalies_cycle(self, truck_id: int) -> dict:
        depuis = datetime.utcnow() - timedelta(days=14)
        cycles = self.db.query(Cycle).filter(
            Cycle.entree_porte >= depuis,
            Cycle.status == TruckStatus.TERMINE
        ).all()

        if len(cycles) < 5:
            return self._check_seuils_metier(truck_id)

        durees = np.array([c.duree_total for c in cycles])
        moyenne, ecart_type = np.mean(durees), np.std(durees)

        cycle_actuel = self.db.query(Cycle).filter(
            Cycle.truck_id == truck_id,
            Cycle.status == TruckStatus.EN_COURS
        ).first()

        if not cycle_actuel:
            return {"anomalie": False, "raison": "Aucun cycle en cours"}

        duree_ecoulee = (datetime.utcnow() - cycle_actuel.entree_porte).total_seconds() / 60
        z_score = (duree_ecoulee - moyenne) / ecart_type if ecart_type > 0 else 0
        est_anomalie = z_score > 2.0 or duree_ecoulee > settings.seuil_cycle_total_max

        return {
            "anomalie": est_anomalie,
            "z_score": round(z_score, 2),
            "duree_ecoulee_min": round(duree_ecoulee, 1),
            "moyenne_historique": round(moyenne, 1),
            "ecart_type": round(ecart_type, 1),
            "niveau": 1,
            "raison": (f"Z-score {z_score:.1f} > 2.0" if z_score > 2.0
                       else f"Seuil métier dépassé") if est_anomalie else "Normal"
        }

    def _check_seuils_metier(self, truck_id: int) -> dict:
        """Fallback Niveau 0 : vérification simple des seuils."""
        cycle = self.db.query(Cycle).filter(
            Cycle.truck_id == truck_id,
            Cycle.status == TruckStatus.EN_COURS
        ).first()

        if not cycle:
            return {"anomalie": False, "raison": "Aucun cycle en cours"}

        duree = (datetime.utcnow() - cycle.entree_porte).total_seconds() / 60
        est_anomalie = duree > settings.seuil_cycle_total_max

        return {
            "anomalie": est_anomalie,
            "duree_ecoulee_min": round(duree, 1),
            "seuil_max": settings.seuil_cycle_total_max,
            "niveau": 0,
            "raison": (f"Seuil {settings.seuil_cycle_total_max}min dépassé"
                       if est_anomalie else "Normal — pas assez d'historique")
        }

    def get_poste_bloquant(self) -> dict:
        """Identifie le poste avec la durée moyenne la plus élevée."""
        depuis = datetime.utcnow() - timedelta(days=7)
        cycles = self.db.query(Cycle).filter(
            Cycle.entree_porte >= depuis,
            Cycle.status == TruckStatus.TERMINE
        ).all()

        if not cycles:
            return {"poste_bloquant": None, "note": "Pas assez de données"}

        import pandas as pd
        df = pd.DataFrame([{
            'parking': c.duree_parking,
            'bascule': c.duree_bascule_tare + c.duree_bascule_brut,
            'ensachage': c.duree_ensachage
        } for c in cycles])

        moyennes = df.mean().to_dict()
        bloquant = max(moyennes, key=moyennes.get)

        return {
            "poste_bloquant": bloquant,
            "duree_moyenne_min": round(moyennes[bloquant], 1),
            "details": {k: round(v, 1) for k, v in moyennes.items()}
        }
```

### `backend/app/services/auto_train.py`

```python
"""
Pipeline d'entraînement automatique — Prophet prioritaire + XGBoost expérimental.
Champion = Prophet (production). Challenger XGBoost = toggle manuel uniquement.
"""
import asyncio
import os
import pickle
import json
from datetime import datetime, timedelta
from typing import Dict, Any
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from app.database import SessionLocal
from app.models import Cycle, TruckStatus


class AutoTrainPipeline:
    """MLOps simplifié : Prophet en production, XGBoost en mode recherche."""

    MODELS_DIR = "models"
    METRICS_FILE = "models/training_metrics.json"

    def __init__(self):
        os.makedirs(self.MODELS_DIR, exist_ok=True)

    async def schedule_loop(self):
        """Boucle infinie : entraînement toutes les 6 heures."""
        while True:
            await asyncio.sleep(6 * 3600)
            try:
                self.run_training_pipeline()
            except Exception as e:
                print(f"[AutoTrain] Erreur : {e}")

    def _build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Feature engineering pour XGBoost (mode expérimental)."""
        df = df.copy()
        df['hour_sin'] = np.sin(2 * np.pi * df['heure'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['heure'] / 24)
        df['dow_sin'] = np.sin(2 * np.pi * df['jour_semaine'] / 7)
        df['dow_cos'] = np.cos(2 * np.pi * df['jour_semaine'] / 7)
        df['is_weekend'] = (df['jour_semaine'] >= 5).astype(int)
        df['is_morning_rush'] = ((df['heure'] >= 7) & (df['heure'] <= 9)).astype(int)
        df['is_afternoon_rush'] = ((df['heure'] >= 14) & (df['heure'] <= 16)).astype(int)
        df['lag_1d'] = df['y'].shift(24)
        df['lag_7d'] = df['y'].shift(24 * 7)
        df['rolling_mean_24h'] = df['y'].shift(1).rolling(window=24, min_periods=1).mean()
        df['rolling_std_24h'] = df['y'].shift(1).rolling(window=24, min_periods=1).std().fillna(0)
        df = df.fillna(df.median(numeric_only=True))
        return df

    def run_training_pipeline(self) -> Dict[str, Any]:
        print(f"[AutoTrain] Démarrage — {datetime.now()}")

        db = SessionLocal()
        try:
            # 1. CHARGEMENT
            depuis = datetime.utcnow() - timedelta(days=90)
            cycles = db.query(Cycle).filter(
                Cycle.entree_porte >= depuis,
                Cycle.status == TruckStatus.TERMINE,
                Cycle.duree_total > 0
            ).all()

            if len(cycles) < 100:
                return {"status": "skipped", "raison": f"{len(cycles)} < 100 cycles"}

            # 2. PRÉPARATION
            df = pd.DataFrame([{
                'ds': c.entree_porte,
                'y': c.duree_total,
                'heure': c.entree_porte.hour,
                'jour_semaine': c.entree_porte.weekday(),
                'parking': c.duree_parking,
                'ensachage': c.duree_ensachage,
                'bascule': c.duree_bascule_tare + c.duree_bascule_brut,
            } for c in cycles])

            # Split chronologique
            split_idx = int(len(df) * 0.8)
            train_df = df.iloc[:split_idx].copy()
            test_df = df.iloc[split_idx:].copy()

            scores = {}
            candidats = {}

            # --- Champion : Prophet (production) ---
            try:
                from prophet import Prophet
                m = Prophet(daily_seasonality=True, yearly_seasonality=False)
                m.fit(train_df[['ds', 'y']].rename(columns={'ds': 'ds', 'y': 'y'}))
                future = test_df[['ds']].rename(columns={'ds': 'ds'})
                forecast = m.predict(future)
                pred_prophet = forecast['yhat'].values

                mae_prophet = mean_absolute_error(test_df['y'].values, pred_prophet)
                scores['prophet'] = round(mae_prophet, 2)
                candidats['prophet'] = m
                print(f"[AutoTrain] Prophet — MAE: {mae_prophet:.2f}")
            except Exception as e:
                print(f"[AutoTrain] Prophet failed: {e}")

            # --- Challenger : XGBoost (expérimental) ---
            try:
                import xgboost as xgb
                df_feat = self._build_features(df)
                train_feat = df_feat.iloc[:split_idx]
                test_feat = df_feat.iloc[split_idx:]
                feature_cols = [c for c in df_feat.columns if c not in ['ds', 'y']]

                dtrain = xgb.DMatrix(train_feat[feature_cols], label=train_feat['y'])
                dtest = xgb.DMatrix(test_feat[feature_cols], label=test_feat['y'])

                params = {
                    'objective': 'reg:squarederror',
                    'max_depth': 6, 'learning_rate': 0.05,
                    'subsample': 0.8, 'colsample_bytree': 0.8,
                    'eval_metric': 'mae', 'seed': 42
                }
                model_xgb = xgb.train(params, dtrain, num_boost_round=200,
                                      evals=[(dtest, 'test')],
                                      early_stopping_rounds=20, verbose_eval=False)
                pred_xgb = model_xgb.predict(dtest)
                mae_xgb = mean_absolute_error(test_feat['y'].values, pred_xgb)
                scores['xgboost'] = round(mae_xgb, 2)
                candidats['xgboost'] = model_xgb
                print(f"[AutoTrain] XGBoost — MAE: {mae_xgb:.2f}")
            except Exception as e:
                print(f"[AutoTrain] XGBoost failed: {e}")

            if not scores:
                return {"status": "failed", "raison": "Aucun modèle entraînable"}

            # 3. DÉPLOIEMENT — Prophet est TOUJOURS le champion production
            champion_mae = self._get_champion_mae()
            meilleur = min(scores, key=scores.get)

            # Sauvegarde Prophet (production)
            if 'prophet' in candidats:
                self._save_model('prophet_champion.pkl', candidats['prophet'], scores['prophet'], len(df))

            # Sauvegarde XGBoost (expérimental) si meilleur que Prophet
            if 'xgboost' in candidats and scores.get('xgboost', 999) < scores.get('prophet', 999) * 0.95:
                self._save_model('xgboost_champion.pkl', candidats['xgboost'], scores['xgboost'], len(df))
                print(f"[AutoTrain] XGBoost meilleur mais reste expérimental")

            self._save_metrics({
                "date": datetime.now().isoformat(),
                "champion": "prophet",
                "mae": scores.get('prophet'),
                "n_cycles": len(cycles),
                "all_scores": scores
            })

            print(f"[AutoTrain] Terminé — Scores: {scores}")
            return {"status": "success", "scores": scores}

        finally:
            db.close()

    def _save_model(self, filename, model, mae, n_samples):
        artifact = {
            'model': model,
            'mae': mae,
            'trained_at': datetime.now().isoformat(),
            'n_samples': n_samples
        }
        with open(f"models/{filename}", 'wb') as f:
            pickle.dump(artifact, f)

    def _get_champion_mae(self) -> float:
        if os.path.exists(self.METRICS_FILE):
            with open(self.METRICS_FILE) as f:
                data = json.load(f)
                return data.get("mae", 9999.0)
        return 9999.0

    def _save_metrics(self, metrics: dict):
        with open(self.METRICS_FILE, 'w') as f:
            json.dump(metrics, f, indent=2)
```

### `backend/app/services/cv_service.py`

```python
"""
Service Computer Vision.
En mode "real" : YOLOv8 + EasyOCR sur flux RTSP.
En mode "simulation" : génère des événements crédibles avec logique de cycle respectée.
"""
import asyncio
import random
from datetime import datetime
from typing import Optional

from app.config import get_settings
from app.database import SessionLocal
from app.models import Truck, Event, Cycle, PosteType
from app.services.event_ingestion import EventIngestionService

settings = get_settings()


class CVService:
    """Service de capture et traitement des flux caméra."""

    def __init__(self):
        self.mode = settings.cv_mode
        # Ordre logique des postes avec types d'événements explicites pour la simulation
        self.postes_cycle = [
            (PosteType.PORTE_USINE, "entree"),
            (PosteType.PARKING, "entree"),
            (PosteType.PARKING, "sortie"),
            (PosteType.BASCULE, "entree"),
            (PosteType.BASCULE, "sortie"),
            (PosteType.ENSACHAGE, "entree"),
            (PosteType.ENSACHAGE, "sortie"),
            (PosteType.BASCULE, "entree"),
            (PosteType.BASCULE, "sortie"),
            (PosteType.PORTE_USINE, "sortie")
        ]
        self.plaques = ["12345-أ-1", "67890-ب-2", "11111-د-3",
                        "22222-و-4", "33333-ط-5", "44444-س-6"]
        # État de simulation : pour chaque plaque, index du poste actuel dans le cycle
        self.sim_state = {}

    async def run_simulation_loop(self):
        """
        Boucle de simulation en arrière-plan.
        Génère des événements de camion toutes les 5-15 secondes
        en respectant la logique de cycle (pas de sortie sans entrée).
        """
        print("[CV] Mode simulation activé — génération d'événements...")

        while True:
            await asyncio.sleep(random.randint(5, 15))

            db = SessionLocal()
            try:
                plaque = random.choice(self.plaques)
                service = EventIngestionService(db)

                # Initialiser l'état si nouveau camion
                if plaque not in self.sim_state:
                    self.sim_state[plaque] = {"index": 0}

                state = self.sim_state[plaque]
                poste, type_event = self.postes_cycle[state["index"]]

                # Créer l'événement via le service unifié
                service.ingest_event(
                    plaque=plaque,
                    poste=poste,
                    type_event=type_event,  # type: ignore
                    source="simulation",
                    confiance_ocr=round(random.uniform(0.75, 0.99), 2)
                )

                print(f"[CV-Sim] {plaque} | {poste.value} | {type_event}")

                # Avancer l'index pour le prochain tour
                state["index"] = (state["index"] + 1) % len(self.postes_cycle)

            finally:
                db.close()

    def detect_from_camera(self, camera_url: str) -> Optional[dict]:
        """
        Mode réel : capture frame, détecte camion, lit plaque.
        À appeler par un worker ou un scheduler.
        """
        if self.mode != "real":
            return None

        try:
            import cv2
            import numpy as np
            from ultralytics import YOLO
            import easyocr

            model = YOLO("yolov8n.pt")
            reader = easyocr.Reader(['en'], gpu=False)

            cap = cv2.VideoCapture(camera_url)
            ret, frame = cap.read()
            cap.release()

            if not ret:
                return None

            results = model(frame, verbose=False)
            detections = []
            for r in results:
                for box in r.boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    if cls in [2, 5, 7] and conf > 0.5:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        detections.append({"bbox": [x1, y1, x2, y2], "conf": round(conf, 3)})

            return {
                "detections": detections,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            print(f"[CV] Erreur détection : {e}")
            return None
```


---

## 📡 Routers API Backend

### `backend/app/routers/trucks.py`

```python
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
```

### `backend/app/routers/events.py`

```python
"""Router API pour la gestion des événements."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Event
from app.schemas import EventRead

router = APIRouter(prefix="/api/events", tags=["Événements"])

@router.get("/active", response_model=List[EventRead])
def list_active_events(db: Session = Depends(get_db)):
    """Retourne les événements récents des dernières 24 heures."""
    since = datetime.utcnow() - timedelta(hours=24)
    return db.query(Event).options(joinedload(Event.truck)).filter(Event.horodatage >= since).order_by(Event.horodatage.desc()).all()
```

### `backend/app/routers/analytics.py`

```python
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
```

### `backend/app/routers/dashboard.py`

```python
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
```

### `backend/app/routers/delays.py`

```python
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
```

### `backend/app/routers/mobile.py`

```python
"""Router API pour l'agent mobile et les causes de retard dynamiques."""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.models import DelayCause, PosteType, PosteConfig, CaptureMode
from app.schemas import DelayCauseCreate, DelayCauseRead, PosteConfigRead, PosteConfigUpdate
from app.services.event_ingestion import EventIngestionService

router = APIRouter(prefix="/api/mobile", tags=["Mobile & Causes"])


# ============================================================
# CAUSES DE RETARD DYNAMIQUES
# ============================================================
@router.get("/delay-causes", response_model=List[DelayCauseRead])
def list_causes(
    poste: Optional[PosteType] = None,
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """
    Retourne les causes de retard, triées par fréquence d'utilisation.
    Si 'poste' est fourni, filtre les causes pertinentes pour ce poste.
    """
    query = db.query(DelayCause)
    if active_only:
        query = query.filter(DelayCause.is_active == True)
    if poste:
        query = query.filter(
            (DelayCause.poste_concerne == poste) | (DelayCause.poste_concerne == None)
        )
    return query.order_by(DelayCause.usage_count.desc()).all()


@router.post("/delay-causes", response_model=DelayCauseRead)
def create_cause(cause: DelayCauseCreate, db: Session = Depends(get_db)):
    """Crée une nouvelle cause de retard à la volée."""
    existing = db.query(DelayCause).filter(DelayCause.nom.ilike(cause.nom)).first()
    if existing:
        return existing

    db_cause = DelayCause(**cause.dict())
    db.add(db_cause)
    db.commit()
    db.refresh(db_cause)
    return db_cause


@router.patch("/delay-causes/{cause_id}/deactivate")
def deactivate_cause(cause_id: int, db: Session = Depends(get_db)):
    cause = db.query(DelayCause).get(cause_id)
    if not cause:
        raise HTTPException(404, "Cause non trouvée")
    cause.is_active = False
    db.commit()
    return {"status": "deactivated"}


# ============================================================
# INGESTION MOBILE (Agent scanne avec téléphone)
# ============================================================
@router.post("/events")
async def create_event_mobile(
    plaque: str = Form(...),
    poste: PosteType = Form(...),
    type_event: str = Form(..., pattern="^(entree|sortie)$"),
    agent_id: str = Form(...),
    delay_cause_id: Optional[int] = Form(None),
    minutes_retard: Optional[int] = Form(None),
    gps_lat: Optional[float] = Form(None),
    gps_lon: Optional[float] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Point d'entrée pour l'agent mobile.
    Accepte une photo optionnelle + métadonnées GPS.
    """
    config = db.query(PosteConfig).filter(PosteConfig.poste == poste).first()
    if config and config.capture_mode == CaptureMode.CAMERA:
        raise HTTPException(400, f"Poste {poste.value} en mode caméra uniquement")

    image_path = None
    confiance_ocr = None
    if photo:
        contents = await photo.read()
        # TODO: appeler OCRService si dispo
        image_path = f"/uploads/{photo.filename}"

    service = EventIngestionService(db)
    event = service.ingest_event(
        plaque=plaque,
        poste=poste,
        type_event=type_event,  # type: ignore
        source="agent_mobile",
        agent_id=agent_id,
        image_path=image_path,
        confiance_ocr=confiance_ocr,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        delay_cause_id=delay_cause_id,
        minutes_retard=minutes_retard,
    )
    return event


# ============================================================
# CONFIG POSTES (Admin)
# ============================================================
@router.get("/poste-configs", response_model=List[PosteConfigRead])
def list_poste_configs(db: Session = Depends(get_db)):
    return db.query(PosteConfig).all()


@router.put("/poste-configs/{poste}", response_model=PosteConfigRead)
def update_poste_config(
    poste: PosteType,
    config_update: PosteConfigUpdate,
    db: Session = Depends(get_db)
):
    """
    Permet de changer le mode d'un poste à chaud via un corps JSON.
    Ex: la bascule passe de CAMERA à HYBRID si la caméra tombe en panne.
    """
    config = db.query(PosteConfig).filter(PosteConfig.poste == poste).first()
    if not config:
        config = PosteConfig(poste=poste)
        db.add(config)

    config.capture_mode = config_update.capture_mode
    if config_update.camera_url is not None:
        config.camera_url = config_update.camera_url
    if config_update.agent_pin is not None:
        config.agent_pin = config_update.agent_pin

    db.commit()
    db.refresh(config)
    return config
```

---

## 🎲 Simulation & Génération de données

### `backend/app/simulation/data_generator.py`

```python
"""
Générateur de données synthétiques crédibles avec logique de cycle respectée.
Simule le flux complet de camions sur plusieurs jours.
"""
import random
from datetime import datetime, timedelta
from faker import Faker
from typing import List, Dict

fake = Faker()

TEMPS_MOYENS = {
    "parking": (10, 25),
    "bascule_tare": (3, 8),
    "ensachage": (20, 40),
    "bascule_brut": (3, 8),
    "sortie": (2, 5)
}

TRANSPORTEURS = [
    "Trans Meknes", "Atlas Logistique", "Maroc Transport",
    "Sahara Camions", "Fes Cargo", "Rabat Transit"
]


def generate_moroccan_plate() -> str:
    """Génère une plaque marocaine réaliste."""
    nums = random.randint(10000, 99999)
    lettres = random.choice(["أ", "ب", "د", "و", "ط", "س", "ف", "ق", "ش", "م", "ن", "ل", "ه", "ي"])
    region = random.randint(1, 99)
    return f"{nums}-{lettres}-{region}"


def simuler_journee(date: datetime, nb_camions: int) -> List[Dict]:
    """Simule une journée complète à l'usine avec logique de cycle."""
    events = []

    for i in range(nb_camions):
        arrival_offset = random.randint(0, 12 * 60)
        current = date.replace(hour=6, minute=0) + timedelta(minutes=arrival_offset)

        plaque = generate_moroccan_plate()
        company = random.choice(TRANSPORTEURS)
        truck = {"immatriculation": plaque, "transporteur_nom": company}

        # 1. PORTE USINE — Entrée
        events.append({"truck": truck, "poste": "porte_usine", "type": "entree", "horodatage": current})

        # 2. PARKING (Entrée & Sortie)
        current += timedelta(minutes=random.randint(2, 5))
        events.append({"truck": truck, "poste": "parking", "type": "entree", "horodatage": current})
        
        parking_duration = random.randint(*TEMPS_MOYENS["parking"])
        cause_parking = None
        if random.random() < 0.1:
            parking_duration += random.randint(15, 45)
            cause_parking = "Attente opérateur"
            
        current += timedelta(minutes=parking_duration)
        events.append({"truck": truck, "poste": "parking", "type": "sortie", "horodatage": current, "cause_retard": cause_parking})

        # 3. BASCULE — Tare (Entrée & Sortie)
        current += timedelta(minutes=random.randint(2, 5))
        events.append({"truck": truck, "poste": "bascule", "type": "entree", "horodatage": current})
        current += timedelta(minutes=random.randint(*TEMPS_MOYENS["bascule_tare"]))
        events.append({"truck": truck, "poste": "bascule", "type": "sortie", "horodatage": current})

        # 4. ENSACHAGE (Entrée & Sortie)
        current += timedelta(minutes=random.randint(2, 5))
        events.append({"truck": truck, "poste": "ensachage", "type": "entree", "horodatage": current})
        duree_ensachage = random.randint(*TEMPS_MOYENS["ensachage"])
        cause_ensachage = None
        if random.random() < 0.15:
            duree_ensachage += random.randint(20, 60)
            cause_ensachage = random.choice([
                "Panne ensacheuse", "Rupture sacs", "Attente qualité",
                "Changement produit", "Maintenance"
            ])
        current += timedelta(minutes=duree_ensachage)
        events.append({"truck": truck, "poste": "ensachage", "type": "sortie", "horodatage": current, "cause_retard": cause_ensachage})

        # 5. BASCULE — Brut (Entrée & Sortie)
        current += timedelta(minutes=random.randint(2, 5))
        events.append({"truck": truck, "poste": "bascule", "type": "entree", "horodatage": current})
        current += timedelta(minutes=random.randint(*TEMPS_MOYENS["bascule_brut"]))
        events.append({"truck": truck, "poste": "bascule", "type": "sortie", "horodatage": current})

        # 6. PORTE USINE — Sortie
        current += timedelta(minutes=random.randint(*TEMPS_MOYENS["sortie"]))
        events.append({"truck": truck, "poste": "porte_usine", "type": "sortie", "horodatage": current})

    return events


def run_full_simulation(days: int = 30, trucks_per_day: int = 80) -> List[Dict]:
    """Lance la simulation sur N jours."""
    all_events = []
    base_date = datetime.now() - timedelta(days=days)

    for day in range(days):
        date = base_date + timedelta(days=day)
        if date.weekday() >= 5:
            nb = int(trucks_per_day * 0.3)
        else:
            nb = int(trucks_per_day * random.uniform(0.8, 1.2))
        all_events.extend(simuler_journee(date, nb))

    return all_events
```

### `scripts/init_db.py`

```python
#!/usr/bin/env python3
"""
Script d'initialisation de la base de données.
À exécuter UNE SEULE FOIS au démarrage du projet.
"""
import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.database import engine
from app.models import Base
from app.database import SessionLocal
from app.models import Truck, Event, Cycle, Transporteur, PosteType, PosteConfig, CaptureMode, DelayCause
from app.simulation.data_generator import run_full_simulation, TRANSPORTEURS
from app.services.event_ingestion import EventIngestionService
from app.config import get_settings

settings = get_settings()


def init_database():
    print("🚀 Initialisation de la base de données V2...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables créées")

    db = SessionLocal()
    try:
        # 1. Transporteurs
        transporteurs = {}
        for nom in TRANSPORTEURS:
            t = Transporteur(nom=nom, est_whitelist=True)
            db.add(t)
            db.commit()
            db.refresh(t)
            transporteurs[nom] = t.id
        print(f"✅ {len(transporteurs)} transporteurs créés")

        # 2. Configs postes (bi-mode)
        configs = [
            (PosteType.PORTE_USINE, CaptureMode.CAMERA),
            (PosteType.PARKING, CaptureMode.AGENT),
            (PosteType.BASCULE, CaptureMode.HYBRID),
            (PosteType.ENSACHAGE, CaptureMode.AGENT),
        ]
        for poste, mode in configs:
            if not db.query(PosteConfig).filter(PosteConfig.poste == poste).first():
                db.add(PosteConfig(poste=poste, capture_mode=mode, agent_pin="1234"))
        db.commit()
        print("✅ Configs postes créées")

        # 3. Causes de retard par défaut
        default_causes = [
            ("Attente opérateur", None),
            ("Panne équipement", None),
            ("Rupture sacs", PosteType.ENSACHAGE),
            ("Vérification qualité", PosteType.ENSACHAGE),
            ("Changement produit", PosteType.ENSACHAGE),
            ("Problème pesée", PosteType.BASCULE),
            ("Maintenance", None),
        ]
        for nom, p in default_causes:
            if not db.query(DelayCause).filter(DelayCause.nom == nom).first():
                db.add(DelayCause(nom=nom, poste_concerne=p, created_by="system"))
        db.commit()
        print("✅ Causes de retard par défaut créées")

        # 4. Simulation
        print(f"🎲 Simulation de {settings.simulation_days} jours...")
        events_data = run_full_simulation(
            days=settings.simulation_days,
            trucks_per_day=settings.simulation_trucks_per_day
        )

        # Trier chronologiquement pour que l'ingestion et la création des cycles soient cohérentes
        events_data.sort(key=lambda x: x["horodatage"])

        # Pré-créer les camions avec leurs transporteurs
        trucks_cache = {}
        for ev in events_data:
            plaque = ev["truck"]["immatriculation"]
            if plaque not in trucks_cache:
                truck = db.query(Truck).filter(Truck.immatriculation == plaque).first()
                if not truck:
                    truck = Truck(
                        immatriculation=plaque,
                        transporteur_id=random.choice(list(transporteurs.values()))
                    )
                    db.add(truck)
                    db.commit()
                    db.refresh(truck)
                trucks_cache[plaque] = truck.id

        # Ingestion via le service unifié pour générer automatiquement les Cycles et durées
        service = EventIngestionService(db)
        print("📥 Ingestion des événements et génération automatique des cycles...")
        for ev in events_data:
            plaque = ev["truck"]["immatriculation"]
            
            delay_cause_id = None
            if ev.get("cause_retard"):
                cause_obj = db.query(DelayCause).filter(DelayCause.nom == ev["cause_retard"]).first()
                if cause_obj:
                    delay_cause_id = cause_obj.id

            service.ingest_event(
                plaque=plaque,
                poste=PosteType(ev["poste"]),
                type_event=ev["type"],
                source="simulation",
                delay_cause_id=delay_cause_id,
                cause_retard_libre=ev.get("cause_retard"),
                horodatage=ev["horodatage"]
            )

        print(f"✅ {len(events_data)} événements simulés et cycles associés injectés avec succès !")
        print("🎉 Base de données prête !")

    finally:
        db.close()


if __name__ == "__main__":
    init_database()
```

### `scripts/migrate_bimode.py`

```python
#!/usr/bin/env python3
"""Migration pour ajouter les tables bi-mode et causes dynamiques (si upgrade V1→V2)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.database import engine
from app.models import Base, PosteType, CaptureMode, PosteConfig, DelayCause
from app.database import SessionLocal

Base.metadata.create_all(bind=engine)
print("✅ Tables poste_configs et delay_causes créées")

db = SessionLocal()
try:
    for poste in PosteType:
        if not db.query(PosteConfig).filter(PosteConfig.poste == poste).first():
            mode = CaptureMode.CAMERA if poste == PosteType.PORTE_USINE else CaptureMode.AGENT
            db.add(PosteConfig(poste=poste, capture_mode=mode))

    default_causes = [
        ("Attente opérateur", None), ("Panne équipement", None),
        ("Rupture sacs", PosteType.ENSACHAGE), ("Vérification qualité", PosteType.ENSACHAGE),
        ("Changement produit", PosteType.ENSACHAGE), ("Problème pesée", PosteType.BASCULE),
        ("Maintenance", None),
    ]
    for nom, p in default_causes:
        if not db.query(DelayCause).filter(DelayCause.nom == nom).first():
            db.add(DelayCause(nom=nom, poste_concerne=p, created_by="system"))

    db.commit()
    print("✅ Configs et causes par défaut insérées")
finally:
    db.close()
```

---

## ⚛️ Frontend React

### `frontend/src/types/index.ts`

```typescript
export interface Truck {
  id: number;
  immatriculation: string;
  type_camion: string;
  transporteur?: Transporteur;
}

export interface Transporteur {
  id: number;
  nom: string;
  est_whitelist: boolean;
}

export interface DelayCause {
  id: number;
  nom: string;
  poste_concerne: string | null;
  usage_count: number;
  is_active: boolean;
}

export interface Event {
  id: number;
  truck_id: number;
  poste: 'porte_usine' | 'parking' | 'bascule' | 'ensachage';
  type_event: 'entree' | 'sortie';
  horodatage: string;
  source: string;
  agent_id?: string;
  cause?: DelayCause;
  minutes_retard?: number;
  truck?: Truck;
}

export interface Cycle {
  id: number;
  immatriculation: string;
  entree_porte: string;
  sortie_porte?: string;
  duree_total: number;
  status: string;
  est_anomalie: boolean;
}

export interface DashboardStats {
  camions_en_cours: number;
  camions_aujourdhui: number;
  temps_moyen_cycle: number;
  poste_bloquant?: string;
  alertes_actives: number;
  top_cause_retard?: string;
}
```

### `frontend/src/services/api.ts`

```typescript
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function apiFetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

export const getTrucks = () => apiFetch<Truck[]>('/api/trucks/');
export const getActiveEvents = () => apiFetch<Event[]>('/api/events/active');
export const getDashboardStats = () => apiFetch<DashboardStats>('/api/dashboard/stats');
export const getCycles = () => apiFetch<Cycle[]>('/api/analytics/cycles');
export const getDelayCauses = (poste?: string) => apiFetch<DelayCause[]>(`/api/mobile/delay-causes?poste=${poste || ''}&active_only=true`);
export const createDelayCause = (data: Partial<DelayCause>) => apiFetch<DelayCause>('/api/mobile/delay-causes', {
  method: 'POST', body: JSON.stringify(data)
});
```

### `frontend/src/hooks/useWebSocket.ts`

```typescript
import { useEffect, useRef, useState } from 'react';

export function useWebSocket(url: string) {
  const [lastMessage, setLastMessage] = useState<any>(null);
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    const socket = new WebSocket(url);
    ws.current = socket;

    socket.onopen = () => {
      setIsConnected(true);
      const interval = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send('ping');
      }, 30000);
      socket.onclose = () => clearInterval(interval);
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data !== 'pong') setLastMessage(data);
    };

    socket.onclose = () => setIsConnected(false);

    return () => socket.close();
  }, [url]);

  return { lastMessage, isConnected };
}
```

### `frontend/src/hooks/useCamera.ts`

```typescript
import { useState, useRef, useCallback } from 'react';

export function useCamera() {
  const [photo, setPhoto] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const triggerCapture = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const handleCapture = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    setFile(selected);
    const reader = new FileReader();
    reader.onloadend = () => setPhoto(reader.result as string);
    reader.readAsDataURL(selected);
  }, []);

  const clearPhoto = useCallback(() => {
    setPhoto(null);
    setFile(null);
    if (inputRef.current) inputRef.current.value = '';
  }, []);

  return { photo, file, inputRef, triggerCapture, handleCapture, clearPhoto };
}
```


---

### `frontend/src/components/AlertBanner.tsx`

```tsx
import { AlertTriangle, Info } from 'lucide-react';

interface Props {
  message: string;
  type: 'warning' | 'info';
}

export function AlertBanner({ message, type }: Props) {
  const isWarning = type === 'warning';
  return (
    <div className={`p-4 rounded-lg flex items-center gap-3 border ${isWarning ? 'bg-yellow-50 border-yellow-200 text-yellow-800' : 'bg-blue-50 border-blue-200 text-blue-800'}`}>
      {isWarning ? <AlertTriangle className="w-5 h-5 text-yellow-600" /> : <Info className="w-5 h-5 text-blue-600" />}
      <span className="font-medium">{message}</span>
    </div>
  );
}
```

### `frontend/src/components/StatsChart.tsx`

```tsx
import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { getCycles } from '@/services/api';

export function StatsChart() {
  const [data, setData] = useState<any[]>([]);

  useEffect(() => {
    getCycles().then(cycles => {
      const formatted = cycles.slice(0, 10).map(c => ({
        name: c.immatriculation,
        duree: Math.round(c.duree_total),
      }));
      setData(formatted);
    });
  }, []);

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h2 className="text-lg font-semibold mb-4">Durée des derniers cycles (minutes)</h2>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="duree" fill="#1d4ed8" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
```

### `frontend/src/components/mobile/AgentCapture.tsx`

```tsx
import { useState, useEffect } from 'react';
import { Camera, AlertTriangle, Check, MapPin } from 'lucide-react';
import { useCamera } from '@/hooks/useCamera';
import type { DelayCause } from '@/types';

interface Props {
  poste: 'porte_usine' | 'parking' | 'bascule' | 'ensachage';
  agentId: string;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export function AgentCapture({ poste, agentId }: Props) {
  const { photo, file, inputRef, triggerCapture, handleCapture, clearPhoto } = useCamera();
  const [causes, setCauses] = useState<DelayCause[]>([]);
  const [selectedCause, setSelectedCause] = useState<number | null>(null);
  const [newCauseName, setNewCauseName] = useState('');
  const [showNewCauseInput, setShowNewCauseInput] = useState(false);
  const [plaque, setPlaque] = useState('');
  const [typeEvent, setTypeEvent] = useState<'entree' | 'sortie'>('entree');
  const [minutesRetard, setMinutesRetard] = useState(0);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/mobile/delay-causes?poste=${poste}&active_only=true`)
      .then(r => r.json())
      .then(data => setCauses(data.sort((a: DelayCause, b: DelayCause) => b.usage_count - a.usage_count)));
  }, [poste]);

  const handleAddNewCause = async () => {
    if (!newCauseName.trim()) return;
    const res = await fetch(`${API_BASE}/api/mobile/delay-causes`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nom: newCauseName, poste_concerne: poste, created_by: agentId })
    });
    const newCause = await res.json();
    setCauses([newCause, ...causes]);
    setSelectedCause(newCause.id);
    setShowNewCauseInput(false);
    setNewCauseName('');
  };

  const handleSubmit = async () => {
    if (!plaque.trim()) return;
    setLoading(true);

    const formData = new FormData();
    formData.append('plaque', plaque.toUpperCase().trim());
    formData.append('poste', poste);
    formData.append('type_event', typeEvent);
    formData.append('agent_id', agentId);
    if (selectedCause) formData.append('delay_cause_id', String(selectedCause));
    if (minutesRetard > 0) formData.append('minutes_retard', String(minutesRetard));

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        pos => {
          formData.append('gps_lat', String(pos.coords.latitude));
          formData.append('gps_lon', String(pos.coords.longitude));
        }, () => {}, { timeout: 3000 }
      );
    }
    if (file) formData.append('photo', file);

    await fetch(`${API_BASE}/api/mobile/events`, { method: 'POST', body: formData });

    setLoading(false);
    setSuccess(true);
    setTimeout(() => {
      setSuccess(false);
      setPlaque('');
      setSelectedCause(null);
      setMinutesRetard(0);
      clearPhoto();
    }, 2000);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4 space-y-4 pb-24">
      <div className="bg-white rounded-xl p-4 shadow-sm flex items-center gap-3">
        <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
          <MapPin className="w-5 h-5 text-blue-600" />
        </div>
        <div>
          <h2 className="font-bold text-gray-900 capitalize">{poste.replace('_', ' ')}</h2>
          <p className="text-xs text-gray-500">Agent: {agentId}</p>
        </div>
      </div>

      <div className="bg-white rounded-xl p-4 shadow-sm space-y-3">
        <label className="text-sm font-medium text-gray-700">Immatriculation</label>
        <div className="flex gap-2">
          <input type="text" value={plaque} onChange={e => setPlaque(e.target.value)}
            placeholder="ex: 45231-أ-12"
            className="flex-1 border rounded-lg px-3 py-3 text-lg font-mono uppercase" />
          <button onClick={triggerCapture} className="bg-blue-600 text-white px-4 rounded-lg flex items-center gap-2">
            <Camera className="w-5 h-5" />
          </button>
        </div>
        <input ref={inputRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={handleCapture} />
        {photo && <img src={photo} alt="Plaque" className="w-full h-32  object-cover rounded-lg" />}
      </div>

      <div className="bg-white rounded-xl p-4 shadow-sm space-y-3">
        <label className="text-sm font-medium text-gray-700">Type d'événement</label>
        <div className="grid grid-cols-2 gap-2">
          <button onClick={() => setTypeEvent('entree')} className={`py-3 rounded-lg font-medium transition ${typeEvent === 'entree' ? 'bg-green-600 text-white' : 'bg-gray-100 text-gray-600'}`}>Entrée</button>
          <button onClick={() => setTypeEvent('sortie')} className={`py-3 rounded-lg font-medium transition ${typeEvent === 'sortie' ? 'bg-orange-600 text-white' : 'bg-gray-100 text-gray-600'}`}>Sortie</button>
        </div>
      </div>

      <div className="bg-white rounded-xl p-4 shadow-sm space-y-3">
        <div className="flex items-center gap-2 text-orange-600">
          <AlertTriangle className="w-5 h-5" />
          <h3 className="font-medium">Signaler un retard (optionnel)</h3>
        </div>
        <div className="space-y-2">
          <label className="text-sm text-gray-600">Cause identifiée</label>
          {showNewCauseInput ? (
            <div className="flex gap-2">
              <input type="text" value={newCauseName} onChange={e => setNewCauseName(e.target.value)} placeholder="Nouvelle cause..." className="flex-1 border rounded-lg px-3 py-2 text-sm" autoFocus />
              <button onClick={handleAddNewCause} className="bg-green-600 text-white px-3 rounded-lg text-sm"><Check className="w-4 h-4" /></button>
            </div>
          ) : (
            <select value={selectedCause || ''} onChange={e => { if (e.target.value === '__new__') setShowNewCauseInput(true); else setSelectedCause(Number(e.target.value) || null); }} className="w-full border rounded-lg px-3 py-3 text-sm bg-white">
              <option value="">Aucun retard</option>
              {causes.map(c => <option key={c.id} value={c.id}>{c.nom} {c.usage_count > 0 ? `(${c.usage_count}×)` : ''}</option>)}
              <option value="__new__">➕ Ajouter une nouvelle cause...</option>
            </select>
          )}
        </div>
        {selectedCause && (
          <div className="space-y-2">
            <label className="text-sm text-gray-600">Minutes de retard: <span className="font-bold text-orange-600">{minutesRetard} min</span></label>
            <input type="range" min="0" max="120" step="5" value={minutesRetard} onChange={e => setMinutesRetard(Number(e.target.value))} className="w-full" />
            <div className="flex justify-between text-xs text-gray-400"><span>0</span><span>60</span><span>120</span></div>
          </div>
        )}
      </div>

      <button onClick={handleSubmit} disabled={!plaque.trim() || loading} className={`w-full py-4 rounded-xl font-bold text-lg transition shadow-lg ${success ? 'bg-green-500 text-white' : 'bg-blue-700 text-white active:scale-95 disabled:opacity-50'}`}>
        {loading ? 'Enregistrement...' : success ? '✅ Enregistré !' : "Valider l'événement"}
      </button>
    </div>
  );
}
```

### `frontend/src/components/TruckCard.tsx`

```tsx
import { Truck, MapPin, Clock } from 'lucide-react';
import type { Event } from '@/types';

interface Props { event: Event; }

const posteLabels: Record<string, string> = {
  porte_usine: 'Porte Usine', parking: 'Parking',
  bascule: 'Bascule', ensachage: 'Ensachage',
};

export function TruckCard({ event }: Props) {
  return (
    <div className="bg-white border rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Truck className="w-5 h-5 text-blue-600" />
          <span className="font-mono font-bold text-lg">{event.truck?.immatriculation || 'Inconnu'}</span>
        </div>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${event.type_event === 'entree' ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'}`}>
          {event.type_event === 'entree' ? 'Entrée' : 'Sortie'}
        </span>
      </div>
      <div className="space-y-1 text-sm text-gray-600">
        <div className="flex items-center gap-2"><MapPin className="w-4 h-4" /><span>{posteLabels[event.poste] || event.poste}</span></div>
        <div className="flex items-center gap-2"><Clock className="w-4 h-4" /><span>{new Date(event.horodatage).toLocaleTimeString('fr-FR')}</span></div>
        {event.source !== 'camera' && <span className="text-xs text-blue-600">Source: {event.source}</span>}
      </div>
      {event.cause?.nom && (
        <div className="mt-2 p-2 bg-red-50 rounded text-xs text-red-700">
          ⚠️ {event.cause.nom} {event.minutes_retard ? `(${event.minutes_retard} min)` : ''}
        </div>
      )}
    </div>
  );
}
```

### `frontend/src/pages/Dashboard.tsx`

```tsx
import { useEffect, useState } from 'react';
import { getDashboardStats, getActiveEvents } from '@/services/api';
import { useWebSocket } from '@/hooks/useWebSocket';
import { TruckCard } from '@/components/TruckCard';
import { AlertBanner } from '@/components/AlertBanner';
import { StatsChart } from '@/components/StatsChart';
import type { DashboardStats, Event } from '@/types';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/live';

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const { lastMessage, isConnected } = useWebSocket(WS_URL);

  useEffect(() => {
    getDashboardStats().then(setStats);
    getActiveEvents().then(setEvents);
  }, []);

  useEffect(() => {
    if (lastMessage) {
      getDashboardStats().then(setStats);
      getActiveEvents().then(setEvents);
    }
  }, [lastMessage]);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">🏭 Dashboard Temps Réel — LafargeHolcim Meknès</h1>
        <div className={`px-3 py-1 rounded-full text-sm font-medium ${isConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
          {isConnected ? '● Connecté' : '● Déconnecté'}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <KPICard title="Camions en cours" value={stats?.camions_en_cours || 0} color="blue" />
        <KPICard title="Aujourd'hui" value={stats?.camions_aujourdhui || 0} color="green" />
        <KPICard title="Temps moyen cycle" value={`${Math.round(stats?.temps_moyen_cycle || 0)} min`} color="purple" />
        <KPICard title="Alertes actives" value={stats?.alertes_actives || 0} color="red" />
      </div>

      {stats?.poste_bloquant && <AlertBanner message={`⚠️ Poste bloquant : ${stats.poste_bloquant}`} type="warning" />}
      {stats?.top_cause_retard && <AlertBanner message={`🔥 Cause fréquente : ${stats.top_cause_retard}`} type="info" />}

      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-lg font-semibold mb-4">Camions actuellement dans l'usine</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {events.map(ev => <TruckCard key={ev.id} event={ev} />)}
        </div>
      </div>

      <StatsChart />
    </div>
  );
}

function KPICard({ title, value, color }: { title: string; value: string | number; color: string }) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-900', green: 'bg-green-50 text-green-900',
    purple: 'bg-purple-50 text-purple-900', red: 'bg-red-50 text-red-900',
  };
  return (
    <div className={`rounded-lg p-4 ${colors[color]}`}>
      <p className="text-sm opacity-75">{title}</p>
      <p className="text-3xl font-bold">{value}</p>
    </div>
  );
}
```

### `frontend/src/pages/MobilePage.tsx`

```tsx
import { useState } from 'react';
import { AgentCapture } from '@/components/mobile/AgentCapture';

export default function MobilePage() {
  const [poste, setPoste] = useState<'porte_usine' | 'parking' | 'bascule' | 'ensachage'>('parking');
  const [agentId, setAgentId] = useState('agent_01');

  return (
    <div className="max-w-md mx-auto bg-gray-100 min-h-screen">
      <div className="p-4 bg-blue-700 text-white flex justify-between items-center">
        <h1 className="font-bold">Lafarge Mobile</h1>
        <select 
          value={poste} 
          onChange={e => setPoste(e.target.value as any)}
          className="bg-blue-800 text-white text-sm rounded p-1 border-none"
        >
          <option value="porte_usine">Porte Usine</option>
          <option value="parking">Parking</option>
          <option value="bascule">Bascule</option>
          <option value="ensachage">Ensachage</option>
        </select>
      </div>
      <AgentCapture poste={poste} agentId={agentId} />
    </div>
  );
}
```

### `frontend/src/App.tsx`

```tsx
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import Dashboard from '@/pages/Dashboard';
import MobilePage from '@/pages/MobilePage';

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-100">
        <nav className="bg-white shadow-sm p-4 flex gap-4">
          <Link to="/" className="text-blue-700 font-bold hover:underline">Dashboard</Link>
          <Link to="/mobile" className="text-blue-700 font-bold hover:underline">Interface Mobile</Link>
        </nav>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/mobile" element={<MobilePage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
```

### `frontend/src/main.tsx`

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```


---

## 🐳 Docker & Déploiement

### `docker-compose.yml`

```yaml
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    container_name: lafarge_db
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-lafarge_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-password}
      POSTGRES_DB: ${POSTGRES_DB:-lafarge_tracker}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-lafarge_user}"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: lafarge_redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: lafarge_backend
    restart: unless-stopped
    env_file:
      - .env
    environment:
      POSTGRES_HOST: db
      REDIS_HOST: redis
    ports:
      - "8000:8000"
    volumes:
      - ./backend/app:/app/app
      - ./models:/app/models
      - ./uploads:/app/uploads          # Photos agent mobile
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: lafarge_frontend
    restart: unless-stopped
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  postgres_data:
  redis_data:
```

### `backend/Dockerfile`

```dockerfile
FROM python:3.11.9-slim

# Installation des dépendances runtime et de la toolchain de compilation pour Prophet/cmdstanpy
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 \
    libxrender-dev libgomp1 tesseract-ocr \
    build-essential g++ cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN mkdir -p uploads models

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### `frontend/Dockerfile`

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### `frontend/nginx.conf`

```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /ws/ {
        proxy_pass http://backend:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```


---

## 🖥️ Guide d'installation pas à pas

### Étape 0 : Prérequis

```bash
python --version        # Python 3.11.9
node --version          # v20.x ou +
docker --version        # 24.x ou +
docker-compose --version
```

### Étape 1 : Cloner et structurer

```bash
mkdir lafarge-camion-tracker && cd lafarge-camion-tracker
git init
mkdir -p backend/app/{routers,services,simulation}
mkdir -p backend/tests
mkdir -p frontend/src/{components/mobile,pages,hooks,services,types}
mkdir -p scripts uploads docs

touch backend/app/__init__.py
 touch backend/app/routers/__init__.py
 touch backend/app/services/__init__.py
 touch backend/app/simulation/__init__.py
```

### Étape 2 : Configuration environnement

```bash
cp .env.example .env
# Éditer .env : CV_MODE=simulation, pas besoin de vraies URLs caméra
```

### Étape 3 : Backend

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
cd ..
```

### Étape 4 : Initialisation DB

```bash
docker-compose up -d db redis
sleep 5
cd scripts
python init_db.py
cd ..
```

### Étape 5 : Lancer le backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Test : curl http://localhost:8000/health
```

### Étape 6 : Frontend

```bash
cd frontend
npm install
npm run dev
# Accessible sur http://localhost:5173
```

### Étape 7 : Docker complet (production)

```bash
docker-compose up --build -d
docker-compose ps
docker-compose logs -f backend
```

---

## 📱 PWA Agent Mobile

### Pourquoi une PWA ?

- **Pas de store** : l'agent ouvre l'URL dans Chrome/Safari
- **Ajouter à l'écran d'accueil** : icône native, plein écran
- **Accès caméra** : `capture="environment"` pour scanner les plaques
- **Coût zéro** : les opérateurs ont déjà leur téléphone

### Configuration Vite PWA

```bash
cd frontend
npm install vite-plugin-pwa -D
```

Modifier `frontend/vite.config.ts` :

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Lafarge Tracker',
        short_name: 'Lafarge',
        description: 'Traçabilité camions LafargeHolcim Meknès',
        theme_color: '#1d4ed8',
        background_color: '#ffffff',
        display: 'standalone',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' }
        ]
      }
    })
  ]
})
```

### Auth par PIN (rapide et pragmatique)

Pas de login/mot de passe complexe. Un **PIN à 4 chiffres par poste** :

| Poste | PIN |
|-------|-----|
| Porte Usine | 1001 |
| Parking | 1002 |
| Bascule | 1003 |
| Ensachage | 1004 |

L'agent entre son PIN → l'app récupère le poste automatiquement.

### Mode Offline (basique)

Pour les zones sans réseau en usine, utiliser `navigator.serviceWorker` + `Background Sync` :

```typescript
// Simplifié : file d'attente de requêtes
const offlineQueue: any[] = [];

window.addEventListener('online', () => {
  offlineQueue.forEach(req => fetch(req.url, req.options));
  offlineQueue.length = 0;
});
```

---

## 🚀 Prochaines étapes suggérées

1. **Semaine 1** : Implémenter les routers FastAPI + router mobile + migration bi-mode
2. **Semaine 2** : Connecter EventIngestionService au WebSocket + simulation cohérente
3. **Semaine 3** : Dashboard causes de retard (Pareto, Top 5) + PWA mobile
4. **Semaine 4** : Prophet production + toggle XGBoost expérimental + heatmap horaire
5. **Semaine 5** : Tests + Docker + déploiement usine + soutenance

---

## 🎓 Phrase d'accroche pour la soutenance

> *"J'ai conçu un système bi-mode qui fonctionne pleinement dès le premier jour sans aucune donnée historique. Il mixe caméras fixes et agents mobiles selon les contraintes terrain de chaque poste. Les causes de retard sont créables à la volée par les opérateurs, ce qui nous permet de découvrir les vrais goulots d'étranglement de l'usine. Prophet assure la stabilité en production, tandis qu'un XGBoost expérimental permet de valider les gains potentiels avant bascule automatique."*

---

## 📝 Changements majeurs par rapport à V1

| Aspect | V1 | V2 |
|--------|-----|-----|
| **Sources événements** | Caméra RTSP uniquement | Bi-mode : caméra + agent mobile |
| **Causes retard** | Liste figée | Table dynamique, créable à la volée |
| **ML** | XGBoost/LightGBM/Prophet en compétition | Prophet production, XGBoost toggle expérimental |
| **Simulation** | Événements aléatoires | Logique de cycle respectée (porte→parking→bascule→ensachage→bascule→porte) |
| **Ingestion** | Chaque source crée ses Events | EventIngestionService unique avec déduplication |
| **Déploiement** | Desktop uniquement | PWA mobile pour agents terrain |
| **Dashboard** | Temps réel simple | + Top causes retard, heatmap, Pareto |

---

> **Document généré pour le stage LafargeHolcim Meknès — 2026**
> Architecture Zero-to-Hero V2 : opérationnel jour 1, intelligent après 1 mois, bi-mode dès le déploiement.
