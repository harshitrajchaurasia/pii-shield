"""
Redis Client Module for PI Remover Services.

Provides Redis connection management for:
- Distributed rate limiting across service instances
- Session management (optional)
- Caching (optional)

Falls back to in-memory storage if Redis is unavailable.

Usage:
    from shared.redis_client import RedisClient, get_redis_client
    
    # Get client (auto-connects)
    redis = await get_redis_client()
    
    # Rate limiting
    allowed, info = await redis.check_rate_limit("client_id", max_requests=100)
    
    # Caching
    await redis.cache_set("key", {"data": "value"}, ttl=300)
    data = await redis.cache_get("key")

Version: 2.9.0
"""

import os
import sys
import time
import json
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Union
from collections import defaultdict

# Add parent directory for config imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from shared.config_loader import get_config
except ImportError:
    get_config = lambda *args, **kwargs: None

logger = logging.getLogger(__name__)

# Try to import redis
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.info("Redis library not installed, using in-memory fallback")


@dataclass
class RedisConfig:
    """Redis connection configuration."""
    enabled: bool = False
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ssl: bool = False
    
    # Connection pool
    pool_size: int = 10
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    
    # Rate limiting
    rate_limit_key_prefix: str = "pi_remover:ratelimit"
    rate_limit_window: int = 60
    
    # Caching
    cache_key_prefix: str = "pi_remover:cache"
    cache_default_ttl: int = 300
    
    @classmethod
    def from_config(cls, config_path: Optional[str] = None) -> 'RedisConfig':
        """Load configuration from YAML file."""
        # Try to load from config file
        config = get_config('api_service', config_path)
        
        if not config:
            return cls()
        
        redis_config = config.get_section('redis')
        if not redis_config:
            return cls()
        
        return cls(
            enabled=redis_config.get('enabled', False),
            host=redis_config.get('host', 'localhost'),
            port=redis_config.get('port', 6379),
            db=redis_config.get('db', 0),
            password=redis_config.get('password'),
            ssl=redis_config.get('ssl', False),
            pool_size=redis_config.get('pool_size', 10),
            socket_timeout=redis_config.get('socket_timeout', 5.0),
        )


class InMemoryFallback:
    """
    In-memory fallback when Redis is unavailable.
    
    Provides the same interface as Redis but stores data in memory.
    Not suitable for distributed deployments.
    """
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._rate_limits: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "window_start": time.time()}
        )
        self._lock = asyncio.Lock()
    
    async def _cleanup_expired(self):
        """Remove expired keys."""
        now = time.time()
        expired = [k for k, exp in self._expiry.items() if exp < now]
        for key in expired:
            self._data.pop(key, None)
            self._expiry.pop(key, None)
    
    async def get(self, key: str) -> Optional[str]:
        """Get a value."""
        await self._cleanup_expired()
        return self._data.get(key)
    
    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set a value with optional expiry."""
        async with self._lock:
            self._data[key] = value
            if ex:
                self._expiry[key] = time.time() + ex
            return True
    
    async def incr(self, key: str) -> int:
        """Increment a counter."""
        async with self._lock:
            current = int(self._data.get(key, 0))
            self._data[key] = str(current + 1)
            return current + 1
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiry on a key."""
        self._expiry[key] = time.time() + seconds
        return True
    
    async def ttl(self, key: str) -> int:
        """Get TTL of a key."""
        if key not in self._expiry:
            return -1
        remaining = int(self._expiry[key] - time.time())
        return max(0, remaining)
    
    async def delete(self, *keys: str) -> int:
        """Delete keys."""
        count = 0
        async with self._lock:
            for key in keys:
                if key in self._data:
                    del self._data[key]
                    self._expiry.pop(key, None)
                    count += 1
        return count
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        await self._cleanup_expired()
        return key in self._data
    
    async def ping(self) -> bool:
        """Always returns True for in-memory."""
        return True
    
    async def close(self):
        """No-op for in-memory."""
        pass


class RedisClient:
    """
    Redis client with automatic fallback to in-memory storage.
    
    Features:
    - Automatic connection management
    - Fallback to in-memory if Redis unavailable
    - Rate limiting helpers
    - Caching helpers
    """
    
    def __init__(self, config: Optional[RedisConfig] = None):
        """
        Initialize Redis client.
        
        Args:
            config: Redis configuration (loads from file if not provided)
        """
        self.config = config or RedisConfig.from_config()
        self._client: Optional[Union[aioredis.Redis, InMemoryFallback]] = None
        self._is_redis = False
        self._lock = asyncio.Lock()
    
    async def _get_client(self):
        """Get or create Redis client."""
        async with self._lock:
            if self._client is not None:
                return self._client
            
            # Check if Redis is enabled and available
            if self.config.enabled and REDIS_AVAILABLE:
                try:
                    self._client = aioredis.Redis(
                        host=self.config.host,
                        port=self.config.port,
                        db=self.config.db,
                        password=self.config.password,
                        ssl=self.config.ssl,
                        socket_timeout=self.config.socket_timeout,
                        socket_connect_timeout=self.config.socket_connect_timeout,
                        max_connections=self.config.pool_size,
                        decode_responses=True
                    )
                    
                    # Test connection
                    await self._client.ping()
                    self._is_redis = True
                    logger.info(
                        f"Connected to Redis at {self.config.host}:{self.config.port}"
                    )
                except Exception as e:
                    # Sanitize error message to prevent Redis credentials leaking into logs
                    err_msg = str(e)
                    if 'password' in err_msg.lower() or '@' in err_msg:
                        err_msg = "Connection failed (credentials redacted)"
                    logger.warning(
                        f"Could not connect to Redis ({err_msg}), using in-memory fallback"
                    )
                    self._client = InMemoryFallback()
                    self._is_redis = False
            else:
                self._client = InMemoryFallback()
                self._is_redis = False
                if not self.config.enabled:
                    logger.info("Redis disabled in config, using in-memory storage")
                elif not REDIS_AVAILABLE:
                    logger.info("Redis library not available, using in-memory storage")
            
            return self._client
    
    @property
    def is_redis_connected(self) -> bool:
        """Check if connected to actual Redis (not fallback)."""
        return self._is_redis
    
    async def close(self):
        """Close Redis connection."""
        if self._client and self._is_redis:
            await self._client.close()
        self._client = None
    
    # =========================================================================
    # RATE LIMITING
    # =========================================================================
    
    async def check_rate_limit(
        self,
        identifier: str,
        max_requests: int = 100,
        window_seconds: int = 60,
        cost: int = 1
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit using sliding window.
        
        Args:
            identifier: Client identifier (IP, client_id, etc.)
            max_requests: Maximum requests per window
            window_seconds: Window size in seconds
            cost: Request cost (default 1)
            
        Returns:
            Tuple of (allowed: bool, info: dict)
        """
        client = await self._get_client()
        
        key = f"{self.config.rate_limit_key_prefix}:{identifier}"
        now = time.time()
        window_start = int(now / window_seconds) * window_seconds
        window_key = f"{key}:{window_start}"
        
        try:
            current = await client.incr(window_key)
            
            # Set expiry on first request in window
            if current == 1:
                await client.expire(window_key, window_seconds + 10)
            
            remaining = max(0, max_requests - current)
            reset_at = window_start + window_seconds
            
            allowed = current <= max_requests
            
            return allowed, {
                "remaining": remaining,
                "limit": max_requests,
                "reset": int(reset_at - now),
                "current": current
            }
            
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # Fail open - allow request on error
            return True, {"remaining": -1, "limit": max_requests, "reset": 0, "error": str(e)}
    
    async def get_rate_limit_info(
        self,
        identifier: str,
        window_seconds: int = 60
    ) -> Dict[str, Any]:
        """Get current rate limit info without incrementing."""
        client = await self._get_client()
        
        key = f"{self.config.rate_limit_key_prefix}:{identifier}"
        now = time.time()
        window_start = int(now / window_seconds) * window_seconds
        window_key = f"{key}:{window_start}"
        
        try:
            current = await client.get(window_key)
            current = int(current) if current else 0
            ttl = await client.ttl(window_key)
            
            return {
                "current": current,
                "reset_in": max(0, ttl)
            }
        except Exception as e:
            return {"current": 0, "reset_in": 0, "error": str(e)}
    
    # =========================================================================
    # CACHING
    # =========================================================================
    
    async def cache_get(self, key: str) -> Optional[Any]:
        """
        Get a cached value.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        client = await self._get_client()
        full_key = f"{self.config.cache_key_prefix}:{key}"
        
        try:
            value = await client.get(full_key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    async def cache_set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set a cached value.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time to live in seconds
            
        Returns:
            Success boolean
        """
        client = await self._get_client()
        full_key = f"{self.config.cache_key_prefix}:{key}"
        ttl = ttl or self.config.cache_default_ttl
        
        try:
            json_value = json.dumps(value)
            await client.set(full_key, json_value, ex=ttl)
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def cache_delete(self, key: str) -> bool:
        """Delete a cached value."""
        client = await self._get_client()
        full_key = f"{self.config.cache_key_prefix}:{key}"
        
        try:
            await client.delete(full_key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    # =========================================================================
    # HEALTH CHECK
    # =========================================================================
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Redis health."""
        try:
            client = await self._get_client()
            await client.ping()
            
            return {
                "status": "healthy",
                "backend": "redis" if self._is_redis else "memory",
                "host": self.config.host if self._is_redis else "local"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "backend": "redis" if self._is_redis else "memory",
                "error": str(e)
            }


# Global client instance
_redis_client: Optional[RedisClient] = None
_redis_lock = asyncio.Lock()


async def get_redis_client(config: Optional[RedisConfig] = None) -> RedisClient:
    """
    Get or create the global Redis client.
    
    Args:
        config: Optional configuration override
        
    Returns:
        RedisClient instance
    """
    global _redis_client
    
    async with _redis_lock:
        if _redis_client is None:
            _redis_client = RedisClient(config)
        return _redis_client


async def close_redis_client():
    """Close the global Redis client."""
    global _redis_client
    
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
