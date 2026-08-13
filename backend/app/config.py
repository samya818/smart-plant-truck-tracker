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
    sim_speed_multiplier: float = 60.0  # 1 seconde simulée = 1 minute réelle

    seuil_attente_parking_max: int = 30
    seuil_bascule_max: int = 15
    seuil_ensachage_max: int = 45
    seuil_cycle_total_max: int = 120

    upload_dir: str = "./uploads"
    max_upload_size: int = 5 * 1024 * 1024  # 5MB

    @property
    def get_database_url(self) -> str:
        """Génère dynamiquement l'URL de connexion PostgreSQL ou SQLite fallback."""
        if self.database_url:
            return self.database_url
        if self.postgres_host:
            return f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        return "sqlite:///./lafarge_local.db"

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
