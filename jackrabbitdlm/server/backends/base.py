# -*- coding: utf-8 -*-
"""
Base interface for Jackrabbit DLM storage backends.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class LockBackend(ABC):
    """
    Abstract base class for Jackrabbit DLM storage backends.

    Implement this interface to add new storage backends (Redis, SQLite, Filesystem, etc.)

    Required methods:
        - connect(): Initialize the backend connection
        - disconnect(): Clean up the backend connection
        - read(filename): Read a lock entry
        - write(filename, data, expire): Write/update a lock entry
        - erase(filename): Remove a lock entry
        - list(): Return all lock entries
        - exists(filename): Check if a lock exists
        - is_expired(filename): Check if a lock has expired
    """

    @abstractmethod
    def connect(self) -> bool:
        """Initialize the backend. Returns True on success."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Clean up backend resources."""
        pass

    @abstractmethod
    def read(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Read a lock entry by filename.

        Returns:
            Dict with lock data or None if not found/expired
        """
        pass

    @abstractmethod
    def write(self, filename: str, data: Dict[str, Any], expire: float) -> bool:
        """
        Write or update a lock entry.

        Args:
            filename: Resource/filename identifier
            data: Lock data dict (ID, Expire, DataStore, Name, Identity, etc.)
            expire: Expiration timestamp (time.time() + ttl)

        Returns:
            True on success
        """
        pass

    @abstractmethod
    def erase(self, filename: str) -> bool:
        """
        Remove a lock entry.

        Returns:
            True if removed, False if not found
        """
        pass

    @abstractmethod
    def list(self) -> Dict[str, Dict[str, Any]]:
        """
        Return all lock entries as a dict mapping filename -> lock_data.

        Returns:
            Dict of all current locks
        """
        pass

    @abstractmethod
    def exists(self, filename: str) -> bool:
        """Check if a lock entry exists and is not expired."""
        pass

    @abstractmethod
    def is_expired(self, filename: str) -> bool:
        """Check if a lock entry has expired."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return backend name (e.g., 'memory', 'redis', 'sqlite', 'filesystem')."""
        pass

    @property
    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """Return backend-specific statistics."""
        pass