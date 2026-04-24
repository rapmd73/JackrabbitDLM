# -*- coding: utf-8 -*-
"""
Filesystem backend for Jackrabbit DLM.

Stores lock data as individual JSON files on disk.
Good for single-instance deployments with persistence needs.

Configuration:
    base_dir: Directory to store lock files (default: /home/JackrabbitDLM/backend_locks)
    file_ext: File extension for lock files (default: .lock)

Usage:
    backend = FilesystemBackend({'base_dir': '/tmp/dlm_locks'})
    backend.connect()
"""

import json
import os
import time
from typing import Optional, Dict, Any


class FilesystemBackend:
    """
    Filesystem-backed storage for Jackrabbit DLM.

    Stores each lock as a separate JSON file with expiration metadata.
    Provides persistence without database dependencies.
    """

    name = "filesystem"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._base_dir = self._config.get('base_dir', '/home/JackrabbitDLM/backend_locks')
        self._file_ext = self._config.get('file_ext', '.lock')
        self._initialized = False
        self._stats = {
            'reads': 0,
            'writes': 0,
            'erases': 0,
            'hits': 0,
            'misses': 0,
        }

    def _lock_path(self, filename: str) -> str:
        """Build full path for a lock file."""
        # Sanitize filename for filesystem safety
        safe_name = filename.replace('/', '_').replace('\\', '_')
        return os.path.join(self._base_dir, safe_name + self._file_ext)

    def connect(self) -> bool:
        """Create base directory if needed."""
        try:
            os.makedirs(self._base_dir, exist_ok=True)
            self._initialized = True
            return True
        except Exception:
            return False

    def disconnect(self) -> None:
        """Clean up resources."""
        self._initialized = False

    def read(self, filename: str) -> Optional[Dict[str, Any]]:
        """Read a lock entry from filesystem."""
        self._stats['reads'] += 1
        path = self._lock_path(filename)
        try:
            if not os.path.exists(path):
                self._stats['misses'] += 1
                return None
            with open(path, 'r') as f:
                data = json.load(f)
            # Check expiration
            if time.time() > data.get('Expire', 0):
                self.erase(filename)
                self._stats['misses'] += 1
                return None
            self._stats['hits'] += 1
            return data
        except Exception:
            return None

    def write(self, filename: str, data: Dict[str, Any], expire: float) -> bool:
        """Write or update a lock entry on filesystem."""
        self._stats['writes'] += 1
        path = self._lock_path(filename)
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data['Expire'] = expire
            data['Updated'] = time.time()
            with open(path, 'w') as f:
                json.dump(data, f)
            return True
        except Exception:
            return False

    def erase(self, filename: str) -> bool:
        """Remove a lock entry from filesystem."""
        self._stats['erases'] += 1
        path = self._lock_path(filename)
        try:
            if os.path.exists(path):
                os.remove(path)
                return True
            return False
        except Exception:
            return False

    def list(self) -> Dict[str, Dict[str, Any]]:
        """Return all non-expired lock entries from filesystem."""
        result = {}
        if not os.path.isdir(self._base_dir):
            return result
        now = time.time()
        for fname in os.listdir(self._base_dir):
            if not fname.endswith(self._file_ext):
                continue
            path = os.path.join(self._base_dir, fname)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                # Check expiration
                if now > data.get('Expire', 0):
                    # Clean up expired
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                    continue
                # Extract filename from lock file
                lock_name = fname[:-len(self._file_ext)]
                result[lock_name] = data
            except Exception:
                pass
        return result

    def exists(self, filename: str) -> bool:
        """Check if a non-expired lock entry exists on filesystem."""
        return self.read(filename) is not None

    def is_expired(self, filename: str) -> bool:
        """Check if a lock entry has expired."""
        path = self._lock_path(filename)
        try:
            if not os.path.exists(path):
                return True
            with open(path, 'r') as f:
                data = json.load(f)
            return time.time() > data.get('Expire', 0)
        except Exception:
            return True

    @property
    def name(self) -> str:
        return "filesystem"

    @property
    def stats(self) -> Dict[str, Any]:
        return self._stats.copy()