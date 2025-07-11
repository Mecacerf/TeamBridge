#!/usr/bin/env python3
"""
File: time_tracker.py
Author: Bastian Cerf
Date: 17/02/2025
Description:
    Base abstract classes for accessing and managing an employee's data.
    Three interfaces that inherit from each other are provided:
    - The `Employee` just give access to basic information that aren't
        related to a specific date and time (such as name, id).
    - The `TimeTracker` offers simple access to raw attendance data. It
        allows to read and write clock events, vacation and attendance
        errors.
    - The `TimeTrackerAnalyzer` goes one step further by analyzing and
        computing the attendance data to provide different information,
        such as total of scheduled work, worked time, vacation and so
        on. The computing engine is implementation dependent and may not
        be Python. For this reason the access to these data is restricted
        by a flag `analyzed`. The data must be analyzed before access.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
from abc import ABC, abstractmethod
from typing import Optional, Type, Any, ClassVar
from types import TracebackType
from dataclasses import dataclass, field
from enum import Enum, auto
import datetime as dt
from threading import Lock

########################################################################
#              Time tracker related errors declaration                 #
########################################################################


class TimeTrackerException(Exception):
    """Base type for all exceptions related to the time tracker."""

    pass


class TimeTrackerReadException(TimeTrackerException):
    """Custom exception for illegal read operation."""

    def __init__(self, message: str = "Illegal read operation attempted."):
        super().__init__(message)


class TimeTrackerWriteException(TimeTrackerException):
    """Custom exception for illegal write operation."""

    def __init__(self, message: str = "Illegal write operation attempted."):
        super().__init__(message)


class TimeTrackerValueException(TimeTrackerException):
    """Custom exception for value errors."""

    def __init__(self, message: str = "Got an unexpected value."):
        super().__init__(message)


class TimeTrackerOpenException(TimeTrackerException):
    """Custom exception for time tracker opening errors."""

    def __init__(self, message: str = "Unable to open the time tracker."):
        super().__init__(message)


class TimeTrackerDateException(TimeTrackerException):
    """Custom exception for time tracker date errors."""

    def __init__(self, message: str = "Date is outside accepted range."):
        super().__init__(message)


class TimeTrackerAnalysisException(TimeTrackerException):
    """Custom exception for time tracker analysis errors."""

    def __init__(self, message: str = "Data analysis failed."):
        super().__init__(message)


class TimeTrackerSaveException(TimeTrackerException):
    """Custom exception for time tracker saving errors."""

    def __init__(self, message: str = "Failed to save."):
        super().__init__(message)


class TimeTrackerCloseException(TimeTrackerException):
    """Custom exception for time tracker closing errors."""

    def __init__(self, message: str = "Failed to close."):
        super().__init__(message)


########################################################################
#                Clocking event dataclass declaration                  #
########################################################################


class ClockAction(Enum):
    """Clock actions enumeration."""

    CLOCK_IN = auto()  # The employee starts working
    CLOCK_OUT = auto()  # The employee finishes working

    def __str__(self):
        return self.name.lower().replace("_", "-")


@dataclass(frozen=True)
class ClockEvent:
    """
    Simple container for a clock event.

    Attributes:
        time (datetime.time): Time in the day at which the event occurred.
        action (ClockAction): Related clock action.

    Factory:
        midnight_rollover(): Create a midnight rollover special event.
    """

    time: dt.time
    action: ClockAction
    _midnight_rollover: bool = field(default=False, repr=True, compare=True)

    # Class attributes
    _midnight_rollover_instance: ClassVar["Optional[ClockEvent]"] = None
    _singleton_lock: ClassVar[Lock] = Lock()

    @classmethod
    def midnight_rollover(cls) -> "ClockEvent":
        """
        Get a midnight rollover clock-out event. This is a singleton
        with thread-safe access.

        This special `ClockEvent` type is used to end a day where an
        employee was still working at midnight. The next day must start
        with a clock-in event at midnight.
        """
        # Create the singleton instance if not existing
        if cls._midnight_rollover_instance is None:
            with cls._singleton_lock:
                # Double check before entering the critical section
                if cls._midnight_rollover_instance is None:
                    cls._midnight_rollover_instance = cls(
                        time=dt.time(0, 0),
                        action=ClockAction.CLOCK_OUT,
                        _midnight_rollover=True,
                    )

        return cls._midnight_rollover_instance

    def __str__(self):
        if self._midnight_rollover:
            return "midnight-rollover at 24:00"
        return f"{self.action} at {self.time.strftime('%H:%M')}"


########################################################################
#                   Employee base class declaration                    #
########################################################################


class Employee(ABC):
    """
    The `Employee` is the base interface that provides access to general
    information about an employee, such as his name, firstname, ID or
    any data that is static.
    This interface doesn't provide any setter because the implementation
    is supposed to be read-only. Implementation(s) of this interface
    works with IO resources (file, database). A context manager can be
    used to automatically manage resource lifecycle.
    """

    def __init__(self, employee_id: str, *kargs: Any, **kwargs: Any) -> None:
        """
        Initialize for the specified employee.

        Args:
            employee_id (str): The unique identifier of the employee.
            kwargs (Any): Any argument the subclass may need to setup.

        Raises:
            TimeTrackerOpenException: If the time tracker data cannot be
                opened.
            See chained exceptions for specific failure reasons.
        """
        self._employee_id = employee_id

        try:
            self._setup(*kargs, **kwargs)
        except Exception as e:
            raise TimeTrackerOpenException() from e

    def __enter__(self) -> "Employee":
        # Enter function when using a context manager
        return self

    @abstractmethod
    def _setup(self, *kargs: Any, **kwargs: Any):
        """
        Called during object initialization to setup access to the data
        storage. Any exception can be raised in this method on failure,
        it will be chained to the more general `TimeTrackerOpenException`.
        Once the setup successes, object properties must be accessible.
        """
        pass

    @property
    def employee_id(self) -> str:
        """
        Get employee's id.

        Returns:
            str: Employee's id.
        """
        return self._employee_id

    @property
    @abstractmethod
    def firstname(self) -> str:
        """
        Get employee's firstname.

        Returns:
            str: Employee's firstname.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get employee's name.

        Returns:
            str: Employee's name.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Close the `Employee`. It should not be used again after this
        call.

        Raises:
            TimeTrackerCloseException: Raised when the closing fails.
            See chained exceptions for specific failure reasons.
        """
        pass

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        """
        Ensures the `Employee` is properly closed when exiting the
        context manager.

        If an exception occurs in the `with` block and `close()` also
        fails, the original exception is re-raised and the close error
        is chained to it. If only the close fails, that exception is
        raised. Otherwise, lets Python handle any other exception.
        """
        try:
            self.close()
        except TimeTrackerCloseException as close_ex:
            if exc_val:
                # If there was an exception during the context block,
                # chain the close error to it
                raise exc_val from close_ex
            # No prior exception: just raise the close failure
            raise close_ex
        return False  # Propagate any exception from the context block

    def __str__(self) -> str:
        return f"Employee['{self.employee_id}' {self.firstname} {self.name}]"


########################################################################
#                Time tracker base class declaration                   #
########################################################################


class TimeTracker(Employee, ABC):
    """
    The `TimeTracker` is a specialization of the `Employee` interface
    that provides methods to read and write clock events (such as
    clock-ins and clock-outs), day vacation and day attendance error. It
    focuses on single days and does not evaluate any given data in any
    way. The `save()` method allows to write the data to the storage
    system. Each `TimeTracker` instance is bound to a specific year,
    and all read or write operations must relate to that year.
    """

    def __enter__(self) -> "TimeTracker":
        # Enter function when using a context manager
        return self

    @property
    @abstractmethod
    def tracked_year(self) -> int:
        """
        Get the year each read or write operations must relate to.

        Note that each read or write operation attempted on another year
        will raise a `TimeTrackerDateException`.

        Returns:
            int: Tracked year.

        Raises:
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
        """
        pass

    @property
    @abstractmethod
    def opening_day_schedule(self) -> dt.timedelta:
        """
        Get the initial working day schedule at the beginning of the
        year.

        This value represents the expected working time on a regular day,
        typically based on the employee's work percentage (e.g., full-time,
        part-time).

        This value is the reference time set at year beginning. It
        may change during the year, for example after a work load
        modification. See `read_month_expected_daily_schedule()` and
        `read_day_schedule()` from the `TimeTrackerAnalyzer` for a value
        dependent to the date.

        Returns:
            datetime.timedelta: Working day schedule at year beginning.

        Raises:
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
        """
        pass

    @property
    @abstractmethod
    def opening_balance(self) -> dt.timedelta:
        """
        Returns:
            datetime.timedelta: Initial balance at year beginning.

        Raises:
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
        """
        pass

    @property
    @abstractmethod
    def opening_vacation_days(self) -> float:
        """
        Returns:
            float: Initial number of available vacation days at year
                beginning.

        Raises:
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
        """
        pass

    @property
    @abstractmethod
    def max_clock_events_per_day(self) -> int:
        """
        Get the maximal number of clock events the current implementation
        is able to register for one day. This value is implementation
        dependent.

        Returns:
            int: Maximal number of clock events for one day.
        """
        pass

    @abstractmethod
    def get_clocks(self, date: dt.date | dt.datetime) -> list[Optional[ClockEvent]]:
        """
        Retrieve all clock-in and clock-out events on a given date.

        The clock events follow the expected pattern:
        clock-in, clock-out, clock-in, clock-out, etc. If a corresponding
        event is missing (e.g., a missing clock-out after a clock-in),
        `None` is inserted in its place to preserve the sequence
        structure.

        Events are supposed to be ordered chronologically without any
        hole (None value), however they may not if an error exists for
        the date. Using an `AttendanceValidator` can help finding such
        special cases.

        Args:
            date (datetime.date): The date to retrieve clock events.

        Returns:
            list[Optional[ClockEvent]]: A list of clock events for the date.
                The list may be empty if no events are recorded.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`.
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
        """
        pass

    @abstractmethod
    def register_clock(self, date: dt.date | dt.datetime, event: ClockEvent):
        """
        Register a clock in/out event on the given date.

        The clock event is written in the next available slot for the
        day, eventually leaving empty slots if two same actions are
        registered one after the other.

        Args:
            event (ClockEvent): Clock event to register on given date.
            date (datetime.date): The date to register the clock event.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`.
            TimeTrackerWriteException: Raised on writing error.
            TimeTrackerSaveException: Unable to save the tracker in the
                local cache.
            See chained exceptions for specific failure reasons.
        """
        pass

    @abstractmethod
    def write_clocks(
        self, date: dt.date | dt.datetime, events: list[Optional[ClockEvent]]
    ):
        """
        Write the given clock events list on the given date, overwriting
        existing entries.

        The clock events are given in the same format they are retrieved
        using `get_clocks()`. The events are not added to the next
        available slot, like `register_clock()` does. Existing events
        are overwritten.

        The events list must not be greater than `max_clock_events_per_day`,
        or a `TimeTrackerWriteException` will be raised.

        Args:
            events (list[Optional[ClockEvent]]): List of clock events to
                write on the given date.
            date (datetime.date): The date to write the clock events.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`.
            TimeTrackerWriteException: Raised on writing error.
            TimeTrackerSaveException: Unable to save the tracker in the
                local cache.
            See chained exceptions for specific failure reasons.
        """
        pass

    def is_clocked_in(self, date: dt.date | dt.datetime) -> bool:
        """
        Check if the employee is clocked in on a given date.

        The method just checks that the last registered event is a
        clock-in action.

        Args:
            date (datetime.date): The date to check.

        Returns:
            bool: True if clocked in.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`.
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
        """
        events = self.get_clocks(date)
        return (
            bool(events)  # Not empty
            and events[-1] is not None
            and (events[-1].action == ClockAction.CLOCK_IN)
        )

    @abstractmethod
    def set_vacation(self, date: dt.date | dt.datetime, day_ratio: float):
        """
        Set the vacation ratio for the day, from 0.0 (no vacation) to
        1.0 (full-day off).

        Args:
            date (datetime.date): The date to set data.
            day_ratio (float): Vacation ratio for the day.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`.
            TimeTrackerWriteException: Raised on writing error.
            TimeTrackerSaveException: Unable to save the tracker in the
                local cache.
            See chained exceptions for specific failure reasons.
        """
        pass

    @abstractmethod
    def get_vacation(self, date: dt.date | dt.datetime) -> float:
        """
        Get the vacation ratio for the day, from 0.0 (no vacation) to
        1.0 (full-day off).

        Args:
            date (datetime.date): The date to read data.

        Returns:
            float: Vacation ratio for the date.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`.
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
        """
        pass

    @abstractmethod
    def set_paid_absence(self, date: dt.date | dt.datetime, day_ratio: float):
        """
        Set the paid absence ratio for the day, from 0.0 (no absence) to
        1.0 (full-day absence). Paid absences refer to time off that is
        not counted as vacation, such as sick leave or accidents.

        Args:
            date (datetime.date): The date to set data.
            day_ratio (float): Paid absence ratio for the day.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`.
            TimeTrackerWriteException: Raised on writing error.
            TimeTrackerSaveException: Unable to save the tracker in the
                local cache.
            See chained exceptions for specific failure reasons.
        """
        pass

    @abstractmethod
    def get_paid_absence(self, date: dt.date | dt.datetime) -> float:
        """
        Get the paid absence ratio for the day, from 0.0 (no absence) to
        1.0 (full-day absence). Paid absences refer to time off that is
        not counted as vacation, such as sick leave or accidents.

        Args:
            date (datetime.date): The date to read data.

        Returns:
            float: Paid absence ratio for the date.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`.
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
        """
        pass

    @abstractmethod
    def set_attendance_error(
        self, date: dt.date | dt.datetime, error_id: Optional[int]
    ):
        """
        Set or reset an attendance error on the given date.

        Only one attendance error can exist for a date, thus setting a
        new one will overwrite the previous value.

        Args:
            date (datetime.date): The date to set data.
            error_id (Optional[int]): The error ID to set or `None` to
                reset.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`.
            TimeTrackerWriteException: Raised on writing error.
            TimeTrackerSaveException: Unable to save the tracker in the
                local cache.
            See chained exceptions for specific failure reasons.
        """
        pass

    @abstractmethod
    def get_attendance_error(self, date: dt.date | dt.datetime) -> Optional[int]:
        """
        Get an attendance error on the given date.

        Args:
            date (datetime.date): To date to read data.

        Returns:
            Optional[int]: The error on the given date or `None` if none
                exists.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`.
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
        """
        pass

    @abstractmethod
    def get_attendance_error_desc(self, error_id: int) -> str:
        """
        Get the description for the given error identifier.

        Args:
            error_id (int): Error identifier.

        Returns:
            str: Error description.

        Raises:
            TimeTrackerValueException: No description associated with
                given identifier.
        """
        pass

    @abstractmethod
    def save(self):
        """
        Save the modifications on the time trackers repository.

        Raises:
            TimeTrackerSaveException: Failed to save.
            See chained exceptions for specific failure reasons.
        """
        pass


########################################################################
#                Time tracker analyzer class declaration               #
########################################################################


class TimeTrackerAnalyzer(TimeTracker, ABC):
    """
    The `TimeTrackerAnalyzer` interface extends the `TimeTracker`
    interface by providing methods to analyze an employee's data,
    including day, month, and year balances, dynamic daily schedules
    based on weekdays and vacations, and more.

    Data is not immediately available. It becomes accessible only after
    calling the `analyze()` method with a specified `target_datetime`.
    This datetime defines the point in time the analysis is based on.
    For example, if the tracker is analyzed at 10:00 on a given day and
    the employee clocked in at 08:00, the worked time will be 2 hours.
    If analyzed at 11:00, it will be 3 hours. Once the data is analyzed,
    the `analyzed` property is `True`. Note that trying to access the
    `read_` prefixed methods while the tracker is not analyzed will
    result in a `TimeTrackerReadException`.

    The analyzer also performs basic attendance error detection, such as
    identifying missing clock-out events. These errors can be retrieved
    using `read_attendance_error(date)`. This differs from the
    `set/get_attendance_error()` methods, which are used to manually
    define or retrieve custom errors.
    """

    def __init__(self, employee_id: str, *kargs: Any, **kwargs: Any) -> None:
        """
        Initialize the `TimeTracker`.
        """
        self._target_dt: Optional[dt.datetime] = None
        super().__init__(employee_id, *kargs, **kwargs)

    def __enter__(self) -> "TimeTrackerAnalyzer":
        # Enter function when using a context manager
        return self

    @property
    def target_datetime(self) -> Optional[dt.datetime]:
        """
        Returns:
            Optional[datetime.datetime]: The point in time the analysis
                is based on or `None` if not analyzed.
        """
        return self._target_dt

    @property
    def analyzed(self) -> bool:
        """
        Same as checking if `target_datetime` is not `None`.

        Returns:
            bool: `True` if analyzed, meaning the `read_` prefixed methods
                are available for use. `False` otherwise.
        """
        return self.target_datetime is not None

    def analyze(self, target_datetime: dt.datetime):
        """
        Analyze the employee's data at given `target_datetime`.

        This method processes the raw attendance data based on the
        `target_datetime`, enabling the `read_` prefixed methods on
        success. The `analyzed` property gets `True` when this method
        is called without any exception raised.

        Depending on the underlying implementation, this operation may
        take some time.

        Args:
            target_datetime (datetime.datetime): Target point in time
                to analyze the data.

        Raises:
            TimeTrackerAnalysisException: The analysis failed.
            TimeTrackerDateException: Target datetime is outside the
                `tracked_year`.
            See chained exceptions for specific failure reasons.
        """
        if target_datetime.year != self.tracked_year:
            raise TimeTrackerDateException(
                f"'{target_datetime}' is outside of tracked year {self.tracked_year}."
            )

        self._target_dt = target_datetime

        try:
            self._analyze_internal()
        except Exception as e:
            self._target_dt = None  # `analyzed` stays `False` on failure
            raise TimeTrackerAnalysisException() from e

    @abstractmethod
    def _analyze_internal(self):
        """
        Implementation of the analysis method by the subclasses. Any
        error raised in this method will be chained to the more general
        `TimeTrackerAnalysisException`.
        """
        pass

    @abstractmethod
    def read_day_schedule(self, date: dt.date | dt.datetime) -> dt.timedelta:
        """
        Get employee's daily schedule on a given date (how much time
        he's supposed to work).

        This method is only available when the `analyzed` property is
        `True`.

        Args:
            date (datetime.date): The date to read data.

        Returns:
            datetime.timedelta: Schedule for the day as a timedelta.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`.
            TimeTrackerReadException: The reading methods are unavailable
                (see `analyzed` property).
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
            See chained exceptions for specific failure reasons.
        """
        pass

    @abstractmethod
    def read_day_worked_time(self, date: dt.date | dt.datetime) -> dt.timedelta:
        """
        Get employee's worked time on a given date.

        If the employee is clocked in on that date, the worked time is
        computed relative to `target_datetime.time()`. For example, if
        the employee clocked in at 8:00 and the `target_datetime.time()`
        is 10:00, the worked time is 2:00.

        Warning; implementation dependent behavior:
        The worked time (as well as many other values) may be calculated
        relative to `target_datetime.time()` disregarding to the
        `target_datetime.date()`. Typically, if the given date is before
        the target date and the last clock-out is missing for that date,
        the worked time may still be calculated relative to the
        `target_datetime.time()`.

        In summary, always check that no attendance error exists for the
        date before relying on the returned value, especially when
        reading a date before the `target_datetime.date()`.

        This method is only available when the `analyzed` property is
        `True`.

        Args:
            date (datetime.date): The date to read data.

        Returns:
            datetime.timedelta: Worked time for the day as a timedelta.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`.
            TimeTrackerReadException: The reading methods are unavailable
                (see `analyzed` property).
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
            See chained exceptions for specific failure reasons.
        """
        pass

    @abstractmethod
    def read_day_balance(self, date: dt.date | dt.datetime) -> dt.timedelta:
        """
        Get the employee's time balance on a given date.

        The balance represents the remaining work time the employee is
        expected to complete on the specified day. A positive balance
        means the employee worked more than the expected daily schedule.

        The balance is 00:00 for all days after the `target_datetime.date`,
        even if some clock events are already registered for that date.
        In other words, the balance can be thought as:

            balance = day_worked_time - day_schedule
                if day <= `target_datetime.date` else 0

        If the employee is clocked in on that date, the worked time is
        computed relative to `target_datetime.time()`, which involves
        the same limitations as the `read_day_worked_time()` method.

        This method is only available when the `analyzed` property is
        `True`.

        Args:
            date (datetime.date): The date to read data.

        Returns:
            datetime.timedelta: The time balance for the specified date.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`.
            TimeTrackerReadException: The reading methods are unavailable
                (see `analyzed` property).
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
            See chained exceptions for specific failure reasons.
        """
        pass

    @abstractmethod
    def read_day_attendance_error(self, date: dt.date | dt.datetime) -> Optional[int]:
        """
        Read the attendance error on a given date.

        The `TimeTrackerAnalyzer` automatically detects basic errors,
        such as missing clock-outs on past days. This method allows you
        to retrieve those errors.

        It differs from the `set_attendance_error()` and `get_attendance_error()`
        methods defined in the `TimeTracker` interface, which provide low-level
        access for setting and retrieving custom attendance errors. The
        `AttendanceValidator` class typically uses the set/get methods to
        register its own custom errors, and `read_day_attendance_error()`
        to access the basic errors detected automatically by the
        `TimeTrackerAnalyzer`.

        In most cases, using an `AttendanceValidator` is preferred over
        interacting directly with these low-level methods.

        Args:
            date (datetime.date): The date to read data.

        Returns:
            Optional[int]: Detected attendance error for the date or
                `None` if no error is found.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`.
            TimeTrackerReadException: The reading methods are unavailable
                (see `analyzed` property).
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
            See chained exceptions for specific failure reasons.
        """
        pass

    @abstractmethod
    def read_month_expected_daily_schedule(
        self, month: int | dt.date | dt.datetime
    ) -> dt.timedelta:
        """
        Read the standard daily work schedule on the given month, based
        on the employee's contract percentage. This value does not
        account for weekends or vacations.

        Args:
            month (int): The month to read data.

        Returns:
            datetime.timedelta: The standard daily work schedule.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`.
            TimeTrackerReadException: The reading methods are unavailable
                (see `analyzed` property).
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
            See chained exceptions for specific failure reasons.
        """
        pass

    @abstractmethod
    def read_month_schedule(self, month: int | dt.date | dt.datetime) -> dt.timedelta:
        """
        Get employee's schedule on the given month (how many time
        he's supposed to work in the month).

        This method is only available when the `analyzed` property is
        `True`.

        Args:
            month (int): The month to read data.

        Returns:
            datetime.timedelta: Scheduled work time for the given month.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`
                (not raised when month is given directly).
            TimeTrackerReadException: The reading methods are unavailable
                (see `analyzed` property).
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
            See chained exceptions for specific failure reasons.
        """
        pass

    @abstractmethod
    def read_month_worked_time(
        self, month: int | dt.date | dt.datetime
    ) -> dt.timedelta:
        """
        Get employee's worked time on the given month.

        This method calculates the sum of all days worked during the
        month as if they were retrieved and added together using the
        `read_day_worked_time()` method.

        Since this method relies on the `read_day_worked_time()` method,
        it has the same problem regarding attendance errors. Always check
        that no attendance error exists for the month using an
        `AttendanceValidator` before relying on this value.

        This method is only available when the `analyzed` property is
        `True`.

        Args:
            month (int): The month to read data.

        Returns:
            datetime.timedelta: Worked time for the month.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`
                (not raised when month is given directly).
            TimeTrackerReadException: The reading methods are unavailable
                (see `analyzed` property).
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
            See chained exceptions for specific failure reasons.
        """
        pass

    @abstractmethod
    def read_month_balance(self, month: int | dt.date | dt.datetime) -> dt.timedelta:
        """
        Read employee's balance on the given month.

        This method calculates the sum of all days balances during the
        month as if they were retrieved and added together using the
        `read_day_balance()` method.

        Since this method relies on the `read_day_balance()` method,
        it has the same problem regarding attendance errors. Always check
        that no attendance error exists for the month using an
        `AttendanceValidator` before relying on this value.

        This method is only available when the `analyzed` property is
        `True`.

        Args:
            month (int): The month to read data.

        Returns:
            datetime.timedelta: Balance for the month.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`
                (not raised when month is given directly).
            TimeTrackerReadException: The reading methods are unavailable
                (see `analyzed` property).
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
            See chained exceptions for specific failure reasons.
        """
        pass

    @abstractmethod
    def read_month_vacation(self, month: int | dt.date | dt.datetime) -> float:
        """
        Get the total number of vacation days planned on the given month.

        This method is only available when the `analyzed` property is
        `True`.

        Args:
            month (int): The month to read data.

        Returns:
            float: Number of planned vacation days on the given month.

        Raises:
            TimeTrackerDateException: Date is outside the `tracked_year`
                (not raised when month is given directly).
            TimeTrackerReadException: The reading methods are unavailable
                (see `analyzed` property).
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
            See chained exceptions for specific failure reasons.
        """
        pass

    @abstractmethod
    def read_year_vacation(self) -> float:
        """
        Get the total number of vacation days planned for the year.

        This is the sum of all planned vacation days in the year,
        disregarding to the `target_datetime.date()`.

        This value can be thought as:
            opening_vacation_days - remaining_vacation

        This method is only available when the `analyzed` property is
        `True`.

        Returns:
            float: Number of planned vacation days for the year.

        Raises:
            TimeTrackerReadException: The reading methods are unavailable
                (see `analyzed` property).
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
            See chained exceptions for specific failure reasons.
        """
        pass

    @abstractmethod
    def read_year_remaining_vacation(self) -> float:
        """
        Get the number of vacation days the employee still has available
        (not yet planned or used) this year.

        This is the remaining vacation days (not planned) the employee
        still has for the year, disregarding to the `target_datetime.date()`.

        This value can be thought as:
            opening_vacation_days - year_vacation

        This method is only available when the `analyzed` property is
        `True`.

        Returns:
            float: Number of remaining vacation days.

        Raises:
            TimeTrackerReadException: The reading methods are unavailable
                (see `analyzed` property).
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
            See chained exceptions for specific failure reasons.
        """
        pass

    @abstractmethod
    def read_year_to_date_balance(self) -> dt.timedelta:
        """
        Get employee's year-to-date balance.

        The year-to-date balance is calculated by summing up all month
        balances up to `target_datetime.date()` (included).

        Since this method relies on the `read_month_balance()` method
        that itself relies on the `read_day_balance()` method, it has
        the same problem regarding attendance errors. Always check
        that no attendance error exists for the year using an
        `AttendanceValidator` before relying on this value.

        This method is only available when the `analyzed` property is
        `True`.

        Returns:
            datetime.timedelta: Year-to-date balance as a timedelta.

        Raises:
            TimeTrackerReadException: The reading methods are unavailable
                (see `analyzed` property).
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
            See chained exceptions for specific failure reasons.
        """
        pass

    def read_year_to_yesterday_balance(self) -> dt.timedelta:
        """
        Get employee's year-to-yesterday balance.

        The year-to-yesterday balance is calculated by summing up all
        month balances up to `target_datetime.date()` (excluded). It is
        often more relevant for the employee to see his balance related
        to yesterday when the current day is still in progress.

        Since this method relies on the `read_month_balance()` method
        that itself relies on the `read_day_balance()` method, it has
        the same problem regarding attendance errors. Always check
        that no attendance error exists for the year using an
        `AttendanceValidator` before relying on this value.

        This method is only available when the `analyzed` property is
        `True`.

        Returns:
            datetime.timedelta: Year-to-yesterday balance as a timedelta.

        Raises:
            TimeTrackerReadException: The reading methods are unavailable
                (see `analyzed` property).
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
            See chained exceptions for specific failure reasons.
        """
        if not self.target_datetime:
            raise TimeTrackerReadException()

        # A simple way of getting this value is to subtract the current day
        # balance to the year-to-date balance
        year_to_date = self.read_year_to_date_balance()
        day_balance = self.read_day_balance(self.target_datetime.date())
        return year_to_date - day_balance

    def read_year_attendance_error(self) -> Optional[int]:
        """
        Read the global attendance error for the year. It returns the
        most severe error from all days.

        In most cases, using an `AttendanceValidator` is preferred over
        interacting directly with these low-level methods.

        Returns:
            Optional[int]: Detected attendance error for the year or
                `None` if no error is found.

        Raises:
            TimeTrackerReadException: The reading methods are unavailable
                (see `analyzed` property).
            TimeTrackerValueException: Read an unexpected value from the
                storage system.
            See chained exceptions for specific failure reasons.
        """
        pass
