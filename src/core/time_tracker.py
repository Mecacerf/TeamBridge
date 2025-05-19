#!/usr/bin/env python3
"""
File: time_tracker.py
Author: Bastian Cerf
Date: 17/02/2025
Description: 
    Base abstract class for accessing and managing an employee's attendance data.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from contextlib import contextmanager
from enum import Enum
import datetime as dt

###############################################
#   Time tracker related errors declaration   #
###############################################

class TimeTrackerReadException(Exception):
    """
    Custom exception for illegal read operation.
    """
    def __init__(self, message="Illegal read operation attempted"):
        super().__init__(message)

class TimeTrackerWriteException(Exception):
    """
    Custom exception for illegal write operation.
    """
    def __init__(self, message="Illegal write operation attempted"):
        super().__init__(message)

class TimeTrackerOpenException(Exception):
    """
    Custom exception for time tracker opening errors.
    """
    def __init__(self, message="Unable to open the time tracker"):
        super().__init__(message)

class TimeTrackerDateException(Exception):
    """
    Custom exception for time tracker date errors.
    """
    def __init__(self, message="The operation failed due to a date error"):
        super().__init__(message)

class TimeTrackerEvaluationException(Exception):
    """
    Custom exception for time tracker evaluation errors.
    """
    def __init__(self, message="The data evaluation failed"):
        super().__init__(message)

class TimeTrackerSaveException(Exception):
    """
    Custom exception for time tracker saving errors.
    """
    def __init__(self, message="The time tracker hasn't been saved properly"):
        super().__init__(message)

class TimeTrackerCloseException(Exception):
    """
    Custom exception for time tracker closing errors.
    """
    def __init__(self, message="The time tracker hasn't been properly closed"):
        super().__init__(message)

###############################################
#    Clocking event dataclass declaration     #
###############################################

class ClockAction(Enum):
    """
    Clock actions enumeration.
    """
    CLOCK_IN = 0
    CLOCK_OUT = 1

@dataclass(frozen=True)
class ClockEvent:
    """
    Simple container for a clock event.

    Attributes:
        time (datetime.time): time in the day at which the event occurred
        action (ClockAction): related clock action
    """
    time: dt.time
    action: ClockAction
    
###############################################
#           Attendance error types            #
###############################################

@dataclass(frozen=True)
class AttendanceError:
    """
    Simple attendance error class.

    Attributes:
        description (str): concise error description
    """
    description: str

CLOCK_EVENT_MISSING = AttendanceError("A clock event is missing.")
CLOCK_EVENTS_UNORDERED = AttendanceError("Clock events times are unordered.")

###############################################
#    Time tracker base class declaration      #
###############################################

class BaseTimeTracker(ABC):
    """
    Base abstract class for accessing and managing an employee's attendance data.

    This interface handles attendance data for a single employee over the course of one year.
    It provides functionality to manage and retrieve clock-in and clock-out events across 
    multiple dates within that year.

    The `current_date` property controls the working date, and the `data_year` property 
    indicates the required year for all operations. If a date outside of the specified year 
    is used, a `TimeTrackerDateException` is raised.

    This object is stateful since it relies on the `current_date` property for the different
    reading and writing operations. It is therefore not thread-safe.

    In addition to reading and modifying raw attendance data, the time tracker can perform 
    calculations based on that data. Raw data are always accessible through properties, 
    while calculated values (prefixed with `read_`) become available only after calling 
    the `evaluate()` method. These calculated properties are only valid when the
    `readable` property is `True`.
    """

    def __init__(self, employee_id: str, date: Optional[dt.date] = None):
        """
        Opens the employee's data for the given date.

        Args:
            employee_id (str): unique identifier for the employee
            date (Optional[datetime.date]): the current date pointer, defaults to first of January

        Raises:
            TimeTrackerOpenException: raised when data cannot be opened
            See subclass implementations for more detailed reasons.
        """
        self._employee_id = employee_id
        self._date = date

        try:
            # Call the setup method to get access to properties
            self._setup()
        except Exception as e:
            raise TimeTrackerOpenException() from e

        # Date defaults to the first of January when not provided
        if self._date is None:
            self._date = dt.date(year=self.data_year, month=1, day=1)

    def __enter__(self):
        # Allow the use of a context manager
        return self

    @abstractmethod
    def _setup(self):
        """
        Internally setup the data access. Properties must then be accessible.
        Note that the current date may not be set at this point.
        """
        pass

    @property
    @abstractmethod
    def firstname(self) -> str:
        """
        Get employee's firstname.

        Returns:
            str: employee's firstname
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get employee's name.

        Returns:
            str: employee's name
        """
        pass

    @property
    @abstractmethod
    def data_year(self) -> int:
        """
        Get the year of the information held by the time tracker.

        Returns:
            int: year of the information
        """
        pass

    @property
    def current_date(self) -> dt.date:
        """
        Get the current date.

        Returns:
            datetime.date: current date pointer
        """
        return self._date

    @current_date.setter
    def current_date(self, new_date: dt.date):
        """
        Set the current date.
        
        Args:
            new_date (datetime.date): new date pointer
        """ 
        self._date = new_date

    @contextmanager
    def date_context(self, temp_date: dt.date):
        """
        Temporarily set `current_date` to a different date and restore it afterward.
        Useful for scoped operations like aggregations.

        Args:
            temp_date (datetime.date): the temporary date to set
        """
        original_date = self.current_date
        self.current_date = temp_date
        try:
            yield
        finally:
            # Current date is always restored, even if an error occurred
            self.current_date = original_date

    @property
    @abstractmethod
    def clock_events(self) -> list[ClockEvent]:
        """
        Retrieve all clock-in and clock-out events for the current date.

        Events are supposed to be ordered chronologically. They follow the 
        expected pattern:
        clock-in, clock-out, clock-in, clock-out, etc. If a corresponding 
        event is missing (e.g., a missing clock-out after a clock-in), `None` 
        is inserted in its place to preserve the sequence structure.

        Returns:
            list[ClockEvent]: A list of clock events for the current date.
                The list may be empty if no events are recorded for the date.
        """
        pass

    @property
    def is_clocked_in(self) -> bool:
        """
        Check if the employee is clocked in at current date.

        Returns:
            bool: True if clocked in
        """
        # Get last today event and check if it's a clock in action
        events = self.clock_events
        return bool(events) and (events[-1].action == ClockAction.CLOCK_IN)

    @property
    @abstractmethod
    def readable(self) -> bool:
        """
        Check if the reading functions are accessible at this moment. 
        They are initially not accessible (since the opened data are not evaluated) 
        and get accessible after an evaluation is performed.

        Returns:
            bool: reading flag
        """
        pass

    def check_date_error(self) -> Optional[AttendanceError]:
        """
        Analyze the current date and check for clocking errors.

        This method verifies that:
        - The day finishes with a clock-out event
        - There is no missing clock event
        - Clock events times are in ascending order

        Returns:
            Optional[AttendanceError]: Optionally return an `AttendanceError`
                object corresponding to the error found
        """
        events = self.clock_events

        # Check 1: day finishes with a clock-out
        if events[-1].action != ClockAction.CLOCK_OUT:
            return CLOCK_EVENT_MISSING
        # Check 2: no missing (None) clock event
        if any([evt == None for evt in events]):
            return CLOCK_EVENT_MISSING
        # Check 3: events times are in ascending order
        if any(e1.time >= e2.time for e1, e2 in zip(events, events[1:])):
            return CLOCK_EVENTS_UNORDERED 
        
        return None

    def check_attendance_errors(self) -> dict[dt.date, AttendanceError]:
        """
        Analyze all past days of the year and check for clocking errors.

        This method internally uses `time_tracker.check_date_error()` on each
        past day of the year.

        Returns:
            dict[datetime.date, AttendanceError]: A dictionary of error dates
                as keys and error type as values. The dictionary is empty if no 
                error is found.
        """
        day_delta = dt.timedelta(days=1)
        end_date = self.current_date
        # Dictionary of days with an attendance error
        errors = {}
        # Iterate all days from the first of January until the current day
        # and search for errors
        date = dt.date(day=1, month=1, year=self.data_year)
        while date < end_date:
            with self.date_context(date):
                error = self.check_date_error()
                if error:
                    errors[date] = error
            date += day_delta

        return errors

    @abstractmethod
    def read_day_schedule(self) -> dt.timedelta:
        """
        Get employee's daily schedule at current date (how much time he's supposed to work).

        Accessible when the `readable` property is `True`.

        Returns:
            datetime.timedelta: schedule for the day as a timedelta
        """
        pass

    @abstractmethod
    def read_day_balance(self) -> dt.timedelta:
        """
        Get employee's balance at current date (remaining time he's supposed to work).
        If the employee is clocked in the value is calculated based on the time the last evaluation
        has been done. This value is always in the range [00:00, 23:59].

        Special case: if the current date is a day that has already passed this year and the 
        employee has forgotten to clock out on that day, the calculated value depends on the time of 
        the current day, which is not conceptually correct.
        
        Accessible when the `readable` property is `True`.

        Returns:
            datetime.timedelta: balance for the day as a timedelta
        """
        pass

    @abstractmethod
    def read_day_worked_time(self) -> dt.timedelta:
        """
        Get employee's worked time at current date.
        If the employee is clocked in the value is calculated based on the time the last evaluation
        has been done.

        Special case: if the current date is a day that has already passed this year and the 
        employee has forgotten to clock out on that day, the calculated value depends on the time of 
        the current day, which is not conceptually correct.
        
        Accessible when the `readable` property is `True`.
        
        Returns:
            datetime.timedelta: worked time for the day as a timedelta
        """
        pass

    @abstractmethod
    def read_month_balance(self) -> dt.timedelta:
        """
        Get employee's balance for the current month (depends on current date).
        If the employee is clocked in the value is calculated based on the time the last evaluation
        has been done.

        Special case: if the employee has forgotten to clock out on a past day, the balance 
        for that day may be calculated using today's time, affecting the total. This 
        value is only accurate if all prior clocking actions in the month are correct.
        You can validate the data using `check_attendance_errors()`.
        
        Accessible when the `readable` property is `True`.

        Returns:
            datetime.timedelta: balance for the month as a timedelta
        """
        pass

    @abstractmethod
    def read_year_balance(self) -> dt.timedelta:
        """
        Get employee's year-to-date balance.

        Special case: if the employee has forgotten to clock out on a past day, the balance 
        for that day may be calculated using today's time, affecting the total. This 
        value is only accurate if all prior clocking actions are correct.
        You can validate the data using `check_attendance_errors()`.

        Accessible when the `readable` property is `True`.

        Returns:
            datetime.timedelta: balance for the year as a timedelta
        """
        pass

    def read_year_balance_until_yesterday(self) -> dt.timedelta:
        """
        Get the employee's accumulated balance from the start of the year up to yesterday.

        This is often more relevant for employees than the full year-to-date balance,
        especially when today's work is still in progress.

        Special case: if the employee has forgotten to clock out on a past day, the balance 
        for that day may be calculated using today's time, affecting the total. This 
        value is only accurate if all prior clocking actions are correct.
        You can validate the data using `check_attendance_errors()`.

        Accessible when the `readable` property is `True`.

        Returns:
            datetime.timedelta: balance from the start of the year up to (but excluding) today.
        """
        return (self.read_year_balance() - self.read_day_balance())

    @abstractmethod
    def read_remaining_vacation(self) -> float:
        """
        Get the number of vacation days the employee still has available (not yet planned or used).

        Accessible when the `readable` property is `True`.

        Returns:
            float: number of remaining vacation days
        """
        pass

    @abstractmethod
    def read_month_vacation(self) -> float:
        """
        Get the total number of vacation days planned for the current month.

        Accessible when the `readable` property is `True`.

        Returns:
            float: number of planned vacation days for the current month.
        """
        pass

    @abstractmethod
    def read_day_vacation(self) -> float:
        """
        Get the vacation ratio for the current date.

        Typically returns a value in the range [0.0, 1.0], where:
        - 1.0 represents a full vacation day,
        - 0.5 represents a half-day,
        - 0.0 means no vacation.

        Accessible when the `readable` property is `True`.

        Returns:
            float: vacation ratio for the current date.
        """
        pass

    def read_year_vacation(self) -> float:
        """
        Get the total number of vacation days planned for the year.
       
        Accessible when the `readable` property is `True`.

        Returns:
            float: number of planned vacation days for the year.
        """
        # Iterate the months and sum the vacation days
        total_days = 0.0
        for month in range(1, 13):
            # Read the planned vacations for the month
            with self.date_context(dt.date(day=1, month=month, year=self.data_year)):
                total_days += self.read_month_vacation()

        return total_days

    @abstractmethod
    def register_clock(self, event: ClockEvent) -> None:
        """
        Register a clock in/out event at the current date.

        After a clock event is registered, the `readable` property gets `False` and the reading
        functions are not available until a new evaluation is performed.

        Args:
            event (ClockEvent): clock event to register at current date
        
        Raises:
            TimeTrackerWriteException: raised when the registering fails
            See subclass implementations for more detailed reasons.
        """
        pass

    @abstractmethod
    def evaluate(self) -> None:
        """
        Evaluate the employee's data. Depending on the implementation in use, this process may take 
        some time. Once complete and successful, the 'readable' property will be set to 'True', 
        meaning that all 'read_' prefixed methods will be available for use.

        Raises:
            TimeTrackerEvaluationException: raised when the evaluation fails
            See subclass implementations for more detailed reasons.
        """
        pass

    @abstractmethod
    def save(self) -> None:
        """
        Save changes. 
        
        This must be called after changes have been done (typically after new clock events have been 
        registered) to save the modifications.

        Raises:
            TimeTrackerSaveException: raised when the saving fails
            See subclass implementations for more detailed reasons.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Close the time tracker. It should not be used again after this call.

        This does not automatically save the data. In most cases, the `save()` method should be called
        before this.

        Raises:
            TimeTrackerCloseException: raised when the closing fails
            See subclass implementations for more detailed reasons.
        """
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Ensures the time tracker is properly closed when exiting the context manager.

        If an exception occurs in the `with` block and `close()` also fails, the original
        exception is re-raised and the close error is chained to it. If only the close
        fails, that exception is raised. Otherwise, lets Python handle any other exception.
        """
        try:
            self.close()
        except TimeTrackerCloseException as close_ex:
            if exc_val:
                # If there was an exception during the context block, chain close error to it
                raise exc_val from close_ex
            # No prior exception: just raise the close failure
            raise close_ex
        return False  # Propagate any exception from the context block
