"""
Response caching for AI DM with TTL and scenario-based keys.

Caches AI-generated narrative responses to reduce API calls and costs.
Uses content hashing to find similar scenarios.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cached AI response with metadata."""
    response: str
    created_at: datetime
    scenario_type: str  # scene, combat, skill_check, npc
    context_hash: str
    hit_count: int = 0

    def is_expired(self, ttl: timedelta) -> bool:
        """Check if this entry has expired."""
        return datetime.utcnow() - self.created_at > ttl

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "response": self.response,
            "created_at": self.created_at.isoformat(),
            "scenario_type": self.scenario_type,
            "context_hash": self.context_hash,
            "hit_count": self.hit_count,
        }


class AIDMCache:
    """
    LRU cache for AI DM responses with TTL and scenario matching.

    Uses content hashing to find similar scenarios and return
    cached responses when appropriate.

    Features:
    - TTL-based expiration (default 30 minutes)
    - Scenario-specific key generation
    - LRU eviction when max size reached
    - Hit count tracking for analytics
    """

    def __init__(self, max_size: int = 100, ttl_minutes: int = 30):
        """
        Initialize the cache.

        Args:
            max_size: Maximum number of entries to cache
            ttl_minutes: Time-to-live in minutes for cache entries
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._ttl = timedelta(minutes=ttl_minutes)
        self._hits = 0
        self._misses = 0

        logger.info(f"AI DM Cache initialized: max_size={max_size}, ttl={ttl_minutes}min")

    def _generate_key(self, scenario_type: str, context: Dict[str, Any]) -> str:
        """
        Generate cache key from scenario context.

        Normalizes the context to extract only cache-relevant fields,
        then hashes them for a consistent key.

        Args:
            scenario_type: Type of narrative (scene, combat, skill_check, npc)
            context: Full context dictionary

        Returns:
            MD5 hash string as cache key
        """
        normalized = self._normalize_context(scenario_type, context)
        normalized["_type"] = scenario_type
        content = json.dumps(normalized, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()

    def _normalize_context(self, scenario_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract cacheable elements from context.

        Different scenario types have different key fields.
        We extract only the fields that would result in semantically
        similar responses if matched.

        Args:
            scenario_type: Type of narrative
            context: Full context dictionary

        Returns:
            Normalized dictionary with only cache-relevant fields
        """
        if scenario_type == "scene":
            # For scene descriptions, match on encounter type and intro text prefix
            intro_text = context.get("story", {}).get("intro_text", "")
            return {
                "encounter_type": context.get("type", "unknown"),
                "intro_hash": hashlib.md5(intro_text[:100].encode()).hexdigest()[:8],
            }

        elif scenario_type == "combat":
            # For combat narration, match on action type, hit/miss, and kill status
            return {
                "action_type": context.get("action_type", "attack"),
                "hit": context.get("hit", False),
                "is_kill": context.get("current_hp", 1) <= 0,
                "damage_type": context.get("damage_type", ""),
            }

        elif scenario_type == "skill_check":
            # For skill checks, match on skill, success/fail, and margin bucket
            roll = context.get("roll", 10)
            dc = context.get("dc", 10)
            margin = abs(roll - dc)
            # Bucket margin into groups: 0-2 (close), 3-5 (moderate), 6+ (decisive)
            margin_bucket = min(margin // 3, 2)
            return {
                "skill": context.get("skill", "").lower(),
                "success": context.get("success", False),
                "margin_bucket": margin_bucket,
            }

        elif scenario_type == "npc":
            # For NPC dialogue, match on NPC type and personality
            return {
                "npc_type": context.get("npc_type", ""),
                "personality": context.get("personality", ""),
                "situation": context.get("situation", "")[:50],
            }

        # Default: return empty (no caching for unknown types)
        return {}

    def get(self, scenario_type: str, context: Dict[str, Any]) -> Optional[str]:
        """
        Get cached response if available and not expired.

        Args:
            scenario_type: Type of narrative
            context: Scenario context

        Returns:
            Cached response string, or None if not found/expired
        """
        key = self._generate_key(scenario_type, context)
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired(self._ttl):
            # Remove expired entry
            del self._cache[key]
            self._misses += 1
            logger.debug(f"Cache entry expired: {scenario_type}")
            return None

        # Cache hit
        entry.hit_count += 1
        self._hits += 1
        logger.debug(f"Cache hit for {scenario_type} (hits: {entry.hit_count})")
        return entry.response

    def set(self, scenario_type: str, context: Dict[str, Any], response: str) -> None:
        """
        Cache a response.

        Args:
            scenario_type: Type of narrative
            context: Scenario context
            response: AI-generated response to cache
        """
        if not response:
            return

        # Evict oldest entries if at capacity
        while len(self._cache) >= self._max_size:
            self._evict_oldest()

        key = self._generate_key(scenario_type, context)
        self._cache[key] = CacheEntry(
            response=response,
            created_at=datetime.utcnow(),
            scenario_type=scenario_type,
            context_hash=key,
        )
        logger.debug(f"Cached {scenario_type} response (size: {len(self._cache)})")

    def _evict_oldest(self) -> None:
        """Remove the oldest cache entry (LRU)."""
        if not self._cache:
            return

        oldest_key = min(self._cache, key=lambda k: self._cache[k].created_at)
        evicted = self._cache.pop(oldest_key)
        logger.debug(f"Evicted cache entry: {evicted.scenario_type} (age: {datetime.utcnow() - evicted.created_at})")

    def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache cleared: {count} entries removed")
        return count

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired(self._ttl)
        ]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired entries")

        return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_hits = sum(e.hit_count for e in self._cache.values())

        # Group by scenario type
        by_type: Dict[str, int] = {}
        for entry in self._cache.values():
            by_type[entry.scenario_type] = by_type.get(entry.scenario_type, 0) + 1

        hit_rate = (self._hits / (self._hits + self._misses) * 100) if (self._hits + self._misses) > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl_minutes": self._ttl.total_seconds() / 60,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 1),
            "total_response_hits": total_hits,
            "by_scenario_type": by_type,
        }

    def get_cached_scenarios(self) -> List[Dict[str, Any]]:
        """
        Get list of all cached scenarios (for debugging).

        Returns:
            List of cache entry summaries
        """
        return [
            {
                "scenario_type": entry.scenario_type,
                "created_at": entry.created_at.isoformat(),
                "hit_count": entry.hit_count,
                "age_seconds": (datetime.utcnow() - entry.created_at).total_seconds(),
                "response_preview": entry.response[:100] + "..." if len(entry.response) > 100 else entry.response,
            }
            for entry in self._cache.values()
        ]
