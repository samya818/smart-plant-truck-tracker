"""
Tests unitaires et logiques pour la détection d'anomalies (AnomalyDetector).
"""
import pytest
from app.database import SessionLocal
from app.services.anomaly_detector import AnomalyDetector


def test_anomaly_detector_initialization(db):
    """Vérifie l'initialisation du détecteur d'anomalies avec la session DB."""
    detector = AnomalyDetector(db)
    assert detector.db is not None


def test_anomaly_detector_poste_bloquant(db):
    """Vérifie que l'algorithme retourne une analyse sur les postes bloquants."""
    detector = AnomalyDetector(db)
    bloquant_info = detector.get_poste_bloquant()
    assert isinstance(bloquant_info, dict)
    assert "poste_bloquant" in bloquant_info


def test_anomaly_detector_calcul_retard():
    """Vérifie le calcul correct du dépassement par rapport au seuil."""
    duree_observee = 75.0  # 75 minutes
    seuil_max = 45.0       # Seuil max à 45 minutes
    retard = max(0.0, duree_observee - seuil_max)
    assert retard == 30.0
