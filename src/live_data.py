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

    def __init__(self, value: T):
        """
        Create a live data of type T with an initial value.

        Parameters:
            value: initial value
        """
        # Create generic value
        self._value = value
        # Create observers list
        self._observers = []

    def observe(self, observer: Callable[[T], None]):
        """
        Add an observer to the live data.

        Parameters:
            observer: new observer as a lambda or a function
        """
        # Check for doublon and append
        if not observer in self._observers:
            self._observers.append(observer)

    def remove(self, observer: Callable[[T], None]):
        """
        Remove an observer.

        Parameters:
            observer: observer to remove
        """
        # Check observer exists in the list and remove
        if observer in self._observers:
            self._observers.remove(observer)

    def set_value(self, value: T):
        """
        Change the value and notify observers.

        Parameters:
            value: new value
        """
        # Notify on change
        if self._value == value:
            return
        # Set new value
        self._value = value
        # Notify observers
        for observer in self._observers:
            observer(self._value)

    def get_value(self) -> T:
        """
        Get the value.

        Returns:
            T: value
        """
        return self._value