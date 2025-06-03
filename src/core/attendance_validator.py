#!/usr/bin/env python3
"""
File: attendance_validator.py
Author: Bastian Cerf
Date: 09/06/2025
Description:
    Provides utility functions to detect attendance errors on specific
    dates, months or over a full year.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
from dataclasses import dataclass
import datetime as dt
from typing import Optional

# Internal libraries
from .time_tracker import *

########################################################################
#                  Attendance error class declaration                  #
########################################################################


@dataclass(frozen=True)
class AttendanceError:
    """
    Simple attendance error data class.

    Attributes:
        error_id (int): Unique error ID.
        description (str): Error description.
    """

    error_id: Optional[int]
    description: str


# Declaration of available attendance error types
CLOCK_EVENT_MISSING = AttendanceError(0, "A clock event is missing.")
CLOCK_EVENTS_UNORDERED = AttendanceError(1, "Clock events times are unordered.")


########################################################################
#                          Attendance validator                        #
########################################################################


class AttendanceValidator:
    """
    A utility class to validate the clock events provided by a time
    tracker.
    """

    def __init__(self, tracker: TimeTracker):
        """
        Initialize an attendance validator for the given time tracker.

        Args:
            tracker (TimeTracker): Employee's time tracker.
        """
        self._tracker = tracker

    @property
    def time_tracker(self) -> TimeTracker:
        """
        Get the assigned time tracker.

        Returns:
            TimeTracker: The time tracker instance in use.
        """
        return self._tracker

    def analyze_date(
        self, date: dt.date, update: bool = False
    ) -> Optional[AttendanceError]:
        """
        Check for attendance error on a given date.

        This method verifies the integrity of clock events for the day
        by checking the following:
        - The day ends with a clock-out event
        - No clock events are missing
        - All clock event times are in chronological order

        Args:
            date (datetime.date): The date to analyze.
            update (bool): `True` to register the error found in the
                `TimeTracker` or to reset if none is found.

        Returns:
            Optional[AttendanceError]: An `AttendanceError` describing the
                issue found, or `None` if no error is detected.

        Raises:
            TimeTrackerDateException: Raised if the given date doesn't
                relate to the `tracked_year`.
        """
        events = self._tracker.get_clocks(date)  # May raise date exception

        # No event, no error
        if not events:
            return None

        error = None

        # Check 1: no missing (None) clock event
        if any(evt is None for evt in events):
            error = CLOCK_EVENT_MISSING

        # Check 2: day finishes with a clock-out
        if events[-1] is not None and (events[-1].action != ClockAction.CLOCK_OUT):
            error = CLOCK_EVENT_MISSING

        # Check 3: events times are in ascending order
        events = [evt for evt in events if evt is not None]  # For type checkers
        if any(e1.time >= e2.time for e1, e2 in zip(events, events[1:])):
            error = CLOCK_EVENTS_UNORDERED

        # Update the time tracker with the issue found
        if update:
            self._tracker.set_attendance_error(
                date, (error.error_id if error else None)
            )

        return error

    def analyze_until(
        self, date: dt.date, update: bool = False
    ) -> dict[dt.date, AttendanceError]:
        """
        Analyze all days of the year until the given date and check
        for attendance errors. The given date is not included.

        This method internally uses `validator.analyze_date()` on
        each day in the range [01.01.xxxx; date[

        Args:
            date (datetime.date): The last date to analyze.
            update (bool): `True` to register the error found in the
                `TimeTracker` or to reset if none is found.

        Returns:
            dict[datetime.date, AttendanceError]: A dictionary of error
                dates as keys and error type as values. The dictionary is
                empty if no error is found.

        Raises:
            TimeTrackerDateException: Raised if the given date doesn't
                relate to the `tracked_year`.
        """
        day_delta = dt.timedelta(days=1)
        end_date = date

        if end_date.year != self._tracker.tracked_year:
            raise TimeTrackerDateException()

        # Dictionary of days with an attendance error
        errors: dict[dt.date, AttendanceError] = {}
        # Iterate all days from the first of January until end_date
        # and search for errors
        date = dt.date(day=1, month=1, year=self._tracker.tracked_year)
        while date < end_date:
            if error := self.analyze_date(date, update=update):
                errors[date] = error
            date += day_delta

        return errors
