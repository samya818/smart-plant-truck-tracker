"""
Test de Concurrence et de Race Condition — Ingestion Parallèle Caméra vs Agent Mobile.
Valide que :
1. Deux ingestions simultanées pour le même camion convergent vers un seul événement/cycle (fusion hybride).
2. L'idempotence basée sur client_event_id fonctionne sous charge parallèle.
"""
import pytest
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import sessionmaker
from app.models import Event, Truck, Cycle, PosteType, TruckStatus
from app.services.event_ingestion import EventIngestionService

def test_concurrent_camera_and_agent_race(db_session, test_db_engine):
    """
    Simule une capture caméra et une saisie mobile arrivant EXACTEMENT en même temps (threads concurrents).
    Vérifie qu'un seul événement principal est créé et qu'aucun doublon de cycle n'est généré.
    """
    SessionLocal = sessionmaker(bind=test_db_engine)
    plaque = "RACE-12345"

    def ingest_task(source, agent_id=None):
        sess = SessionLocal()
        try:
            service = EventIngestionService(sess)
            event = service.ingest_event(
                plaque=plaque,
                poste=PosteType.PORTE_USINE,
                type_event="entree",
                source=source,
                agent_id=agent_id,
            )
            return event.id
        finally:
            sess.close()

    # Lancement simultané de 2 threads
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_camera = executor.submit(ingest_task, "camera")
        f_agent = executor.submit(ingest_task, "agent_mobile", "AGENT_RACE")
        res_camera = f_camera.result()
        res_agent = f_agent.result()

    # Vérification en DB
    truck = db_session.query(Truck).filter(Truck.immatriculation == plaque).first()
    assert truck is not None

    events = db_session.query(Event).filter(Event.truck_id == truck.id).all()
    # Le mécanisme de debounce/idempotence doit garantir au plus 1 événement ou une fusion hybride
    assert len(events) == 1
    assert events[0].source in ("camera", "agent_mobile", "hybrid")

    # Un seul cycle EN_COURS
    cycles = db_session.query(Cycle).filter(Cycle.truck_id == truck.id).all()
    assert len(cycles) == 1
    assert cycles[0].status == TruckStatus.EN_COURS


def test_idempotent_offline_replay_concurrency(db_session, test_db_engine):
    """
    Simule l'envoi répété d'un même événement offline avec le même client_event_id (re-jeu multiple du SW).
    """
    SessionLocal = sessionmaker(bind=test_db_engine)
    client_uuid = "client-uuid-test-999"
    plaque = "OFFLINE-99"

    def replay_task():
        sess = SessionLocal()
        try:
            service = EventIngestionService(sess)
            event = service.ingest_event(
                plaque=plaque,
                poste=PosteType.PARKING,
                type_event="entree",
                source="agent_mobile",
                client_event_id=client_uuid,
            )
            return event.id
        finally:
            sess.close()

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(replay_task) for _ in range(4)]
        event_ids = [f.result() for f in futures]

    # Tous les threads doivent avoir retourné le MÊME event ID
    assert len(set(event_ids)) == 1

    # Un seul enregistrement en DB pour ce client_event_id
    matching_events = db_session.query(Event).filter(Event.client_event_id == client_uuid).all()
    assert len(matching_events) == 1
