"""
Tests de mise en cache Redis, performances et invalidation automatique.
"""
import pytest
import time
from app.cache import cache_set, cache_get, cache_invalidate, get_redis


def test_redis_connection_available():
    """Vérifie que la connexion au conteneur Redis est opérationnelle."""
    r = get_redis()
    if r is None:
        pytest.skip("Redis non disponible localement (test d'intégration conteneur)")
    assert r.ping() is True


def test_redis_set_get_and_ttl():
    """Vérifie le stockage, la désérialisation JSON et la lecture depuis Redis."""
    key = "test:kpi:sample"
    data = {"metric": "temps_cycle", "valeur": 42.5, "unite": "min"}
    
    cache_set(key, data, ttl=10)
    cached_val = cache_get(key)
    
    assert cached_val is not None
    assert cached_val["valeur"] == 42.5
    assert cached_val["metric"] == "temps_cycle"


def test_redis_cache_invalidation():
    """Vérifie la suppression par pattern de clés (cache_invalidate)."""
    cache_set("dashboard:test1", {"val": 1}, ttl=30)
    cache_set("dashboard:test2", {"val": 2}, ttl=30)
    
    assert cache_get("dashboard:test1") is not None
    assert cache_get("dashboard:test2") is not None
    
    # Invalidation de toutes les clés de pattern dashboard:*
    deleted_count = cache_invalidate("dashboard:test*")
    assert deleted_count >= 2
    
    assert cache_get("dashboard:test1") is None
    assert cache_get("dashboard:test2") is None


def test_redis_miss_returns_none():
    """Une clé inexistante doit renvoyer None sans lever d'exception."""
    assert cache_get("cle:inexistante:12345") is None
