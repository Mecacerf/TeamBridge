#!/usr/bin/env python3
"""
A live data is a holder of a generic type variable that can be
observed as defined by the observer pattern.

---
TeamBridge - An open-source timestamping application

Author: Bastian Cerf
Copyright (C) 2025 Mecacerf SA
License: AGPL-3.0 <https://www.gnu.org/licenses/>
"""

from typing import Generic, TypeVar, Callable

T = TypeVar(name="T")  # Generic type declaration


class LiveData(Generic[T]):
    """
    Defines an observable data of type T.
    Note that since Python is not typed, T might just be Any. However
    using the Generic class from the typing package allows for better
    type checking and static analysis of the code.
    """

    def __init__(self, value: T, bus_mode: bool = False):
        """
        Create a live data of type T with an initial value.
        An optional bus mode is available if the live data is intended
        to be used for communicating events. In this mode, observers are
        notified each time a value is set, even if the value didn't
        changed. When the bus mode is disabled, observers are called only
        on change.

        Args:
            value (T): Initial value.
            bus_mode (bool): Enable/disable bus mode.
        """
        # Declare live data parameters
        self._value = value
        self._bus_mode = bus_mode
        self._observers: set[Callable[[T], None]] = set()

    def observe(self, observer: Callable[[T], None], init_call: bool = False):
        """
        Add an observer to the live data.

        Args:
            observer (Callable[[T], None]): New observer to register.
            init_call (bool): `True` to setup the observer with the
                current value.
        """
        self._observers.add(observer)
        if init_call:
            observer(self._value)

    def remove(self, observer: Callable[[T], None]):
        """
        Remove an observer.

        Args:
            observer (Callable[[T], None]): Observer to remove.
        """
        # Remove only if not present
        if observer in self._observers:
            self._observers.remove(observer)

    @property
    def value(self) -> T:
        """
        Get the value.

        Returns:
            T: value
        """
        return self._value

    @value.setter
    def value(self, value: T):
        """
        Change the value.

        If not bus mode, observers are notified only on value change.

        Args:
            value (T): New value.
        """
        if not self._bus_mode and self._value == value:
            return

        self._value = value
        for observer in self._observers:
            observer(self._value)
