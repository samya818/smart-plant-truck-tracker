"""
Tests unitaires pour les fonctions de normalisation et similarité OCR.
"""
import pytest
from app.services.cv_service import _normalize_plate, _similarity


def test_normalize_plate_basic():
    """Vérifie le nettoyage et la mise en majuscules des plaques d'immatriculation."""
    assert _normalize_plate("12345-a-1") == "12345-A-1"
    assert _normalize_plate(" 67890 - B - 2 ") == "67890-B-2"
    assert _normalize_plate("ga-998-ln") == "GA-998-LN"


def test_normalize_plate_special_chars():
    """Vérifie que les caractères spéciaux superflus sont retirés."""
    assert _normalize_plate("12345.A.1!") == "12345A1"


def test_similarity_exact_match():
    """Deux plaques identiques doivent retourner une similarité de 1.0."""
    assert _similarity("12345-A-1", "12345-A-1") == 1.0


def test_similarity_close_match():
    """Des plaques proches (ex: erreur OCR d'un caractère) doivent avoir une bonne similarité."""
    sim = _similarity("12345-A-1", "12345-A-2")
    assert sim >= 0.80


def test_similarity_different():
    """Des plaques complètement différentes doivent avoir une faibles similarité."""
    sim = _similarity("12345-A-1", "99999-Z-9")
    assert sim < 0.50
