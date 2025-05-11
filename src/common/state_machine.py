#!/usr/bin/env python3
"""
File: state_machine.py
Author: Bastian Cerf
Date: 17/04/2025
Description: 
    Define the base interfaces to build a finite state machine. 

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

from abc import ABC
from typing import Generic, TypeVar

class IStateMachine(ABC):
    """
    Base class that runs a finite state machine.
    Provide the base interface to make state transitions and call the
    entry(), do() and exit() methods of the states.
    """

    def __init__(self, init_state: "IStateBehavior"):
        """
        Create the state machine and enter the given state.

        Args:
            init_state: `StateBehavior` initial state
        """
        # Set init state
        self._init_state = init_state
        # Current state is initially None
        self._state = None

    def __make_transition(self, state: "IStateBehavior"):
        """
        Internal method to change state. Exit the previous state and enter the new one.
        """
        # Exit current state
        old_state = self._state
        if self._state:
            self._state.exit()
        # Set the new state
        self._state = state
        # Give the reference to the state machine to the new state
        self._state._fsm = self
        # Call the state entry method
        self._state.entry()

        # Notify of the state transition
        self.on_state_changed(old_state)
        
    def run(self):
        """
        Run the state machine. Perform state transition if necessary.
        """
        # Check if initializing
        if self._state is None:
            self.__make_transition(self._init_state)
        # Call the do method of the current state 
        next_state = self._state.do()
        # Check if a state transition should be performed
        if next_state:
            self.__make_transition(next_state)

    def on_state_changed(self, old_state: "IStateBehavior"):
        """
        This method can be overriden to be notified on state transition.

        Args:
            old_state: `IStateBehavior` reference to old state
        """
        pass

# Define generic state machine class
T = TypeVar('T', bound=IStateMachine)

class IStateBehavior(ABC, Generic[T]):
    """
    Base interface that defines how a state behaves.
    The type T is defined by the inheritor of the state. It allows to work
    with a known subclass of IStateMachine, which is great to get better 
    static code analysis and autocompletion.
    """

    def __init__(self):
        """
        Create a state behavior object.
        """
        self._fsm: T = None

    def entry(self):
        """
        State entry method.
        """
        pass

    def do(self) -> "IStateBehavior":
        """
        State running method.

        Returns:
            IStateBehavior: a new state object if a transition should be performed
        """
        pass

    def exit(self):
        """
        State exit method.
        """
        pass

    def __repr__(self):
        """
        Provide a default representation of the state.
        """
        return self.__class__.__name__
