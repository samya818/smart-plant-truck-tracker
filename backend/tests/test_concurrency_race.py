"""
Test de Race Condition et Idempotence — Ingestion Parallèle Caméra vs Agent Mobile.

Note sur la stratégie de test:
  SQLite en mémoire avec StaticPool ne supporte pas les commits parallèles
  de vraies transactions concurrentes (limitation SQLite). Ce fichier teste
  donc la SÉMANTIQUE anti-doublon de deux manières:
  - test_camera_vs_agent_sequential : deux ingestions séquentielles rapides
    depuis des sources différentes → vérifie que la logique de debounce
    produit exactement 1 cycle (identique à ce qui se passe en PostgreSQL).
  - test_idempotent_offline_replay_concurrency : 4 threads envoient le même
    client_event_id → vérifie l'idempotence (même résultat attendu en prod).
"""
import pytest
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import sessionmaker
from app.models import Event, Truck, Cycle, PosteType, TruckStatus
from app.services.event_ingestion import EventIngestionService


def test_camera_vs_agent_sequential(db):
    """
    Simule deux ingestions SÉQUENTIELLES pour le même camion depuis deux sources
    différentes (caméra puis agent mobile).

    Sémantique attendue (identique en prod avec PostgreSQL) :
    - La première ingestion crée le camion + 1 cycle EN_COURS.
    - La deuxième ingestion, pour le même poste/type dans la même fenêtre temporelle,
      est dédoublonnée → retourne l'événement existant (fusion hybride ou debounce).
    - Résultat final : 1 seul cycle EN_COURS pour ce camion.
    """
    plaque = "RACE-SEQ-001"
    service = EventIngestionService(db)

    # Première ingestion : caméra
    ev1 = service.ingest_event(
        plaque=plaque,
        poste=PosteType.PORTE_USINE,
        type_event="entree",
        source="camera",
    )

    # Deuxième ingestion immédiate : agent mobile (même camion, même poste, même type)
    ev2 = service.ingest_event(
        plaque=plaque,
        poste=PosteType.PORTE_USINE,
        type_event="entree",
        source="agent_mobile",
        agent_id="AGENT_RACE",
    )

    # Vérifications
    truck = db.query(Truck).filter(Truck.immatriculation == plaque).first()
    assert truck is not None, "Le camion doit être créé"

    events = db.query(Event).filter(Event.truck_id == truck.id).all()
    # Debounce/fusion : au plus 1 événement principal (pas de doublon de cycle)
    assert len(events) == 1, f"Attendu 1 événement, obtenu {len(events)}"
    assert events[0].source in ("camera", "agent_mobile", "hybrid")

    # Un seul cycle EN_COURS
    cycles = db.query(Cycle).filter(Cycle.truck_id == truck.id).all()
    assert len(cycles) == 1, f"Attendu 1 cycle, obtenu {len(cycles)}"
    assert cycles[0].status == TruckStatus.EN_COURS


def test_idempotent_offline_replay_concurrency(db, engine):
    """
    Simule le re-jeu répété d'un même événement offline avec le même client_event_id
    (comportement du Service Worker : retransmission automatique).

    Vérifie que l'idempotence basée sur client_event_id fonctionne sous charge
    parallèle : 4 threads envoient le même UUID → même event ID retourné partout,
    1 seul enregistrement en base.
    """
    client_uuid = "client-uuid-test-999"
    plaque = "OFFLINE-99"

    # Pré-créer le camion dans la session principale via une première ingestion séquentielle,
    # pour éviter la race condition sur l'INSERT Truck entre threads.
    pre_service = EventIngestionService(db)
    pre_service.ingest_event(
        plaque=plaque,
        poste=PosteType.PARKING,
        type_event="entree",
        source="agent_mobile",
        client_event_id="pre-create-truck-seed",
    )
    db.commit()

    SessionLocal = sessionmaker(bind=engine)

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
    assert len(set(event_ids)) == 1, \
        f"Idempotence brisée : {len(set(event_ids))} ID distincts retournés"

    # Un seul enregistrement en DB pour ce client_event_id
    sess_check = SessionLocal()
    try:
        matching_events = sess_check.query(Event).filter(
            Event.client_event_id == client_uuid
        ).all()
        assert len(matching_events) == 1, \
            f"Attendu 1 event en DB, obtenu {len(matching_events)}"
    finally:
        sess_check.close()
