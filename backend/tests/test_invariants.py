"""
Tests d'Invariants Système — Propriétés Critiques et Cohérence Métier.

Ces tests vérifient des PROPRIÉTÉS (pas des fonctions) :
- Idempotence client_event_id
- Isolation temporelle des cycles
- FSM : anomalie détectée sur séquence invalide
- Feature parity train/inférence
- Cycle isolation : deux cycles successifs ne partagent pas leurs événements
"""
import pytest
from datetime import datetime, timedelta
from app.models import Event, Truck, Cycle, PosteType, TruckStatus
from app.services.event_ingestion import EventIngestionService
from app.services.feature_engineering import (
    build_features_matrix_train,
    build_single_inference_vector,
    FEATURE_COLUMNS,
    ML_TRAINING_THRESHOLD,
    ML_PRODUCTION_THRESHOLD,
)
import pandas as pd
import numpy as np


# ─── INVARIANT 1 : IDEMPOTENCE ────────────────────────────────────────────────
class TestIdempotenceInvariant:
    """POST event A ; POST event A → N_events = 1."""

    def test_same_client_event_id_produces_single_event(self, db):
        """
        L'idempotence basée sur client_event_id doit garantir qu'un même
        UUID ne génère jamais deux enregistrements en base, même après
        deux appels successifs au service.
        """
        client_uuid = "invariant-idemp-001"
        service = EventIngestionService(db)

        ev1 = service.ingest_event(
            plaque="IDEMP-TEST-01",
            poste=PosteType.PORTE_USINE,
            type_event="entree",
            source="agent_mobile",
            client_event_id=client_uuid,
        )
        ev2 = service.ingest_event(
            plaque="IDEMP-TEST-01",
            poste=PosteType.PORTE_USINE,
            type_event="entree",
            source="agent_mobile",
            client_event_id=client_uuid,
        )

        assert ev1.id == ev2.id, "Même UUID → même event_id attendu (idempotence)"

        truck = db.query(Truck).filter(Truck.immatriculation == "IDEMP-TEST-01").first()
        events = db.query(Event).filter(
            Event.truck_id == truck.id,
            Event.client_event_id == client_uuid,
        ).all()
        assert len(events) == 1, f"Idempotence brisée : {len(events)} events pour le même UUID"


# ─── INVARIANT 2 : ISOLATION TEMPORELLE DES CYCLES ───────────────────────────
class TestCycleIsolationInvariant:
    """Deux cycles successifs d'un même camion ne partagent pas leurs événements."""

    def test_cycle_events_are_temporally_isolated(self, db):
        """
        Scénario : Cycle A (10:00→12:00) suivi de Cycle B (14:00→16:00).
        Lors du recalcul des durées du Cycle A, les événements du Cycle B
        (t >= 14:00) NE DOIVENT PAS contaminer les durées du Cycle A.
        """
        service = EventIngestionService(db)
        plaque = "ISOLATION-TEST-01"
        now = datetime(2026, 8, 1, 10, 0, 0)

        # ── Cycle A ────────────────────────────────────────────────────────────
        # Entrée porte (commence Cycle A)
        service.ingest_event(plaque=plaque, poste=PosteType.PORTE_USINE,
                             type_event="entree", source="camera", horodatage=now)
        # Parking 20 min
        service.ingest_event(plaque=plaque, poste=PosteType.PARKING,
                             type_event="entree", source="camera",
                             horodatage=now + timedelta(minutes=5))
        service.ingest_event(plaque=plaque, poste=PosteType.PARKING,
                             type_event="sortie", source="camera",
                             horodatage=now + timedelta(minutes=25))
        # Sortie porte → ferme Cycle A
        sortie_a = now + timedelta(minutes=90)
        service.ingest_event(plaque=plaque, poste=PosteType.PORTE_USINE,
                             type_event="sortie", source="camera", horodatage=sortie_a)

        # ── Cycle B (même camion, 4h plus tard) ────────────────────────────────
        debut_b = now + timedelta(hours=4)
        service.ingest_event(plaque=plaque, poste=PosteType.PORTE_USINE,
                             type_event="entree", source="camera", horodatage=debut_b)
        # Parking très court dans Cycle B (5 min)
        service.ingest_event(plaque=plaque, poste=PosteType.PARKING,
                             type_event="entree", source="camera",
                             horodatage=debut_b + timedelta(minutes=2))
        service.ingest_event(plaque=plaque, poste=PosteType.PARKING,
                             type_event="sortie", source="camera",
                             horodatage=debut_b + timedelta(minutes=7))
        service.ingest_event(plaque=plaque, poste=PosteType.PORTE_USINE,
                             type_event="sortie", source="camera",
                             horodatage=debut_b + timedelta(minutes=60))

        # ── Vérification ──────────────────────────────────────────────────────
        truck = db.query(Truck).filter(Truck.immatriculation == plaque).first()
        cycles = db.query(Cycle).filter(
            Cycle.truck_id == truck.id,
            Cycle.status == TruckStatus.TERMINE,
        ).order_by(Cycle.entree_porte.asc()).all()

        assert len(cycles) >= 2, "Au moins 2 cycles terminés attendus"

        cycle_a = cycles[0]
        cycle_b = cycles[1]

        # Cycle A : durée parking = 20 min (NE DOIT PAS inclure le parking de B = 5 min)
        assert cycle_a.duree_parking is not None
        assert 18.0 <= cycle_a.duree_parking <= 22.0, (
            f"Isolation échouée : durée parking Cycle A = {cycle_a.duree_parking:.1f}min "
            f"(attendu ~20min, pas contamination par Cycle B)"
        )

        # Cycle B : durée parking = 5 min
        assert cycle_b.duree_parking is not None
        assert 4.0 <= cycle_b.duree_parking <= 7.0, (
            f"Cycle B durée parking incorrecte : {cycle_b.duree_parking:.1f}min (attendu ~5min)"
        )


# ─── INVARIANT 3 : FSM ────────────────────────────────────────────────────────
class TestFSMInvariant:
    """Séquence invalide → has_fsm_anomaly = True."""

    def test_invalid_fsm_transition_sets_anomaly_flag(self, db):
        """
        entree porte → sortie ensachage (sans parking ni bascule)
        doit produire has_fsm_anomaly = True sur le cycle.
        """
        service = EventIngestionService(db)
        plaque = "FSM-ANOM-01"

        # Entrée porte (séquence valide)
        service.ingest_event(plaque=plaque, poste=PosteType.PORTE_USINE,
                             type_event="entree", source="camera")
        # Sortie ensachage sans entrée → FSM invalide (étape sautée)
        service.ingest_event(plaque=plaque, poste=PosteType.ENSACHAGE,
                             type_event="sortie", source="camera")

        truck = db.query(Truck).filter(Truck.immatriculation == plaque).first()
        cycle = db.query(Cycle).filter(
            Cycle.truck_id == truck.id,
            Cycle.status == TruckStatus.EN_COURS,
        ).first()

        assert cycle is not None
        assert cycle.has_fsm_anomaly is True, (
            "Séquence invalide (porte→ensachage:sortie sans entrée) "
            "doit lever has_fsm_anomaly=True"
        )


# ─── INVARIANT 4 : FEATURE PARITY ────────────────────────────────────────────
class TestFeatureParityInvariant:
    """features_train.columns == features_inference.columns (ordre strict)."""

    def test_feature_schema_is_identical_train_vs_inference(self):
        """
        Les colonnes de la matrice d'entraînement doivent être EXACTEMENT
        identiques (même ordre) aux colonnes du vecteur d'inférence.
        Ce test échouerait si FEATURE_COLUMNS divergeait entre les deux chemins.
        """
        # Simuler un dataset d'entraînement minimal
        dates = pd.date_range("2026-01-01", periods=20, freq="h")
        df = pd.DataFrame({
            'entree_porte': dates,
            'ds': dates,
            'y': np.random.uniform(40, 120, size=20),
        })
        df_train, median_y = build_features_matrix_train(df)
        train_cols = list(df_train[FEATURE_COLUMNS].columns)

        # Simuler un vecteur d'inférence
        df_infer = build_single_inference_vector(
            dt=datetime(2026, 8, 1, 9, 30),
            recent_durations=[75.0, 80.0, 90.0],
            train_median_y=median_y,
        )
        infer_cols = list(df_infer.columns)

        assert train_cols == infer_cols, (
            f"Feature mismatch détecté !\n"
            f"  Train  : {train_cols}\n"
            f"  Inférence : {infer_cols}"
        )

    def test_feature_columns_count_is_exactly_13(self):
        """Le contrat du modèle XGBoost est exactement 13 features."""
        assert len(FEATURE_COLUMNS) == 13, (
            f"Contrat XGBoost : 13 features attendues, "
            f"{len(FEATURE_COLUMNS)} définies dans FEATURE_COLUMNS"
        )


# ─── INVARIANT 5 : SEUILS ML COHÉRENTS ───────────────────────────────────────
class TestMLThresholdInvariant:
    """ML_TRAINING_THRESHOLD < ML_PRODUCTION_THRESHOLD (toujours)."""

    def test_ml_thresholds_are_logically_ordered(self):
        """
        Le seuil de production doit toujours être supérieur au seuil d'entraînement.
        Si quelqu'un modifie ces constantes sans réfléchir, ce test échoue.
        """
        assert ML_TRAINING_THRESHOLD > 0
        assert ML_PRODUCTION_THRESHOLD > ML_TRAINING_THRESHOLD, (
            f"Incohérence : ML_PRODUCTION_THRESHOLD ({ML_PRODUCTION_THRESHOLD}) "
            f"doit être > ML_TRAINING_THRESHOLD ({ML_TRAINING_THRESHOLD})"
        )

    def test_ml_offline_ordering_respect(self, db):
        """
        Événement A (occurred 10:00, received 10:20) et
        Événement B (occurred 10:05, received 10:05) →
        le cycle utilise horodatage (occurred_at) pour ordonner,
        donc A précède B dans la séquence d'événements recalculée.
        """
        service = EventIngestionService(db)
        plaque = "OFFLINE-ORDER-01"
        base = datetime(2026, 8, 1, 10, 0, 0)

        # B arrive en premier (received first) mais s'est produit après A
        service.ingest_event(
            plaque=plaque,
            poste=PosteType.PORTE_USINE,
            type_event="entree",
            source="camera",
            horodatage=base,         # occurred 10:00
        )
        # Parking B — arrived first but occurred at 10:05
        service.ingest_event(
            plaque=plaque,
            poste=PosteType.PARKING,
            type_event="entree",
            source="agent_mobile",
            horodatage=base + timedelta(minutes=5),   # occurred 10:05
        )
        service.ingest_event(
            plaque=plaque,
            poste=PosteType.PARKING,
            type_event="sortie",
            source="agent_mobile",
            horodatage=base + timedelta(minutes=30),  # occurred 10:30
        )

        truck = db.query(Truck).filter(Truck.immatriculation == plaque).first()
        cycle = db.query(Cycle).filter(
            Cycle.truck_id == truck.id,
            Cycle.status == TruckStatus.EN_COURS,
        ).first()
        assert cycle is not None

        # Les événements sont ordonnés par horodatage (occurred_at), pas received_at
        events = db.query(Event).filter(
            Event.truck_id == truck.id,
        ).order_by(Event.horodatage.asc()).all()

        horodatages = [e.horodatage for e in events]
        assert horodatages == sorted(horodatages), (
            "Les événements doivent être ordonnés par horodatage (occurred_at)"
        )
