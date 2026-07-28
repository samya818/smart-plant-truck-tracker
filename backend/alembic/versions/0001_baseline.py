"""Schema initial complet — baseline LafargeHolcim Tracker

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-07-28 00:00:00

Capture l'état exact de la base au moment de l'intégration Alembic.
Toutes les migrations futures s'appuieront sur cette baseline.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001_baseline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ────────────────────────────────────────────────────────────────
    postetype = postgresql.ENUM(
        'porte_usine', 'parking', 'bascule', 'ensachage',
        name='postetype', create_type=False
    )
    capturemode = postgresql.ENUM(
        'camera', 'agent', 'hybrid',
        name='capturemode', create_type=False
    )
    truckstatus = postgresql.ENUM(
        'EN_COURS', 'TERMINE', 'ANOMALIE', 'EXPIRE',
        name='truckstatus', create_type=False
    )

    # Créer les enums s'ils n'existent pas
    op.execute("DO $$ BEGIN CREATE TYPE postetype AS ENUM ('porte_usine','parking','bascule','ensachage'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE capturemode AS ENUM ('camera','agent','hybrid'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE truckstatus AS ENUM ('EN_COURS','TERMINE','ANOMALIE','EXPIRE'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    # Ajouter EXPIRE si manquant (base existante avant Alembic)
    op.execute("DO $$ BEGIN ALTER TYPE truckstatus ADD VALUE IF NOT EXISTS 'EXPIRE'; EXCEPTION WHEN others THEN NULL; END $$;")

    # ── Table transporteurs ──────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS transporteurs (
            id         SERIAL PRIMARY KEY,
            nom        VARCHAR(100) NOT NULL,
            contact    VARCHAR(100),
            est_actif  BOOLEAN DEFAULT TRUE,
            est_whitelist BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    # ── Table trucks ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS trucks (
            id               SERIAL PRIMARY KEY,
            immatriculation  VARCHAR(20) UNIQUE NOT NULL,
            transporteur_id  INTEGER REFERENCES transporteurs(id),
            type_camion      VARCHAR(50) DEFAULT 'standard'
        )
    """)

    # ── Table delay_causes ───────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS delay_causes (
            id              SERIAL PRIMARY KEY,
            nom             VARCHAR(100) UNIQUE NOT NULL,
            description     TEXT,
            poste_concerne  postetype,
            usage_count     INTEGER DEFAULT 0,
            is_active       BOOLEAN DEFAULT TRUE,
            created_by      VARCHAR(50) DEFAULT 'system',
            created_at      TIMESTAMPTZ DEFAULT now()
        )
    """)

    # ── Table events ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id                   SERIAL PRIMARY KEY,
            truck_id             INTEGER NOT NULL REFERENCES trucks(id),
            poste                postetype NOT NULL,
            type_event           VARCHAR(10) NOT NULL,
            horodatage           TIMESTAMPTZ DEFAULT now(),
            source               VARCHAR(20) DEFAULT 'camera',
            agent_id             VARCHAR(50),
            delay_cause_id       INTEGER REFERENCES delay_causes(id),
            cause_retard_libre   TEXT,
            minutes_retard       INTEGER,
            confiance_detection  FLOAT,
            confiance_ocr        FLOAT,
            image_path           VARCHAR(255),
            gps_lat              FLOAT,
            gps_lon              FLOAT
        )
    """)

    # ── Table cycles ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS cycles (
            id                 SERIAL PRIMARY KEY,
            truck_id           INTEGER NOT NULL REFERENCES trucks(id),
            entree_porte       TIMESTAMPTZ NOT NULL,
            sortie_porte       TIMESTAMPTZ,
            duree_parking      FLOAT DEFAULT 0.0,
            duree_bascule_tare FLOAT DEFAULT 0.0,
            duree_ensachage    FLOAT DEFAULT 0.0,
            duree_bascule_brut FLOAT DEFAULT 0.0,
            duree_total        FLOAT DEFAULT 0.0,
            status             truckstatus DEFAULT 'EN_COURS',
            est_anomalie       BOOLEAN DEFAULT FALSE,
            auto_closed        BOOLEAN DEFAULT FALSE,
            gap_applique       FLOAT
        )
    """)

    # ── Table poste_configs ──────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS poste_configs (
            poste              postetype PRIMARY KEY,
            capture_mode       capturemode DEFAULT 'camera',
            camera_url         VARCHAR(255),
            camera_active      BOOLEAN DEFAULT TRUE,
            agent_pin          VARCHAR(10),
            qr_code_value      VARCHAR(100),
            seuil_attente_max  INTEGER DEFAULT 30,
            is_active          BOOLEAN DEFAULT TRUE,
            updated_at         TIMESTAMPTZ
        )
    """)

    # ── Table etape_configs ──────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS etape_configs (
            id            SERIAL PRIMARY KEY,
            ordre         INTEGER NOT NULL DEFAULT 0,
            code          VARCHAR(50) UNIQUE NOT NULL,
            nom           VARCHAR(100) NOT NULL,
            description   VARCHAR(255),
            seuil_minutes INTEGER NOT NULL DEFAULT 30,
            poste_ref     VARCHAR(50),
            is_active     BOOLEAN DEFAULT TRUE,
            is_default    BOOLEAN DEFAULT FALSE,
            is_custom     BOOLEAN DEFAULT FALSE,
            created_at    TIMESTAMPTZ DEFAULT now(),
            updated_at    TIMESTAMPTZ
        )
    """)

    # ── Migrations additionnelles pour bases existantes ───────────────────────
    # auto_closed
    op.execute("""
        ALTER TABLE cycles ADD COLUMN IF NOT EXISTS auto_closed BOOLEAN DEFAULT FALSE;
    """)
    # gap_applique
    op.execute("""
        ALTER TABLE cycles ADD COLUMN IF NOT EXISTS gap_applique FLOAT;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS etape_configs CASCADE")
    op.execute("DROP TABLE IF EXISTS poste_configs CASCADE")
    op.execute("DROP TABLE IF EXISTS cycles CASCADE")
    op.execute("DROP TABLE IF EXISTS events CASCADE")
    op.execute("DROP TABLE IF EXISTS delay_causes CASCADE")
    op.execute("DROP TABLE IF EXISTS trucks CASCADE")
    op.execute("DROP TABLE IF EXISTS transporteurs CASCADE")
    op.execute("DROP TYPE IF EXISTS truckstatus")
    op.execute("DROP TYPE IF EXISTS capturemode")
    op.execute("DROP TYPE IF EXISTS postetype")
