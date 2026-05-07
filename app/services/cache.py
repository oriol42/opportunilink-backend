# app/services/cache.py
# Redis cache utility for expensive operations like the feed.

import json
import logging
import redis
from app.config import settings

logger = logging.getLogger(__name__)

# One global Redis client shared across the app
_redis_client = None


def get_redis():
    """Return a Redis client, or None if Redis is unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        redis_url = settings.redis_url or "redis://localhost:6379/0"
        ssl = redis_url.startswith("rediss://")
        _redis_client = redis.from_url(
            redis_url,
            decode_responses=True,
            ssl_cert_reqs="none" if ssl else None,
        )
        _redis_client.ping()  # Test connection immediately
        logger.info("Redis cache connected")
    except Exception as e:
        logger.warning(f"Redis unavailable — cache disabled: {e}")
        _redis_client = None

    return _redis_client


def cache_get(key: str):
    """Get a value from cache. Returns None if missing or Redis is down."""
    r = get_redis()
    if not r:
        return None
    try:
        value = r.get(key)
        return json.loads(value) if value else None
    except Exception as e:
        logger.warning(f"Cache GET failed for {key}: {e}")
        return None


def cache_set(key: str, value, ttl_seconds: int = 300):
    """Store a value in cache with expiry. Silently fails if Redis is down."""
    r = get_redis()
    if not r:
        return
    try:
        r.setex(key, ttl_seconds, json.dumps(value))
    except Exception as e:
        logger.warning(f"Cache SET failed for {key}: {e}")


def cache_delete_pattern(pattern: str):
    """Delete all keys matching a pattern — used to invalidate cache."""
    r = get_redis()
    if not r:
        return
    try:
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
            logger.info(f"Cache invalidated: {len(keys)} keys matching '{pattern}'")
    except Exception as e:
        logger.warning(f"Cache DELETE failed for pattern {pattern}: {e}")
