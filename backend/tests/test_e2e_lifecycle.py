"""
Tests End-to-End (E2E) : Simulation du cycle de vie complet d'un camion.
Vérifie la transition des états : ENTRÉE PORTE -> PARKING -> BASCULE -> ENSACHAGE -> SORTIE.
"""
import pytest
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.services.event_ingestion import EventIngestionService
from app.models import Cycle, Event, Truck, TruckStatus, PosteType


def test_complete_truck_lifecycle():
    """Simule le parcours complet d'un camion et vérifie la fermeture et le calcul du cycle."""
    db = SessionLocal()
    try:
        service = EventIngestionService(db)
        plaque_test = "99999-T-99"
        base_time = datetime.utcnow() - timedelta(minutes=90)

        # 1. Entrée Porte Usine
        ev1 = service.ingest_event(
            plaque=plaque_test,
            poste=PosteType.PORTE_USINE,
            type_event="entree",
            source="test_e2e",
            horodatage=base_time
        )
        assert ev1.id is not None

        # Vérifier que le cycle est créé avec statut EN_COURS
        cycle = db.query(Cycle).join(Truck).filter(
            Truck.immatriculation == plaque_test,
            Cycle.status == TruckStatus.EN_COURS
        ).first()
        assert cycle is not None
        assert cycle.status == TruckStatus.EN_COURS

        # 2. Parking (Entrée puis Sortie après 20 min)
        service.ingest_event(
            plaque=plaque_test,
            poste=PosteType.PARKING,
            type_event="entree",
            source="test_e2e",
            horodatage=base_time + timedelta(minutes=5)
        )
        service.ingest_event(
            plaque=plaque_test,
            poste=PosteType.PARKING,
            type_event="sortie",
            source="test_e2e",
            horodatage=base_time + timedelta(minutes=25)
        )

        # 3. Bascule Tare (Pesage 10 min)
        service.ingest_event(
            plaque=plaque_test,
            poste=PosteType.BASCULE,
            type_event="entree",
            source="test_e2e",
            horodatage=base_time + timedelta(minutes=30)
        )
        service.ingest_event(
            plaque=plaque_test,
            poste=PosteType.BASCULE,
            type_event="sortie",
            source="test_e2e",
            horodatage=base_time + timedelta(minutes=40)
        )

        # 4. Ensachage (Chargement 35 min)
        service.ingest_event(
            plaque=plaque_test,
            poste=PosteType.ENSACHAGE,
            type_event="entree",
            source="test_e2e",
            horodatage=base_time + timedelta(minutes=45)
        )
        service.ingest_event(
            plaque=plaque_test,
            poste=PosteType.ENSACHAGE,
            type_event="sortie",
            source="test_e2e",
            horodatage=base_time + timedelta(minutes=80)
        )

        # 5. Sortie Porte Usine (Fermeture du cycle)
        ev_fin = service.ingest_event(
            plaque=plaque_test,
            poste=PosteType.PORTE_USINE,
            type_event="sortie",
            source="test_e2e",
            horodatage=base_time + timedelta(minutes=90)
        )
        assert ev_fin.id is not None

        # Vérifier que le cycle est passé à statut TERMINE avec calcul des durées
        db.refresh(cycle)
        assert cycle.status == TruckStatus.TERMINE
        assert cycle.sortie_porte is not None
        assert cycle.duree_total >= 80.0

    finally:
        # Nettoyage des données du test E2E
        truck = db.query(Truck).filter(Truck.immatriculation == plaque_test).first()
        if truck:
            db.query(Event).filter(Event.truck_id == truck.id).delete()
            db.query(Cycle).filter(Cycle.truck_id == truck.id).delete()
            db.delete(truck)
            db.commit()
        db.close()
