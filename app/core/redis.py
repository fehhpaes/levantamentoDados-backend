import redis.asyncio as redis
from typing import Optional, Any
import json
from .config import settings


class RedisCache:
    """Redis cache manager."""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
    
    async def connect(self) -> None:
        """Connect to Redis."""
        self.redis = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.redis:
            return None
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: int = settings.CACHE_TTL
    ) -> None:
        """Set value in cache."""
        if not self.redis:
            return
        await self.redis.set(key, json.dumps(value), ex=ttl)
    
    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        if not self.redis:
            return
        await self.redis.delete(key)
    
    async def clear_pattern(self, pattern: str) -> None:
        """Clear all keys matching pattern."""
        if not self.redis:
            return
        async for key in self.redis.scan_iter(match=pattern):
            await self.redis.delete(key)


cache = RedisCache()
