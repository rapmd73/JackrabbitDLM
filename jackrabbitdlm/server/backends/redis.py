# -*- coding: utf-8 -*-
"""
Redis backend for Jackrabbit DLM.

Requires: redis (pip install redis)

Configuration:
    host: Redis host (default: localhost)
    port: Redis port (default: 6379)
    db: Redis database number (default: 0)
    password: Optional Redis password
    key_prefix: Key prefix for all DLM keys (default: dlm:)
    ttl_default: Default TTL in seconds (default: 300)

Usage:
    backend = RedisBackend({'host': 'localhost', 'port': 6379})
    backend.connect()
"""

import json
import time
from typing import Optional, Dict, Any

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


class RedisBackend:
    """
    Redis-backed storage for Jackrabbit DLM.

    All lock data is stored in Redis with optional TTL auto-expiration.
    Requires Redis server running.
    """

    name = "redis"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if not HAS_REDIS:
            raise ImportError("redis package required: pip install redis")
        self._config = config or {}
        self._client: Optional['redis.Redis'] = None
        self._key_prefix = self._config.get('key_prefix', 'dlm:')
        self._ttl_default = self._config.get('ttl_default', 300)
        self._stats = {
            'reads': 0,
            'writes': 0,
            'erases': 0,
            'hits': 0,
            'misses': 0,
        }

    def _key(self, filename: str) -> str:
        """Build Redis key for a filename."""
        return f"{self._key_prefix}{filename}"

    def connect(self) -> bool:
        """Connect to Redis server."""
        self._client = redis.Redis(
            host=self._config.get('host', 'localhost'),
            port=self._config.get('port', 6379),
            db=self._config.get('db', 0),
            password=self._config.get('password') or None,
            decode_responses=True,
            socket_timeout=self._config.get('socket_timeout', 5),
            socket_connect_timeout=self._config.get('connect_timeout', 5),
        )
        # Test connection
        self._client.ping()
        return True

    def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            self._client.close()
            self._client = None

    def read(self, filename: str) -> Optional[Dict[str, Any]]:
        """Read a lock entry from Redis."""
        self._stats['reads'] += 1
        if not self._client:
            return None
        try:
            data = self._client.get(self._key(filename))
            if data is None:
                self._stats['misses'] += 1
                return None
            self._stats['hits'] += 1
            return json.loads(data)
        except Exception:
            return None

    def write(self, filename: str, data: Dict[str, Any], expire: float) -> bool:
        """Write or update a lock entry in Redis."""
        self._stats['writes'] += 1
        if not self._client:
            return False
        try:
            # Calculate TTL in seconds
            ttl = max(1, int(expire - time.time()))
            json_data = json.dumps(data)
            self._client.setex(self._key(filename), ttl, json_data)
            return True
        except Exception:
            return False

    def erase(self, filename: str) -> bool:
        """Remove a lock entry from Redis."""
        self._stats['erases'] += 1
        if not self._client:
            return False
        try:
            return bool(self._client.delete(self._key(filename)))
        except Exception:
            return False

    def list(self) -> Dict[str, Dict[str, Any]]:
        """Return all lock entries from Redis."""
        result = {}
        if not self._client:
            return result
        try:
            pattern = f"{self._key_prefix}*"
            for key in self._client.scan_iter(pattern):
                data = self._client.get(key)
                if data:
                    try:
                        entry = json.loads(data)
                        # Extract filename from key
                        fname = key[len(self._key_prefix):]
                        result[fname] = entry
                    except Exception:
                        pass
        except Exception:
            pass
        return result

    def exists(self, filename: str) -> bool:
        """Check if a lock entry exists in Redis."""
        if not self._client:
            return False
        return bool(self._client.exists(self._key(filename)))

    def is_expired(self, filename: str) -> bool:
        """Check if a lock entry has expired (not applicable for Redis - uses TTL)."""
        # Redis handles expiration via TTL; if key exists, it's valid
        return not self.exists(filename)

    @property
    def name(self) -> str:
        return "redis"

    @property
    def stats(self) -> Dict[str, Any]:
        return self._stats.copy()