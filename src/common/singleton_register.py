#!/usr/bin/env python3
"""
File: singleton_register.py
Author: Bastian Cerf
Date: 02/06/2025
Description:
    Abstract base class to create one singleton instance per subclass.
    Any class inheriting from `SingletonRegister` will be created only
    once at first access. Subsequent calls to the constructor will
    always return the only instance.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
from typing import Self, final, Any
from abc import ABC
import threading


class SingletonRegister(ABC):
    """
    Abstract base class to create one singleton instance per subclass.

    Ensures that each subclass is instantiated only once and provides
    thread-safe access to these instances via an internal registry.
    """

    _instances: dict[type, "SingletonRegister"] = {}
    _lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """
        Called when a new instance of the class is requested.

        Ensures singleton behavior by returning an existing instance
        from the internal registry if available, or creating and
        registering a new one if not.

        Thread safety is guaranteed using a lock.
        """
        with SingletonRegister._lock:
            if cls in SingletonRegister._instances:
                return SingletonRegister._instances[cls]

            instance = super().__new__(cls)
            SingletonRegister._instances[cls] = instance
            instance._setup(*args, **kwargs)
            return instance

    def _setup(self, *args: Any, **kwargs: Any) -> None:
        """
        Subclasses should override this method for initialization.

        Called only once per singleton lifetime, during the first
        instantiation.
        """
        pass

    @final
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Indicate to type checker tools that this method should not
        be overridden in subclasses."""
        pass
