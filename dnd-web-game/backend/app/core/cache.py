"""
D&D Combat Engine - Cache Service
In-memory caching with optional Redis support.
"""
import asyncio
import logging
from typing import Any, Optional, Callable, TypeVar, Dict
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import json

logger = logging.getLogger("dnd_engine.cache")

T = TypeVar('T')


class CacheEntry:
    """A single cache entry with expiration."""

    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.created_at = datetime.utcnow()
        self.expires_at = self.created_at + timedelta(seconds=ttl)

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


class CacheService:
    """
    In-memory cache service with TTL support.

    Features:
    - Key-value storage with TTL
    - Pattern-based invalidation
    - Cache statistics
    - Decorator for easy caching
    """

    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        """
        Initialize cache service.

        Args:
            default_ttl: Default time-to-live in seconds (5 minutes)
            max_size: Maximum number of cache entries
        """
        self._cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        self.max_size = max_size

        # Statistics
        self.hits = 0
        self.misses = 0

        # Cleanup task
        self._cleanup_task = None

    async def start(self):
        """Start the cache cleanup background task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("[Cache] Cache service started")

    async def stop(self):
        """Stop the cache cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("[Cache] Cache service stopped")

    async def _cleanup_loop(self):
        """Periodically clean up expired entries."""
        while True:
            await asyncio.sleep(60)  # Run every minute
            self._cleanup_expired()

    def _cleanup_expired(self):
        """Remove expired entries."""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"[Cache] Cleaned up {len(expired_keys)} expired entries")

    def _enforce_max_size(self):
        """Remove oldest entries if cache exceeds max size."""
        if len(self._cache) > self.max_size:
            # Sort by creation time and remove oldest
            sorted_keys = sorted(
                self._cache.keys(),
                key=lambda k: self._cache[k].created_at
            )
            to_remove = sorted_keys[:len(self._cache) - self.max_size]
            for key in to_remove:
                del self._cache[key]
            logger.debug(f"[Cache] Evicted {len(to_remove)} entries due to size limit")

    # ==================== Core Operations ====================

    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        entry = self._cache.get(key)

        if entry is None:
            self.misses += 1
            return None

        if entry.is_expired():
            del self._cache[key]
            self.misses += 1
            return None

        self.hits += 1
        return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        ttl = ttl or self.default_ttl
        self._cache[key] = CacheEntry(value, ttl)
        self._enforce_max_size()

    async def delete(self, key: str) -> bool:
        """
        Delete a key from cache.

        Args:
            key: Cache key

        Returns:
            True if key existed, False otherwise
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired."""
        entry = self._cache.get(key)
        if entry is None or entry.is_expired():
            return False
        return True

    async def invalidate(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.

        Args:
            pattern: Key pattern (supports * wildcard at end)

        Returns:
            Number of keys invalidated
        """
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            keys_to_delete = [
                key for key in self._cache.keys()
                if key.startswith(prefix)
            ]
        else:
            keys_to_delete = [pattern] if pattern in self._cache else []

        for key in keys_to_delete:
            del self._cache[key]

        if keys_to_delete:
            logger.debug(f"[Cache] Invalidated {len(keys_to_delete)} keys matching '{pattern}'")

        return len(keys_to_delete)

    async def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        logger.info("[Cache] Cache cleared")

    # ==================== Convenience Methods ====================

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int] = None
    ) -> Any:
        """
        Get a value from cache, or compute and cache it if not present.

        Args:
            key: Cache key
            factory: Function to compute value if not cached
            ttl: Time-to-live in seconds

        Returns:
            Cached or computed value
        """
        value = await self.get(key)
        if value is not None:
            return value

        # Compute value
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        await self.set(key, value, ttl)
        return value

    def make_key(self, *args, **kwargs) -> str:
        """
        Create a cache key from arguments.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Hash-based cache key
        """
        key_data = json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()

    # ==================== Statistics ====================

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            'entries': len(self._cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f'{hit_rate:.1f}%',
            'default_ttl': self.default_ttl
        }

    def reset_stats(self):
        """Reset cache statistics."""
        self.hits = 0
        self.misses = 0


# ==================== Decorator ====================

def cached(
    ttl: int = 300,
    key_prefix: str = '',
    cache_service: Optional[CacheService] = None
):
    """
    Decorator to cache function results.

    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache keys
        cache_service: Cache service instance (uses default if not provided)

    Usage:
        @cached(ttl=60, key_prefix='user')
        async def get_user(user_id: str):
            return await fetch_user_from_db(user_id)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Use provided cache or default
            cache = cache_service or default_cache

            # Build cache key
            key_data = json.dumps({
                'args': [str(a) for a in args],
                'kwargs': {k: str(v) for k, v in kwargs.items()}
            }, sort_keys=True)
            key_hash = hashlib.md5(key_data.encode()).hexdigest()[:16]
            cache_key = f"{key_prefix}:{func.__name__}:{key_hash}"

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Compute and cache
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await cache.set(cache_key, result, ttl)
            return result

        return wrapper
    return decorator


# ==================== Specialized Caches ====================

class SessionCache(CacheService):
    """Cache specifically for game sessions."""

    def __init__(self):
        super().__init__(default_ttl=3600, max_size=500)  # 1 hour TTL

    async def get_session(self, session_id: str) -> Optional[Dict]:
        return await self.get(f"session:{session_id}")

    async def set_session(self, session_id: str, data: Dict, ttl: int = 3600):
        await self.set(f"session:{session_id}", data, ttl)

    async def invalidate_session(self, session_id: str):
        await self.delete(f"session:{session_id}")


class CombatCache(CacheService):
    """Cache for combat state and calculations."""

    def __init__(self):
        super().__init__(default_ttl=300, max_size=200)  # 5 min TTL

    async def get_reachable_cells(self, combat_id: str, combatant_id: str) -> Optional[list]:
        return await self.get(f"reachable:{combat_id}:{combatant_id}")

    async def set_reachable_cells(self, combat_id: str, combatant_id: str, cells: list):
        await self.set(f"reachable:{combat_id}:{combatant_id}", cells, ttl=60)

    async def invalidate_combat(self, combat_id: str):
        await self.invalidate(f"reachable:{combat_id}:*")


class SpellCache(CacheService):
    """Cache for spell data lookups."""

    def __init__(self):
        super().__init__(default_ttl=86400, max_size=500)  # 24 hour TTL (spell data rarely changes)

    async def get_spell(self, spell_name: str) -> Optional[Dict]:
        return await self.get(f"spell:{spell_name.lower()}")

    async def set_spell(self, spell_name: str, data: Dict):
        await self.set(f"spell:{spell_name.lower()}", data)


# ==================== Default Instance ====================

default_cache = CacheService()
session_cache = SessionCache()
combat_cache = CombatCache()
spell_cache = SpellCache()
