#!/usr/bin/env python3
"""
Define the base interfaces to build a finite state machine.

---
TeamBridge - An open-source timestamping application

Author: Bastian Cerf
Copyright (C) 2025 Mecacerf SA
License: AGPL-3.0 <https://www.gnu.org/licenses/>
"""

from abc import ABC
from typing import Optional


class IStateBehavior(ABC):
    """
    Base interface that defines how a state behaves.

    A state always holds a reference to its parent state machine object
    that is retrievable by the `fsm` property. The type of `fsm` is `T`
    and is defined by the subclass. It must be bound to `IStateMachine`
    (i.e. inherits it). It allows to tell the type checker the exact
    type of `fsm`.
    """

    def _set_fsm(self, value: "IStateMachine"):
        """Internal use only: set the state machine reference"""
        self._fsm = value

    def entry(self):
        """
        State entry method.
        """
        pass

    def do(self) -> Optional["IStateBehavior"]:
        """
        State running method.

        Returns:
            Optional[IStateBehavior]: A new state object if a transition
                should be performed.
        """
        pass

    def exit(self):
        """
        State exit method.
        """
        pass

    def __str__(self):
        """
        Provide a default state description.
        """
        return self.__class__.__name__


class IStateMachine(ABC):
    """
    Base class that runs a finite state machine.

    Provide the base interface to make state transitions and call the
    entry(), do() and exit() methods of the states.
    """

    def __init__(self, init_state: IStateBehavior):
        """
        Create the state machine and enter the given state.

        Args:
            init_state (IStateBehavior): Initial state.
        """
        self._init_state = init_state
        self._state = None

    def __make_transition(self, state: IStateBehavior):
        """
        Internal method to change state. Exit the previous state and
        enter the new one.
        """
        old_state = self._state
        if self._state:
            self._state.exit()

        self._state = state
        self._state._set_fsm(self)  # type: ignore friend class
        self._state.entry()

        self.on_state_changed(old_state, self._state)

    def run(self):
        """
        Run the state machine. Perform state transition if necessary.
        """
        if self._state is None:  # Transition to initial state
            self.__make_transition(self._init_state)

        # The do() method may return a transition
        assert self._state is not None
        next_state = self._state.do()
        if next_state:
            self.__make_transition(next_state)

    def on_state_changed(
        self, old_state: Optional[IStateBehavior], new_state: IStateBehavior
    ):
        """
        This method can be overriden to be notified on state transition.

        Args:
            old_state (IStateBehavior): Old state.
            new_state (IStateBehavior): New state (= self._state).
        """
        pass
