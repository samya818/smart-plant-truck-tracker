"""
Module cache Redis centralisé.

Fournit un client Redis singleton et deux helpers :
  - cache_get(key)          → désérialise le JSON depuis Redis ou retourne None
  - cache_set(key, data, ttl) → sérialise en JSON et stocke avec TTL

En cas d'indisponibilité de Redis (hors ligne, timeout), les fonctions
dégradent silencieusement sans faire planter l'endpoint.
"""
import json
import logging
from typing import Any, Optional

import redis as redis_lib

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[redis_lib.Redis] = None


def get_redis() -> Optional[redis_lib.Redis]:
    """Retourne le client Redis singleton, ou None si Redis est indisponible."""
    global _client
    if _client is not None:
        return _client
    try:
        settings = get_settings()
        _client = redis_lib.Redis.from_url(
            settings.get_redis_url(),
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        )
        _client.ping()
        logger.info("[Cache] Connexion Redis établie ✓")
    except Exception as e:
        logger.warning(f"[Cache] Redis indisponible — cache désactivé : {e}")
        _client = None
    return _client


def cache_get(key: str) -> Optional[Any]:
    """Récupère une valeur depuis Redis et la désérialise en JSON.
    Retourne None si absent ou en cas d'erreur.
    """
    try:
        client = get_redis()
        if client is None:
            return None
        raw = client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"[Cache] Erreur cache_get({key}): {e}")
        return None


def cache_set(key: str, data: Any, ttl: int = 30) -> None:
    """Sérialise data en JSON et le stocke dans Redis avec TTL (secondes).
    Échoue silencieusement si Redis est indisponible.
    """
    try:
        client = get_redis()
        if client is None:
            return
        client.setex(key, ttl, json.dumps(data, default=str, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"[Cache] Erreur cache_set({key}): {e}")


def cache_invalidate(pattern: str) -> int:
    """Supprime toutes les clés correspondant au pattern (ex: 'dashboard:*').
    Retourne le nombre de clés supprimées.
    """
    try:
        client = get_redis()
        if client is None:
            return 0
        keys = client.keys(pattern)
        if keys:
            return client.delete(*keys)
        return 0
    except Exception as e:
        logger.warning(f"[Cache] Erreur cache_invalidate({pattern}): {e}")
        return 0
