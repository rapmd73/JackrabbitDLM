# -*- coding: utf-8 -*-
"""
SQLite backend for Jackrabbit DLM.

Uses SQLite as a persistent lock store with automatic expiration handling.
Good for single-instance or embedded deployments.

Configuration:
    db_path: Path to SQLite database file (default: /home/JackrabbitDLM/locks.db)
    auto_vacuum: Enable auto vacuum (default: True)

Usage:
    backend = SQLiteBackend({'db_path': '/tmp/dlm.db'})
    backend.connect()
"""

import json
import time
import sqlite3
from typing import Optional, Dict, Any
from contextlib import contextmanager


class SQLiteBackend:
    """
    SQLite-backed storage for Jackrabbit DLM.

    Uses a single table to store all lock entries with expiration timestamps.
    Provides persistence without requiring an external server.
    """

    name = "sqlite"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._db_path = self._config.get('db_path', '/home/JackrabbitDLM/locks.db')
        self._conn: Optional[sqlite3.Connection] = None
        self._stats = {
            'reads': 0,
            'writes': 0,
            'erases': 0,
            'hits': 0,
            'misses': 0,
        }

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.execute("PRAGMA auto_vacuum = 1")
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = NORMAL")
            self._create_table()
        return self._conn

    def _create_table(self) -> None:
        """Create locks table if not exists."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS dlm_locks (
                filename TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                expire REAL NOT NULL,
                updated REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_expire ON dlm_locks(expire)
        """)
        self._conn.commit()

    def connect(self) -> bool:
        """Initialize SQLite database."""
        try:
            conn = self._get_connection()
            # Create table if needed
            self._create_table()
            return True
        except Exception as e:
            return False

    def disconnect(self) -> None:
        """Close SQLite connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def read(self, filename: str) -> Optional[Dict[str, Any]]:
        """Read a lock entry from SQLite."""
        self._stats['reads'] += 1
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                "SELECT data, expire FROM dlm_locks WHERE filename = ?",
                (filename,)
            )
            row = cursor.fetchone()
            if row is None:
                self._stats['misses'] += 1
                return None
            # Check expiration
            if time.time() > row[1]:
                # Auto-delete expired entry
                conn.execute("DELETE FROM dlm_locks WHERE filename = ?", (filename,))
                conn.commit()
                self._stats['misses'] += 1
                return None
            self._stats['hits'] += 1
            return json.loads(row[0])
        except Exception:
            return None

    def write(self, filename: str, data: Dict[str, Any], expire: float) -> bool:
        """Write or update a lock entry in SQLite."""
        self._stats['writes'] += 1
        try:
            conn = self._get_connection()
            json_data = json.dumps(data)
            now = time.time()
            conn.execute("""
                INSERT OR REPLACE INTO dlm_locks (filename, data, expire, updated)
                VALUES (?, ?, ?, ?)
            """, (filename, json_data, expire, now))
            conn.commit()
            return True
        except Exception:
            return False

    def erase(self, filename: str) -> bool:
        """Remove a lock entry from SQLite."""
        self._stats['erases'] += 1
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                "DELETE FROM dlm_locks WHERE filename = ?",
                (filename,)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception:
            return False

    def list(self) -> Dict[str, Dict[str, Any]]:
        """Return all non-expired lock entries from SQLite."""
        result = {}
        try:
            conn = self._get_connection()
            now = time.time()
            cursor = conn.execute(
                "SELECT filename, data FROM dlm_locks WHERE expire > ?",
                (now,)
            )
            for row in cursor:
                try:
                    result[row[0]] = json.loads(row[1])
                except Exception:
                    pass
            # Clean up expired entries
            conn.execute("DELETE FROM dlm_locks WHERE expire <= ?", (now,))
            conn.commit()
        except Exception:
            pass
        return result

    def exists(self, filename: str) -> bool:
        """Check if a non-expired lock entry exists in SQLite."""
        result = self.read(filename)
        return result is not None

    def is_expired(self, filename: str) -> bool:
        """Check if a lock entry has expired."""
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                "SELECT expire FROM dlm_locks WHERE filename = ?",
                (filename,)
            )
            row = cursor.fetchone()
            if row is None:
                return True
            return time.time() > row[0]
        except Exception:
            return True

    @property
    def name(self) -> str:
        return "sqlite"

    @property
    def stats(self) -> Dict[str, Any]:
        return self._stats.copy()