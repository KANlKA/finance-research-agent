"""
Caching layer. Uses diskcache (pure-Python, free, no server needed) so it
works identically in dev and prod without standing up Redis. Swap the
`cache` object for a Redis-backed one later without touching callers.
"""
import functools
import hashlib
import json

import diskcache

from app.config import CACHE_DIR

cache = diskcache.Cache(CACHE_DIR)


def _make_key(prefix: str, args, kwargs) -> str:
    raw = json.dumps({"a": args, "k": kwargs}, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{prefix}:{digest}"


def cached(ttl_seconds: int, prefix: str | None = None):
    """Decorator: memoize a function's return value in the disk cache."""

    def decorator(fn):
        key_prefix = prefix or fn.__name__

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = _make_key(key_prefix, args, kwargs)
            hit = cache.get(key, default=None)
            if hit is not None:
                return {**hit, "_cache_hit": True}
            result = fn(*args, **kwargs)
            cache.set(key, result, expire=ttl_seconds)
            if isinstance(result, dict):
                return {**result, "_cache_hit": False}
            return result

        return wrapper

    return decorator
