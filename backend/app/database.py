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
