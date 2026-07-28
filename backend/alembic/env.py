"""
Alembic env.py — Configuration de l'environnement de migration.
Lit dynamiquement l'URL DB depuis app.config pour être cohérent avec le backend.
"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# --- Import des modèles et de la config app ---
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings
from app.models import Base  # importer Base pour que tous les modèles soient connus

# Objet de configuration Alembic
config = context.config

# Injecter l'URL DB depuis notre config applicative (évite la duplication)
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.get_database_url)

# Configuration du logging depuis le fichier alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata cible pour autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Mode offline : génère le SQL sans connexion DB.
    Utile pour inspecter les migrations avant de les appliquer.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,           # Détecte les changements de type
        compare_server_default=True, # Détecte les changements de valeur par défaut
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Mode online : se connecte à la DB et applique les migrations.
    C'est le mode utilisé par `alembic upgrade head`.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
