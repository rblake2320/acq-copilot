"""Redis caching service."""
import hashlib
import json
from typing import Any, Optional
import redis.asyncio as redis
import structlog

logger = structlog.get_logger(__name__)


class CacheService:
    """Service for caching tool results."""

    def __init__(self, redis_url: str) -> None:
        """
        Initialize cache service.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self.redis: Optional[redis.Redis] = None
        self._hit_count = 0
        self._miss_count = 0

    async def connect(self) -> None:
        """Establish Redis connection."""
        try:
            self.redis = await redis.from_url(self.redis_url, decode_responses=True)
            await self.redis.ping()
            logger.info("cache_connected")
        except Exception as e:
            logger.error("cache_connection_failed", error=str(e))
            raise

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            logger.info("cache_closed")

    def _build_key(self, tool_id: str, params: dict) -> str:
        """
        Build cache key from tool_id and parameters.

        Args:
            tool_id: Tool identifier
            params: Input parameters

        Returns:
            Cache key string
        """
        params_str = json.dumps(params, sort_keys=True, default=str)
        params_hash = hashlib.sha256(params_str.encode()).hexdigest()[:16]
        return f"tool:{tool_id}:{params_hash}"

    async def get(self, tool_id: str, params: dict, ttl: int = 3600) -> Optional[Any]:
        """
        Get cached value.

        Args:
            tool_id: Tool identifier
            params: Input parameters
            ttl: Time-to-live in seconds

        Returns:
            Cached value or None
        """
        if not self.redis:
            return None

        key = self._build_key(tool_id, params)
        try:
            value = await self.redis.get(key)
            if value:
                self._hit_count += 1
                logger.debug("cache_hit", key=key)
                return json.loads(value)
            else:
                self._miss_count += 1
                logger.debug("cache_miss", key=key)
                return None
        except Exception as e:
            logger.warning("cache_get_failed", key=key, error=str(e))
            return None

    async def set(self, tool_id: str, params: dict, value: Any, ttl: int = 3600) -> bool:
        """
        Set cached value.

        Args:
            tool_id: Tool identifier
            params: Input parameters
            value: Value to cache
            ttl: Time-to-live in seconds

        Returns:
            True if set successfully
        """
        if not self.redis:
            return False

        key = self._build_key(tool_id, params)
        try:
            serialized = json.dumps(value, default=str)
            await self.redis.setex(key, ttl, serialized)
            logger.debug("cache_set", key=key, ttl=ttl)
            return True
        except Exception as e:
            logger.warning("cache_set_failed", key=key, error=str(e))
            return False

    async def invalidate(self, pattern: str) -> int:
        """
        Invalidate cached entries matching pattern.

        Args:
            pattern: Redis key pattern (e.g., "tool:usaspending:*")

        Returns:
            Number of keys deleted
        """
        if not self.redis:
            return 0

        try:
            keys = await self.redis.keys(pattern)
            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info("cache_invalidated", pattern=pattern, deleted=deleted)
                return deleted
            return 0
        except Exception as e:
            logger.warning("cache_invalidate_failed", pattern=pattern, error=str(e))
            return 0

    async def clear_all(self) -> bool:
        """
        Clear entire cache.

        Returns:
            True if successful
        """
        if not self.redis:
            return False

        try:
            await self.redis.flushdb()
            logger.info("cache_cleared")
            return True
        except Exception as e:
            logger.warning("cache_clear_failed", error=str(e))
            return False

    async def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with hit/miss rates and memory usage
        """
        if not self.redis:
            return {
                "hit_rate": 0.0,
                "total_hits": 0,
                "total_misses": 0,
                "keys_count": 0,
                "memory_bytes": 0,
            }

        try:
            total = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total if total > 0 else 0.0
            info = await self.redis.info("memory")
            keys = await self.redis.dbsize()

            return {
                "hit_rate": round(hit_rate, 4),
                "total_hits": self._hit_count,
                "total_misses": self._miss_count,
                "keys_count": keys,
                "memory_bytes": info.get("used_memory", 0),
            }
        except Exception as e:
            logger.warning("cache_stats_failed", error=str(e))
            return {
                "hit_rate": 0.0,
                "total_hits": self._hit_count,
                "total_misses": self._miss_count,
                "keys_count": 0,
                "memory_bytes": 0,
            }
