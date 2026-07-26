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
