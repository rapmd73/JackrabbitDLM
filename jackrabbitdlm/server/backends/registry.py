# -*- coding: utf-8 -*-
"""
Backend registry and factory for Jackrabbit DLM.

Provides a centralized way to instantiate and swap storage backends
at runtime. Supports configuration via dict or YAML.

Usage:
    from jackrabbitdlm.server.backends.registry import BackendRegistry
    
    # Configure backends
    BackendRegistry.configure({
        'default': 'memory',
        'backends': {
            'redis': {'host': 'localhost', 'port': 6379},
            'sqlite': {'db_path': '/tmp/locks.db'},
            'filesystem': {'base_dir': '/tmp/dlm_locks'},
        }
    })
    
    # Get configured backend
    backend = BackendRegistry.get('redis')
    
    # Swap default backend
    BackendRegistry.set_default('sqlite')
"""

from typing import Optional, Dict, Any, Type
import importlib

from .base import LockBackend
from .memory import MemoryBackend

# Available backends
_BACKENDS: Dict[str, Type[LockBackend]] = {
    'memory': MemoryBackend,
}

# Try to load optional backends
try:
    from .redis import RedisBackend as _RedisBackend
    _BACKENDS['redis'] = _RedisBackend
except ImportError:
    pass

try:
    from .sqlite import SQLiteBackend as _SQLiteBackend
    _BACKENDS['sqlite'] = _SQLiteBackend
except ImportError:
    pass

try:
    from .filesystem import FilesystemBackend as _FilesystemBackend
    _BACKENDS['filesystem'] = _FilesystemBackend
except ImportError:
    pass


class BackendRegistry:
    """
    Central registry for Jackrabbit DLM storage backends.

    Provides a singleton pattern for managing backend instances
    and configuration across the application lifecycle.
    """

    _instance: Optional['BackendRegistry'] = None
    _default_backend: str = 'memory'
    _backend_configs: Dict[str, Dict[str, Any]] = {}
    _backend_instances: Dict[str, Optional[LockBackend]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def configure(cls, config: Dict[str, Any]) -> None:
        """
        Configure backends from a config dict or YAML-loaded dict.

        Expected format:
            {
                'default': 'redis',
                'backends': {
                    'redis': {'host': 'localhost', 'port': 6379},
                    'sqlite': {'db_path': '/tmp/locks.db'},
                }
            }
        """
        cls._backend_configs = config.get('backends', {})
        default = config.get('default')
        if default:
            cls._default_backend = default

    @classmethod
    def register(cls, name: str, backend_class: Type[LockBackend]) -> None:
        """
        Register a custom backend class.

        Usage:
            BackendRegistry.register('mybackend', MyCustomBackend)
        """
        _BACKENDS[name] = backend_class

    @classmethod
    def get(cls, name: Optional[str] = None) -> LockBackend:
        """
        Get a backend instance by name.

        Args:
            name: Backend name (uses default if None)

        Returns:
            LockBackend instance configured and connected

        Raises:
            ValueError: If backend name not found
            ImportError: If backend has unmet dependencies
        """
        if name is None:
            name = cls._default_backend

        if name not in _BACKENDS:
            available = ', '.join(_BACKENDS.keys())
            raise ValueError(
                f"Unknown backend '{name}'. Available: {available}"
            )

        # Return cached instance if connected
        if name in cls._backend_instances and cls._backend_instances[name] is not None:
            return cls._backend_instances[name]

        # Create new instance
        backend_class = _BACKENDS[name]
        backend_config = cls._backend_configs.get(name, {})
        backend_instance = backend_class(backend_config)

        # Connect and cache
        if backend_instance.connect():
            cls._backend_instances[name] = backend_instance
            return backend_instance
        else:
            raise RuntimeError(f"Failed to connect to {name} backend")

    @classmethod
    def set_default(cls, name: str) -> None:
        """Set the default backend name."""
        if name not in _BACKENDS:
            available = ', '.join(_BACKENDS.keys())
            raise ValueError(
                f"Unknown backend '{name}'. Available: {available}"
            )
        cls._default_backend = name

    @classmethod
    def get_default(cls) -> str:
        """Get the current default backend name."""
        return cls._default_backend

    @classmethod
    def list_backends(cls) -> Dict[str, bool]:
        """
        List all available backends with their load status.

        Returns:
            Dict mapping backend name to availability (True/False)
        """
        return {name: True for name in _BACKENDS.keys()}

    @classmethod
    def reset(cls) -> None:
        """Disconnect all backends and clear instances."""
        for name, instance in cls._backend_instances.items():
            if instance:
                try:
                    instance.disconnect()
                except Exception:
                    pass
        cls._backend_instances = {}
        cls._default_backend = 'memory'
        cls._backend_configs = {}