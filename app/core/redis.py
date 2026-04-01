import redis.asyncio as redis
from typing import Optional, Any
import json
from .config import settings


class RedisCache:
    """Redis cache manager - Optional."""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
    
    async def connect(self) -> None:
        """Connect to Redis if URL is provided."""
        if not settings.REDIS_URL:
            return
        
        try:
            self.redis = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
        except Exception:
            self.redis = None
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.redis:
            return None
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
        except Exception:
            pass
        return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: int = None
    ) -> None:
        """Set value in cache."""
        if not self.redis:
            return
        try:
            if ttl is None:
                ttl = settings.CACHE_TTL
            await self.redis.set(key, json.dumps(value), ex=ttl)
        except Exception:
            pass
    
    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        if not self.redis:
            return
        try:
            await self.redis.delete(key)
        except Exception:
            pass
    
    async def clear_pattern(self, pattern: str) -> None:
        """Clear all keys matching pattern."""
        if not self.redis:
            return
        try:
            async for key in self.redis.scan_iter(match=pattern):
                await self.redis.delete(key)
        except Exception:
            pass


cache = RedisCache()
