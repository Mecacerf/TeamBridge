#!/usr/bin/env python3
"""
File: time_tracker_interface.py
Author: Bastian Cerf
Date: 17/02/2025
Description: 
    Give access to employees data through a simple interface.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

import datetime as dt
from enum import Enum

###############################################
# Employee Time Tracker Interface Declaration #
###############################################

class ClockAction(Enum):
    """
    Clock actions enumeration.
    """
    CLOCK_IN = 0
    CLOCK_OUT = 1

class ClockEvent:
    """
    Simple container for a clock event.
    """

    def __init__(self, time: dt.time, action: ClockAction):
        """
        Create a clock event.

        Parameters:
            time: time event occurred
            action: event action
        """
        self.time = time
        self.action = action

    def __repr__(self):
        """
        Get a string representation of this clock event.
        """
        return f"ClockEvent[time={self.time}, action={self.action}]"

class ITodayTimeTracker:
    """
    Interface for accessing and managing an employee's daily attendance data.

    This interface is designed with simplicity in mind: it is initialized for a specific date, 
    after which all operations relate exclusively to times within that date. By focusing on a single 
    day at a time, the interface avoids the complexity of date management, allowing straightforward 
    retrieval and manipulation of attendance events such as clock-ins, clock-outs, and breaks.
    
    Typical use cases include daily time tracking, attendance validation, and working hours reporting.
    """

    def __init__(self, employee_id: str, index: dt.date):
        """
        Open the employee's data for given date.

        Parameters:
            id: employee unique ID
            index: date index
        Raise:
            ValueError: employee not found
            ValueError: wrong / unavailable date time
        """
        pass

    def get_firstname(self) -> str:
        """
        Get employee's firstname.

        Returns:
            str: employee's firstname
        """
        pass

    def get_name(self) -> str:
        """
        Get employee's name.

        Returns:
            str: employee's name
        """
        pass

    def get_clock_events_today(self) -> list[ClockEvent]:
        """
        Get all clock-in/out events for today.

        Returns:
            list[ClockEvent]: list of today's clock events (can be empty)
        """
        pass

    def is_clocked_in_today(self) -> bool:
        """
        Check if the employee is currently clocked in (today).

        Returns:
            bool: True if clocked in
        """
        # Get last today event and check if it's a clock in action
        events = self.get_clock_events_today()
        return bool(events) and (events[-1].action == ClockAction.CLOCK_IN)

    def get_worked_time_today(self, now: dt.time = None) -> dt.timedelta:
        """
        Get employee's worked time today.
        If the employee is clocked in the optional argument can be passed to calculate the worked time
        until the given hour (typically now). If None, the worked time is calculated based on previous
        clock events.
        
        Parameters:
            now: used when the employee is clocked in to calculate the worked time until the given hour
        Returns:
            timedelta: delta time object
        """
        pass

    def get_monthly_balance(self) -> dt.timedelta:
        """
        Get employee's balance for the current month.

        Returns:
            timedelta: delta time object
        """
        pass

    def register_clock(self, event: ClockEvent) -> None:
        """
        Register a clock in/out event.

        Parameters:
            event: clock event object
        Raise:
            ValueError: double clock in/out detected
        """
        pass
