# -*- coding: utf-8 -*-
"""
In-memory backend for Jackrabbit DLM.

Default backend that mirrors the original daemon behavior.
Locks are stored in RAM with optional disk spillover handled separately.
"""

import time
from typing import Optional, Dict, Any


class MemoryBackend:
    """
    In-memory storage backend for Jackrabbit DLM.

    This is the default backend. It stores all lock data in a Python dict
    and does not persist to disk - disk spillover is handled separately by
    the daemon's existing disk logic.

    This backend exists primarily to provide a consistent interface
    when swapping between backends.
    """

    name = "memory"
    _initialized = False

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._name = "memory"
        self._locks: Dict[str, Dict[str, Any]] = {}
        self._config = config or {}
        self._stats = {
            'reads': 0,
            'writes': 0,
            'erases': 0,
            'hits': 0,
            'misses': 0,
        }

    def connect(self) -> bool:
        """Initialize the in-memory store."""
        self._locks = {}
        self._initialized = True
        return True

    def disconnect(self) -> None:
        """Clear the in-memory store."""
        self._locks = {}
        self._initialized = False

    def read(self, filename: str) -> Optional[Dict[str, Any]]:
        """Read a lock entry."""
        self._stats['reads'] += 1
        if filename not in self._locks:
            self._stats['misses'] += 1
            return None
        self._stats['hits'] += 1
        return self._locks.get(filename)

    def write(self, filename: str, data: Dict[str, Any], expire: float) -> bool:
        """Write or update a lock entry."""
        self._stats['writes'] += 1
        self._locks[filename] = data.copy()
        self._locks[filename]['Expire'] = expire
        return True

    def erase(self, filename: str) -> bool:
        """Remove a lock entry."""
        self._stats['erases'] += 1
        if filename in self._locks:
            del self._locks[filename]
            return True
        return False

    def list(self) -> Dict[str, Dict[str, Any]]:
        """Return all lock entries."""
        return self._locks.copy()

    def exists(self, filename: str) -> bool:
        """Check if a lock entry exists."""
        return filename in self._locks

    def is_expired(self, filename: str) -> bool:
        """Check if a lock entry has expired."""
        if filename not in self._locks:
            return True
        return time.time() > self._locks[filename].get('Expire', 0)

    @property
    def name(self) -> str:
        return self._name

    @property
    def stats(self) -> Dict[str, Any]:
        return self._stats.copy()