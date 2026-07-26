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
