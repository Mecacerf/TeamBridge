#!/usr/bin/env python3
"""
File: live_data.py
Author: Bastian Cerf
Date: 02/03/2025
Description: 
    A live data is a holder of a generic type variable that can be
    observed as defined by the observer pattern.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

from typing import Generic, TypeVar, Callable

T = TypeVar(name='T') # Generic type declaration

class LiveData(Generic[T]):
    """
    Defines an observable data of type T.
    Note that since Python is not typed, T might just be Any. However using the Generic
    class from the typing package allows for better type checking and static analysis of the code.
    """

    def __init__(self, value: T, bus_mode: bool=False):
        """
        Create a live data of type T with an initial value.
        An optional bus mode is available if the live data is intended to be used for communicating 
        events. In this mode, observers are notified each time a value is set, even if the actual
        value didn't changed. When the bus mode is disabled, observers are called only on change.
        
        Parameters:
            value: initial value
            bus_mode: enable/disable bus mode
        """
        # Declare live data parameters
        self._value = value
        self._bus_mode = bus_mode
        self._observers = set() # Use a set to prevent observers to be added more than once

    def observe(self, observer: Callable[[T], None]):
        """
        Add an observer to the live data.

        Parameters:
            observer: new observer as a lambda or a function
        """
        self._observers.add(observer)

    def remove(self, observer: Callable[[T], None]):
        """
        Remove an observer.

        Parameters:
            observer: observer to remove
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
        Change the value and notify observers.

        Parameters:
            value: new value
        """
        # Notify on change if not in bus mode
        if not self._bus_mode and self._value == value:
            return
        # Set the new value and notify observers
        self._value = value
        for observer in self._observers:
            observer(self._value)
