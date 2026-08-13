"""
Tests d'intégration des endpoints API FastAPI.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    """Vérifie que l'endpoint /health réponds HTTP 200 OK avec le statut de santé."""
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data.get("status") == "ok"
    assert "version" in json_data


def test_dashboard_stats_endpoint():
    """Vérifie que l'endpoint /api/dashboard/stats retourne la structure attendue."""
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    json_data = response.json()
    assert "camions_en_cours" in json_data
    assert "camions_aujourdhui" in json_data
    assert "temps_moyen_cycle" in json_data


def test_analytics_rapport_endpoint():
    """Vérifie que le rapport analytique /api/analytics/rapport?periode=aujourd_hui fonctionne."""
    response = client.get("/api/analytics/rapport?periode=aujourd_hui")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data.get("periode") == "aujourd_hui"
    assert "nb_cycles_total" in json_data


def test_events_active_endpoint():
    """Vérifie l'endpoint /api/events/active."""
    response = client.get("/api/events/active")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_events_finished_today_endpoint():
    """Vérifie l'endpoint /api/events/finished-today."""
    response = client.get("/api/events/finished-today")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
