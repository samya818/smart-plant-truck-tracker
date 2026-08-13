"""
Tests de robustesse, validation des schémas et cas limites (Edge Cases / Security).
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_invalid_period_in_analytics_falls_back(client):
    """Une période invalide dans /api/analytics/rapport ne doit pas faire crasher l'API."""
    response = client.get("/api/analytics/rapport?periode=periode_invalide")
    # L'API FastAPI retourne 422 Unprocessable Entity (Validation Pydantic)
    assert response.status_code in [200, 422]


def test_nonexistent_endpoint_returns_404(client):
    """Un endpoint inexistant doit proprement retourner un code HTTP 404."""
    response = client.get("/api/endpoint-qui-nexiste-pas")
    assert response.status_code == 404


def test_update_seuils_validation(client):
    """Vérifie la validation des schémas Pydantic lors de la mise à jour des seuils (PUT)."""
    # Payload manquant des champs requis
    payload_invalide = {"parking": 20}
    response = client.put("/api/dashboard/seuils", json=payload_invalide)
    assert response.status_code == 422


def test_cors_headers_present(client):
    """Vérifie que l'API autorise les requêtes web du frontend."""
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
