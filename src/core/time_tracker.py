#!/usr/bin/env python3
"""
File: time_tracker.py
Author: Bastian Cerf
Date: 17/02/2025
Description:
    Base abstract class for accessing and managing an employee's
    attendance data.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
from abc import ABC, abstractmethod
from typing import Optional, Type
from types import TracebackType
from dataclasses import dataclass
from enum import Enum
import datetime as dt

########################################################################
#              Time tracker related errors declaration                 #
########################################################################


class TimeTrackerReadException(Exception):
    """Custom exception for illegal read operation."""

    def __init__(self, message: str = "Illegal read operation attempted"):
        super().__init__(message)


class TimeTrackerWriteException(Exception):
    """Custom exception for illegal write operation."""

    def __init__(self, message: str = "Illegal write operation attempted"):
        super().__init__(message)


class TimeTrackerOpenException(Exception):
    """Custom exception for time tracker opening errors."""

    def __init__(self, message: str = "Unable to open the time tracker"):
        super().__init__(message)


class TimeTrackerDateException(Exception):
    """Custom exception for time tracker date errors."""

    def __init__(self, message: str = "The operation failed due to a date error"):
        super().__init__(message)


class TimeTrackerEvaluationException(Exception):
    """Custom exception for time tracker evaluation errors."""

    def __init__(self, message: str = "The data evaluation failed"):
        super().__init__(message)


class TimeTrackerSaveException(Exception):
    """Custom exception for time tracker saving errors."""

    def __init__(self, message: str = "The time tracker hasn't been saved properly"):
        super().__init__(message)


class TimeTrackerCloseException(Exception):
    """Custom exception for time tracker closing errors."""

    def __init__(self, message: str = "The time tracker hasn't been closed properly"):
        super().__init__(message)


########################################################################
#                Clocking event dataclass declaration                  #
########################################################################


class ClockAction(Enum):
    """Clock actions enumeration."""

    CLOCK_IN = 0  # The employee starts working
    CLOCK_OUT = 1  # The employee finishes working

    def __str__(self):
        # Return `clock-in` or `clock-out` as a user friendly description
        return self.name.lower().replace("_", "-")


@dataclass(frozen=True)
class ClockEvent:
    """Simple container for a clock event.

    Attributes:
        time (datetime.time): Time in the day at which the event occurred.
        action (ClockAction): Related clock action.
    """

    time: dt.time
    action: ClockAction

    def __str__(self):
        return f"{self.action} at {self.time.strftime('%H:%M')}"


########################################################################
#                Time tracker base class declaration                   #
########################################################################


class BaseTimeTracker(ABC):
    """Abstract base class for accessing and managing an employee's
    attendance data.

    This interface handles attendance records for a single employee over
    the span of one calendar year. It provides functionality to manage and
    retrieve clock-in and clock-out events across multiple dates within
    that year.

    In addition to reading and modifying raw attendance data, the tracker
    can compute derived values based on that data. Raw data is always
    accessible via properties, while computed values—prefixed with `read_`—
    become available only after invoking the `evaluate()` method. These
    computed properties are valid only when the `readable` property is `True`.

    The `data_datetime` property defines the reference date and time used
    to evaluate the employee's data. Clock-in and clock-out events that occur
    after this datetime are excluded from day, month, and year balances.
    This property is typically set to the current date and time at
    initialization. It can be used to support external sources (e.g.,
    web clocks or other reference systems).

    Since each time tracker instance covers a single year, the `data_year`
    property provides access to that year. Attempting to use a date outside
    of the valid range typically results in a `TimeTrackerDateException`.

    This class is stateful, as it relies on the `data_datetime` property
    for read and write operations. It is therefore not thread-safe.

    This base class includes some concrete helper methods (e.g.,
    `is_clocked_in()`) that depend on the correct implementation of
    abstract methods such as `get_clock_events()` and `evaluate()`.
    """

    def __init__(self, employee_id: str, data_datetime: Optional[dt.datetime] = None):
        """Initializes the time tracker for the specified employee.

        The optional `data_datetime` parameter defines the date and time
        at which the tracker's data should be evaluated. If not provided,
        the tracker may fall back to the most recently available
        timestamp, or data access via `read_` methods may remain
        unavailable.

        Args:
            employee_id (str): The unique identifier of the employee.
            data_datetime (Optional[datetime]): The reference date and
                time for evaluating the tracker's data.

        Raises:
            TimeTrackerOpenException: If the time tracker data cannot be
                opened.
            See subclass implementations for specific failure reasons.
        """
        self._employee_id = employee_id

        self._date = None
        self._time = None
        if data_datetime is not None:
            self._date = data_datetime.date()
            self._time = data_datetime.time()

        try:
            # Call the setup method to get access to properties
            self._setup()
        except Exception as e:
            raise TimeTrackerOpenException() from e

    def __enter__(self) -> "BaseTimeTracker":
        # Allow the use of a context manager
        return self

    @abstractmethod
    def _setup(self):
        """Internally setup the data access.

        Properties must then be accessible.
        """
        pass

    @property
    def employee_id(self) -> str:
        """Get employee's id.

        Returns:
            str: Employee's id.
        """
        return self._employee_id

    @property
    @abstractmethod
    def firstname(self) -> str:
        """Get employee's firstname.

        Returns:
            str: Employee's firstname.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Get employee's name.

        Returns:
            str: Employee's name.
        """
        pass

    @property
    @abstractmethod
    def day_schedule(self) -> dt.timedelta:
        """Return the employee's standard daily schedule.

        This value represents the expected working time on a regular day,
        typically based on the employee's work percentage (e.g., full-time,
        part-time). It is not affected by the current date or time.

        For date-specific schedules, see `read_day_schedule()`.

        Returns:
            datetime.timedelta: The typical daily working time.
        """
        pass

    @property
    @abstractmethod
    def initial_vacation_days(self) -> int:
        """Return the employee's initial vacation allowance for the year.

        This value represents the total vacation days available to the
        employee at the start of the year (`01.01.data_year`).

        Returns:
            int: Number of vacation days at the beginning of the year.
        """
        pass

    @property
    @abstractmethod
    def initial_balance(self) -> dt.timedelta:
        """Return the employee's initial time balance for the year.

        This is usually the time balance carried over from the previous year
        and applies to `01.01.data_year`.

        Returns:
            datetime.timedelta: The initial balance at the start of the year.
        """
        pass

    @property
    @abstractmethod
    def data_year(self) -> int:
        """Get the year of the information held by the time tracker.

        Returns:
            int: Year of the information.
        """
        pass

    @property
    @abstractmethod
    def max_clock_events_per_day(self) -> int:
        """Get the maximum number of clock events that can be registered
        per day.

        This value is set by the implementation in use.

        Returns:
            int: Maximum number of clock events that can be registered
                for one day.
        """
        pass

    @property
    def data_datetime(self) -> Optional[dt.datetime]:
        """Get the reference datetime for data evaluation.

        This property defines the date and time to which the employee's data
        is evaluated. It determines the cutoff for what events (e.g., clock-ins,
        balances) are considered in computations.

        Returns:
            Optional[datetime.datetime]: The current evaluation datetime.
        """
        if self._date and self._time:
            return dt.datetime.combine(self._date, self._time)
        return None

    @data_datetime.setter
    def data_datetime(self, new_datetime: dt.datetime):
        """Set the reference datetime for data evaluation.

        Updating this property changes the date and time to which the
        employee's data is evaluated. Changing it invalidates all
        previously computed values (those prefixed with `read_`), as they
        may no longer reflect the new reference datetime.

        Args:
            new_datetime (datetime.datetime): The new evaluation datetime.
        """
        self._date = new_datetime.date()
        self._time = new_datetime.time()

    @property
    @abstractmethod
    def readable(self) -> bool:
        """Indicate whether the reading functions are currently available.

        Reading functions (those prefixed with `read_`) typically become
        available after a successful call to the `evaluate()` method.

        Returns:
            bool: `True` if reading functions are available, `False`
                otherwise.
        """
        pass

    @abstractmethod
    def evaluate(self) -> None:
        """Evaluate the employee's data at the current `data_datetime`.

        This method processes the raw attendance data based on the set
        `data_datetime`, enabling the `read_` prefixed functions.
        Depending on the underlying implementation, this operation may
        take some time.

        After successful evaluation, the `readable` property is set to
        `True`.

        Raises:
            TimeTrackerEvaluationException: If the evaluation fails.
            See subclass implementations for specific failure details.
        """
        pass

    @abstractmethod
    def get_clock_events(
        self, date: Optional[dt.date] = None
    ) -> list[Optional[ClockEvent]]:
        """Retrieve all clock-in and clock-out events on a given
        date.

        If no date is specified, the method defaults to using the date
        from `data_datetime`.

        Events are supposed to be ordered chronologically, however they
        may not if an error has occurred. Use the `check_date_error()`
        method to know if an error exists for the date.

        The clock events follow the expected pattern:
        clock-in, clock-out, clock-in, clock-out, etc. If a corresponding
        event is missing (e.g., a missing clock-out after a clock-in),
        `None` is inserted in its place to preserve the sequence
        structure.

        Args:
            date (Optional[datetime.date]): The date to retrieve. Defaults
                to `data_datetime.date` if not provided.

        Returns:
            list[Optional[ClockEvent]]: A list of clock events for the date.
                The list may be empty if no events are recorded.
        """
        pass

    def is_clocked_in(self, date: Optional[dt.date] = None) -> bool:
        """Check if the employee is clocked on a given date.

        If no date is specified, the method defaults to using the date
        from `data_datetime`.

        Args:
            date (Optional[datetime.date]): The date to check. Defaults
                to `data_datetime.date` if not provided.

        Returns:
            bool: True if clocked in.
        """
        # Check if the last event is a clock-in action
        events = self.get_clock_events(date)
        return (
            bool(events)
            and events[-1] is not None
            and (events[-1].action == ClockAction.CLOCK_IN)
        )

    @abstractmethod
    def read_day_schedule(self, date: Optional[dt.date] = None) -> dt.timedelta:
        """Get employee's daily schedule on a given date (how much time
        he's supposed to work).

        If no date is specified, the method defaults to using the date
        from `data_datetime`.

        Accessible when the `readable` property is `True`.

        Args:
            date (Optional[datetime.date]): The date to read data. Defaults
                to `data_datetime.date` if not provided.

        Returns:
            datetime.timedelta: Schedule for the day as a timedelta.

        Raises:
            TimeTrackerReadException: Raised if the reading methods are
                unavailable (see `readable` flag).
        """
        pass

    @abstractmethod
    def read_day_worked_time(self, date: Optional[dt.date] = None) -> dt.timedelta:
        """Get employee's worked time on a given date.

        If no date is specified, the method defaults to using the date
        from `data_datetime`.

        If the employee is clocked in on that date (either a custom date
        or `data_datetime.date`), the worked time is computed relative to
        `data_datetime.time`. This can lead to special cases:

        - If the given date is today and the employee is clocked in, the
        worked time reflects the current working status up to now (as expected).
        - If a specific date is used and the employee forgot to clock out
        on that date, the calculation will still use `data_datetime.time`,
        which may yield inaccurate or misleading results.

        To avoid misinterpretation when evaluating past dates, make sure
        to check for clocking errors using an `AttendanceValidator` before
        relying on this value.

        This method is only available when the `readable` property is
        `True`.

        Args:
            date (Optional[datetime.date]): The date to read data. Defaults
                to `data_datetime.date` if not provided.

        Returns:
            datetime.timedelta: Worked time for the day as a timedelta.

        Raises:
            TimeTrackerReadException: Raised if the reading methods are
                unavailable (see `readable` flag).
        """
        pass

    @abstractmethod
    def read_day_balance(self, date: Optional[dt.date] = None) -> dt.timedelta:
        """Get the employee's time balance for a given date.

        If no date is specified, the method defaults to using the date
        from `data_datetime`.

        The balance represents the remaining work time the employee is
        expected to complete on the specified day. A positive balance
        means the employee worked more than the expected daily schedule.

        The balance is `00:00` for all days after the `data_datetime.date`,
        even if some clock events are already registered for that date.
        In other words, the balance can be thought as:

            balance = day_worked_time - day_schedule
                if day <= `data_datetime.date` else 0

        If the employee is clocked in on that date (either a custom date
        or `data_datetime.date`), the balance is computed relative to
        `data_datetime.time`. This can lead to special cases:

        - If the given date is today and the employee is clocked in, the
        balance reflects the current working status up to now (as expected).
        - If a specific date is used and the employee forgot to clock out
        on that date, the calculation will still use `data_datetime.time`,
        which may yield inaccurate or misleading results.

        To avoid misinterpretation when evaluating past dates, make sure
        to check for clocking errors using an `AttendanceValidator` before
        relying on this value.

        This method is only available when the `readable` property is
        `True`.

        Args:
            date (Optional[datetime.date]): The date to read data. Defaults
                to `data_datetime.date` if not specified.

        Returns:
            datetime.timedelta: The time balance for the specified day.

        Raises:
            TimeTrackerReadException: Raised if the reading methods are
                unavailable (see `readable` flag).
        """
        pass

    @abstractmethod
    def read_month_schedule(self, month: Optional[int] = None) -> dt.timedelta:
        """Get employee's schedule on the given month (how many time
        he's supposed to work).

        If no month is specified, the method defaults to using the month
        from `data_datetime`.

        Accessible when the `readable` property is `True`.

        Args:
            month (Optional[int]): The month to read data. Defaults
                to `data_datetime.date.month` if not provided.

        Returns:
            datetime.timedelta: Worked time for the month as a timedelta.

        Raises:
            TimeTrackerReadException: Raised if the reading methods are
                unavailable (see `readable` flag).
        """
        pass

    @abstractmethod
    def read_month_worked_time(self, month: Optional[int] = None) -> dt.timedelta:
        """Get employee's worked time on the given month.

        If no month is specified, the method defaults to using the month
        from `data_datetime`.

        This method returns the sum of all day worked times of the month,
        as if they were retrieved using `read_day_worked_time()`.

        In contrast with the month balance, days worked time does not
        rely on `data_datetime.date`. That means that worked times after
        `data_datetime.date` are added to the sum. The month worked time
        does not exclude the time worked in future days related to the
        current `data_datetime.date`.

        Clocking errors affect the sum of worked times the same
        way they do on individual day worked time, as explained for the
        `read_day_balance()` method. Always check for clocking errors
        using an `AttendanceValidator` before use.

        This method is only available when the `readable` property is
        `True`.

        Args:
            month (Optional[int]): The month to read data. Defaults
                to `data_datetime.date.month` if not provided.

        Returns:
            datetime.timedelta: Worked time for the month as a timedelta.

        Raises:
            TimeTrackerReadException: Raised if the reading methods are
                unavailable (see `readable` flag).
        """
        pass

    @abstractmethod
    def read_month_balance(self, month: Optional[int] = None) -> dt.timedelta:
        """Get employee's balance on the given month.

        If no month is specified, the method defaults to using the month
        from `data_datetime`.

        This method returns the sum of all day balances of the month, as
        if they were retrieved using `read_day_balance()`. That means
        that day balances after `data_datetime.date` are not added to the
        sum, i.e. reading the month balance of February while
        `data_datetime.date` is January shall return 0.

        Clocking errors on past days affect the sum of balances the same
        way they do on individual day balances, as explained for the
        `read_day_balance()` method. Always check for clocking errors
        using an `AttendanceValidator` before use.

        This method is only available when the `readable` property is
        `True`.

        Args:
            month (Optional[int]): The month to read data. Defaults
                to `data_datetime.date.month` if not provided.

        Returns:
            datetime.timedelta: Balance for the month as a timedelta.

        Raises:
            TimeTrackerReadException: Raised if the reading methods are
                unavailable (see `readable` flag).
        """
        pass

    @abstractmethod
    def read_year_to_date_balance(self) -> dt.timedelta:
        """Get employee's year-to-date balance.

        The year-to-date balance is calculated by summing up all month
        balances up to `data_datetime.date` (included).

        Clocking errors on past days affect the sum of balances the same
        way they do on individual day balances, as explained for the
        `read_day_balance()` method. Always check for clocking errors
        using an `AttendanceValidator` before use.

        This method is only available when the `readable` property is
        `True`.

        Returns:
            datetime.timedelta: Year-to-date balance as a timedelta.

        Raises:
            TimeTrackerReadException: Raised if the reading methods are
                unavailable (see `readable` flag).
        """
        pass

    def read_year_to_yesterday_balance(self) -> dt.timedelta:
        """Get employee's year-to-yesterday balance.

        The year-to-yesterday balance is calculated by summing up all
        month balances up to `data_datetime.date` (excluded). It is
        often more relevant for the employee to see his balance until
        yesterday when the current day is still in progress.

        Clocking errors on past days affect the sum of balances the same
        way they do on individual day balances, as explained for the
        `read_day_balance()` method. Always check for clocking errors
        using an `AttendanceValidator` before use.

        This method is only available when the `readable` property is
        `True`.

        Returns:
            datetime.timedelta: Year-to-yesterday balance as a timedelta.

        Raises:
            TimeTrackerReadException: Raised if the reading methods are
                unavailable (see `readable` flag).
        """
        # A simple way of getting this value is to subtract the current day
        # balance to the year-to-date balance
        return self.read_year_to_date_balance() - self.read_day_balance()

    @abstractmethod
    def read_day_vacation(self, date: Optional[dt.date] = None) -> float:
        """Get the vacation day ratio on the given date.

        If no date is specified, the method defaults to using the date
        from `data_datetime`.

        Typically returns a value in the range [0.0, 1.0], where:
        - 1.0 represents a full vacation day,
        - 0.5 represents a half-day,
        - 0.0 means no vacation.

        This method is only available when the `readable` property is
        `True`.

        Args:
            date (Optional[datetime.date]): The date to read data. Defaults
                to `data_datetime.date` if not provided.

        Returns:
            float: Vacation ratio for the current date.

        Raises:
            TimeTrackerReadException: Raised if the reading methods are
                unavailable (see `readable` flag).
        """
        pass

    @abstractmethod
    def read_month_vacation(self, month: Optional[int] = None) -> float:
        """Get the total number of vacation days planned on the given
        month.

        If no month is specified, the method defaults to using the month
        from `data_datetime`.

        This method is only available when the `readable` property is
        `True`.

        Args:
            month (Optional[int]): The month to read data. Defaults
                to `data_datetime.date.month` if not provided.

        Returns:
            float: Number of planned vacation days for the current month.

        Raises:
            TimeTrackerReadException: Raised if the reading methods are
                unavailable (see `readable` flag).
        """
        pass

    @abstractmethod
    def read_remaining_vacation(self) -> float:
        """Get the number of vacation days the employee still has
        available (not yet planned or used) this year.

        This method does not take `data_datetime` into consideration. If
        a vacation is scheduled in December, but `data_datetime.date` is
        in January, the counter is still decremented by one day.

        This value can be thought as:
            initial_vacation_days - year_vacation

        This method is only available when the `readable` property is
        `True`.

        Returns:
            float: Number of remaining vacation days.

        Raises:
            TimeTrackerReadException: Raised if the reading methods are
                unavailable (see `readable` flag).
        """
        pass

    @abstractmethod
    def read_year_vacation(self) -> float:
        """Get the total number of vacation days planned for the year.

        This method does not take `data_datetime` into consideration. If
        a vacation is scheduled in December, but `data_datetime.date` is
        in January, the counter is still incremented by one day.

        This value can be thought as:
            initial_vacation_days - remaining_vacation

        This method is only available when the `readable` property is
        `True`.

        Returns:
            float: Number of planned vacation days for the year.

        Raises:
            TimeTrackerReadException: Raised if the reading methods are
                unavailable (see `readable` flag).
        """
        pass

    @abstractmethod
    def register_clock(self, event: ClockEvent, date: Optional[dt.date] = None) -> None:
        """Register a clock in/out event on the given date.

        If no date is specified, the method defaults to using the date
        from `data_datetime`.

        The clock event is written in the next available slot for the
        day, eventually leaving empty slots if two same actions are
        registered one after the other.

        After a clock event is registered, the `readable` property gets
        `False` and the reading functions are not available until a new
        evaluation is performed.

        Args:
            event (ClockEvent): Clock event to register on given date.
            date (Optional[datetime.date]): Specify the date to write the
                clock event. Defaults to `data_datetime.date`.

        Raises:
            TimeTrackerWriteException: Raised when the registering fails.
            See subclass implementations for more detailed reasons.
        """
        pass

    @abstractmethod
    def write_clocks(
        self, events: list[Optional[ClockEvent]], date: Optional[dt.date] = None
    ) -> None:
        """Write the given clock events list on the given date, overwriting
        existing entries.

        If no date is specified, the method defaults to using the date
        from `data_datetime`.

        The clock events are given in the same format they are retrieved
        using `get_clock_events()`. The events are not added to the next
        available slot, like `register_clock()` does. Existing events
        are overwritten.

        The events list must not be greater than `max_clock_events_per_day`,
        or a TimeTrackerWriteException will be raised.

        After clock events are written, the `readable` property gets
        `False` and the reading functions are not available until a new
        evaluation is performed.

        Args:
            events (list[Optional[ClockEvent]]): List of clock events to
                write on the given date.
            date (Optional[datetime.date]): Specify the date to write the
                clock events. Defaults to `data_datetime.date`.

        Raises:
            TimeTrackerWriteException: Raised when the registering fails.
            See subclass implementations for more detailed reasons.
        """
        pass

    @abstractmethod
    def save(self) -> None:
        """Save changes.

        This must be called after changes have been done (typically after
        new clock events have been registered) to save the modifications.

        Raises:
            TimeTrackerSaveException: Raised when the saving fails.
            See subclass implementations for more detailed reasons.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the time tracker. It should not be used again after
        this call.

        This does not automatically save the data. In most cases, the
        `save()` method should be called before this.

        Raises:
            TimeTrackerCloseException: Raised when the closing fails.
            See subclass implementations for more detailed reasons.
        """
        pass

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        """Ensures the time tracker is properly closed when exiting the
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
                # If there was an exception during the context block, chain
                # close error to it
                raise exc_val from close_ex
            # No prior exception: just raise the close failure
            raise close_ex
        return False  # Propagate any exception from the context block


########################################################################
#                       Attendance error types                         #
########################################################################


@dataclass(frozen=True)
class AttendanceError:
    """Simple attendance error class.

    Attributes:
        description (str): Concise error description.
    """

    description: str


# Declaration of available attendance error types
CLOCK_EVENT_MISSING = AttendanceError("A clock event is missing.")
CLOCK_EVENTS_UNORDERED = AttendanceError("Clock events times are unordered.")


class AttendanceValidator:
    """A utility class to validate the clock events provided by a time
    tracker.
    """

    def __init__(self, tracker: BaseTimeTracker):
        """Initialize an attendance validator for the given time tracker.

        Args:
            tracker: Employee's time tracker to check.
        """
        self._tracker = tracker

    @property
    def time_tracker(self) -> BaseTimeTracker:
        """
        Get the currently assigned time tracker.

        Returns:
            BaseTimeTracker: The time tracker instance in use.
        """
        return self._tracker

    @time_tracker.setter
    def time_tracker(self, tracker: BaseTimeTracker):
        """
        Assign a new time tracker.

        Args:
            tracker: The time tracker instance to use.
        """
        self._tracker = tracker

    def check_date(self, date: Optional[dt.date] = None) -> Optional[AttendanceError]:
        """Check for attendance error on a given date.

        If no date is specified, the method defaults to using the date
        from `data_datetime`.

        This method verifies the integrity of clock events for the day by
        checking the following:
        - The day ends with a clock-out event
        - No clock events are missing
        - All clock event times are in chronological order

        Args:
            date (Optional[datetime.date]): The date to analyze. Defaults
                to `data_datetime.date` if not provided.

        Returns:
            Optional[AttendanceError]: An `AttendanceError` describing the
                issue found, or `None` if no errors are detected.
        """
        events = self._tracker.get_clock_events(date)

        # No event, no error
        if not events:
            return None

        # Check 1: no missing (None) clock event
        if any(evt is None for evt in events):
            return CLOCK_EVENT_MISSING

        # Check 2: day finishes with a clock-out
        if events[-1] is not None and (events[-1].action != ClockAction.CLOCK_OUT):
            return CLOCK_EVENT_MISSING

        # Check 3: events times are in ascending order
        events = [evt for evt in events if evt is not None]  # For type checkers
        if any(e1.time >= e2.time for e1, e2 in zip(events, events[1:])):
            return CLOCK_EVENTS_UNORDERED

        return None

    def check_year_to_date(
        self, date: Optional[dt.date] = None
    ) -> dict[dt.date, AttendanceError]:
        """Analyze all days of the year until the given date and check
        for clocking errors.

        If no date is specified, the method defaults to using the date
        from `data_datetime` minus one day (year-to-yesterday). This is
        to prevent including an ongoing day in the dates range.

        This method internally uses `validator.check_date()` on
        each past day.

        Args:
            date (Optional[datetime.date]): The last date to analyze.
                Defaults to `data_datetime.date - 1` if not provided.

        Returns:
            dict[datetime.date, AttendanceError]: A dictionary of error
                dates as keys and error type as values. The dictionary is
                empty if no error is found.
        """
        day_delta = dt.timedelta(days=1)

        if date is not None:
            end_date = date
        elif self._tracker.data_datetime is not None:
            end_date = self._tracker.data_datetime.date() - day_delta
        else:
            raise ValueError("No data datetime available.")

        # Dictionary of days with an attendance error
        errors: dict[dt.date, AttendanceError] = {}
        # Iterate all days from the first of January until end_date
        # and search for errors
        date = dt.date(day=1, month=1, year=self._tracker.data_year)
        while date < end_date:
            if error := self.check_date(date=date):
                errors[date] = error
            date += day_delta

        return errors
