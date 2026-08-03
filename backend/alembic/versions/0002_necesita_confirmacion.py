"""Ajout colonne necesita_confirmacion sur la table events

Revision ID: 0002_necesita_confirmacion
Revises: 0001_baseline
Create Date: 2026-08-03

Contexte :
  Le système OCR crée des événements avec une confiance entre 0.45 et 0.65.
  Ces événements sont trop incertains pour être acceptés automatiquement,
  mais pas assez mauvais pour être rejetés silencieusement.
  Ce flag marque les events qui attendent une validation humaine.
  Il est mis à True à la création, et à False après confirmation par un agent.
"""
from alembic import op
import sqlalchemy as sa

revision: str = '0002_necesita_confirmacion'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD COLUMN IF NOT EXISTS : idempotent, safe sur base existante avec données
    op.execute("""
        ALTER TABLE events
        ADD COLUMN IF NOT EXISTS necesita_confirmacion BOOLEAN NOT NULL DEFAULT FALSE;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE events DROP COLUMN IF EXISTS necesita_confirmacion;
    """)
