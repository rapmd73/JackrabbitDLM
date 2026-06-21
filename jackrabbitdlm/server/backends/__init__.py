# -*- coding: utf-8 -*-
"""
Jackrabbit DLM Backend Abstraction

Provides pluggable storage backends for the Jackrabbit DLM server.
"""

from .base import LockBackend

__all__ = ['LockBackend']