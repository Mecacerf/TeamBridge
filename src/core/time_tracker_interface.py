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

# Import datetime for dates and times manipulation
import datetime as dt
# Enumeration module
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
    
class IllegalReadException(Exception):
    """
    Custom exception for illegal read operations.
    """
    def __init__(self, message="Illegal read operation attempted"):
        super().__init__(message)

class ITodayTimeTracker:
    """
    Interface for accessing and managing an employee's daily attendance data.

    This interface is designed with simplicity in mind: it is initialized for a specific date, 
    after which all operations relate exclusively to times within that date. By focusing on a single 
    day at a time, the interface avoids the complexity of date management, allowing straightforward 
    retrieval and manipulation of attendance events such as clock-ins, clock-outs, and breaks.
    
    Typical use cases include daily time tracking, attendance validation, and working hours reporting.
    """

    def __init__(self, employee_id: str, date: dt.date):
        """
        Open the employee's data for given date.

        Parameters:
            id: employee unique ID
            date: date index
        Raise:
            ValueError: employee not found
            ValueError: wrong / unavailable date time
        """
        pass

    def get_firstname(self) -> str:
        """
        Get employee's firstname.
        Always accessible.

        Returns:
            str: employee's firstname
        """
        pass

    def get_name(self) -> str:
        """
        Get employee's name.
        Always accessible.

        Returns:
            str: employee's name
        """
        pass

    def get_clock_events_today(self) -> list[ClockEvent]:
        """
        Get all clock-in/out events for the date.
        Always accessible.
        
        Returns:
            list[ClockEvent]: list of today's clock events (can be empty)
        """
        pass

    def is_clocked_in_today(self) -> bool:
        """
        Check if the employee is currently clocked in (today).
        Always accessible.

        Returns:
            bool: True if clocked in
        """
        # Get last today event and check if it's a clock in action
        events = self.get_clock_events_today()
        return bool(events) and (events[-1].action == ClockAction.CLOCK_IN)

    def is_readable(self) -> bool:
        """
        Check if the reading functions are accessible at this moment. 
        They are initially not accessible (since the opened data are not evaluated) and
        get accessible after an evaluation is performed.

        Returns:
            bool: reading flag
        """
        pass

    def get_daily_schedule(self) -> dt.timedelta:
        """
        Get employee's daily schedule (how much time he's supposed to work).
        Accessible when is_readable() returns True.

        Returns:
            timedelta: daily schedule
        """
        pass

    def get_daily_balance(self) -> dt.timedelta:
        """
        Get employee's daily balance (remaining time he's supposed to work).
        If the employee is clocked in the value is calculated based on the time the last evaluation
        has been done.
        Accessible when is_readable() returns True.

        Returns:
            timedelta: daily balance
        """
        pass

    def get_daily_worked_time(self) -> dt.timedelta:
        """
        Get employee's worked time for the day.
        If the employee is clocked in the value is calculated based on the time the last evaluation
        has been done.
        Accessible when is_readable() returns True.
        
        Returns:
            timedelta: delta time object
        """
        pass

    def get_monthly_balance(self) -> dt.timedelta:
        """
        Get employee's balance for the current month.
        Accessible when is_readable() returns True.

        Returns:
            timedelta: delta time object
        """
        pass

    def register_clock(self, event: ClockEvent) -> None:
        """
        Register a clock in/out event.
        After a clock event is registered, the reading functions are not available until a
        new evaluation is performed.

        Parameters:
            event: clock event object
        Raise:
            ValueError: double clock in/out detected
        """
        pass

    def commit(self) -> None:
        """
        Commit changes. This must be called after changes have been done (typically after new clock events
        have been registered) to save the modifications.
        """
        pass

    def evaluate(self) -> None:
        """
        Start an employee's data evaluation. This must be done after changes have been committed.
        Once done, the reading functions are available again and will provide up to date results.
        """
        pass

    def close(self) -> None:
        """
        Close the time tracker, save and release resources.
        """
        pass
