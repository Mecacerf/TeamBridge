#!/usr/bin/env python3
"""
File: attendance_validator_test.py
Author: Bastian Cerf
Date: 23/07/2025
Description:
    Unit tests for the attendance validator module.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import pytest
from typing import Optional, cast, Callable
import datetime as dt
import logging

# Internal libraries
from .test_constants import *
from core.time_tracker import TimeTracker, TimeTrackerAnalyzer, TimeTrackerDateException
from core.attendance.attendance_validator import (
    AttendanceChecker,
    AttendanceValidator,
    AttendanceErrorStatus,
    AttendanceError,
)

logger = logging.getLogger(__name__)

########################################################################
#                     Attendance Validator Tests                       #
########################################################################


class CustomValidator(AttendanceValidator):

    def __init__(self, checkers: list[AttendanceChecker]):
        super().__init__(checkers)


class CustomChecker(AttendanceChecker):

    def __init__(self, error_id: int, func: Callable[[TimeTracker, dt.date], bool]):
        super().__init__(error_id)
        self._func = func

    def check_date(self, tracker: TimeTracker, date: dt.date) -> bool:
        return self._func(tracker, date)


class TimeTrackerMock:

    def __init__(
        self,
        year: int,
        anchor: Optional[dt.date] = None,
        app_errors: Optional[dict[dt.date, int]] = None,
        tracker_errors: Optional[dict[dt.date, int]] = None,
    ):
        self._year = year

        self.anchor = dt.datetime.now().date()
        if anchor:
            self.anchor = anchor

        self._errors = {}
        if app_errors:
            self._app_errors = app_errors

        self._tracker_errors = {}
        if tracker_errors:
            self._tracker_errors = tracker_errors

        self.set_errors = {}

    def __str__(self):
        return f"{self.__class__.__name__}"

    @property
    def tracked_year(self) -> int:
        return self._year

    def analyze(self, datetime: dt.datetime):
        logger.info(f"{self!s} analyzed for {datetime}.")

    def save(self):
        logger.info(f"{self!s} saved.")

    def get_last_validation_anchor(self) -> dt.date:
        return self.anchor

    def get_attendance_error(self, date: dt.date) -> int:
        return self._app_errors.get(date, 0)

    def get_attendance_error_desc(self, error_id: int) -> str:
        return f"Mock error {error_id}"

    def read_day_attendance_error(self, date: dt.date) -> int:
        return self._tracker_errors.get(date, 0)

    def set_attendance_error(self, date: dt.date, error_id: int):
        self.set_errors[date] = error_id

    def set_last_validation_anchor(self, date: dt.date):
        self.anchor = date


def test_existing_errors_simple_tracker():
    """
    Test the private `_read_existing_errors` of the validator. It should
    return the same errors as provided by the time tracker.
    """
    app_errors = {
        dt.date(2025, 1, 2): 10,
        dt.date(2025, 2, 5): 10,
        dt.date(2025, 1, 20): 20,
    }

    mock = cast(TimeTracker, TimeTrackerMock(2025, app_errors=app_errors))

    validator = CustomValidator([])
    date_errors = {}
    validator._read_existing_errors(mock, date_errors, dt.datetime(2025, 3, 1))

    assert app_errors == date_errors


def test_existing_errors_tracker_analyzer():
    """
    Test the private `_read_existing_errors` of the validator. It should
    return the merge of the application errors and the time tracker
    analyzer errors, with the worse error selected for each day.
    """
    # Make the mock a virtual subclass of TimeTrackerAnalyzer
    TimeTrackerAnalyzer.register(TimeTrackerMock)

    app_errors = {
        dt.date(2025, 1, 2): 10,
        dt.date(2025, 2, 5): 10,
        dt.date(2025, 1, 20): 20,
    }

    tracker_errors = {
        dt.date(2025, 1, 12): 40,
        dt.date(2025, 1, 20): 30,
    }

    merge_errors = {
        dt.date(2025, 1, 2): 10,
        dt.date(2025, 2, 5): 10,
        dt.date(2025, 1, 20): 30,  # The worse error is selected for the date
        dt.date(2025, 1, 12): 40,
    }

    mock = cast(
        TimeTrackerAnalyzer,
        TimeTrackerMock(2025, app_errors=app_errors, tracker_errors=tracker_errors),
    )

    validator = CustomValidator([])
    date_errors = {}
    validator._read_existing_errors(mock, date_errors, dt.datetime(2025, 3, 1, 8))

    assert merge_errors == date_errors


def test_scan_until_wrong_anchor():
    """
    Check that the validator raises an exception if the validation anchor
    is at the wrong year. It may happen if a HR person changed the date
    manually and did an error.
    """
    mock = cast(TimeTracker, TimeTrackerMock(2025, anchor=dt.date(2023, 1, 1)))

    validator = CustomValidator([])
    with pytest.raises(TimeTrackerDateException):
        validator._scan_until(mock, {}, dt.date(2025, 2, 2))


def test_scan_until_10_days():
    """
    Setup 3 checkers in the validator that create a known errors sequence.
    Scan for 11 days and verify the sequence.
    """
    mock = cast(TimeTracker, TimeTrackerMock(2025, anchor=dt.date(2025, 1, 9)))
    until = dt.date(2025, 1, 20)

    # First checker sets error 10 each 5 days
    checker1 = CustomChecker(10, lambda _, date: date.day % 5 == 0)
    # Second checker sets error 20 to pair days
    checker2 = CustomChecker(20, lambda _, date: date.day % 2 == 0)
    # Third checker sets error 30 each four days
    checker3 = CustomChecker(30, lambda _, date: date.day % 4 == 0)

    validator = CustomValidator([checker1, checker2, checker3])

    results = {
        dt.date(2025, 1, 10): 20,
        dt.date(2025, 1, 12): 30,
        dt.date(2025, 1, 14): 20,
        dt.date(2025, 1, 15): 10,
        dt.date(2025, 1, 16): 30,
        dt.date(2025, 1, 18): 20,
    }

    # Anchor date moved to the first date with an error
    new_anchor = dt.date(2025, 1, 10)

    date_errors = {}
    validator._scan_until(mock, date_errors, until)

    assert date_errors == results
    assert cast(TimeTrackerMock, mock).set_errors == results
    assert cast(TimeTrackerMock, mock).anchor == new_anchor

    # A second scan changes nothing to the results
    validator._scan_until(mock, date_errors, until)

    assert date_errors == results
    assert cast(TimeTrackerMock, mock).set_errors == results
    assert cast(TimeTrackerMock, mock).anchor == new_anchor


def test_scan_until_nothing():
    """
    Check that nothing is scanned if the validation anchor is the same
    day as `until` date.
    """
    mock = cast(TimeTracker, TimeTrackerMock(2025, anchor=dt.date(2025, 1, 9)))
    until = dt.date(2025, 1, 9)

    validator = CustomValidator([])

    date_errors = {}
    validator._scan_until(mock, date_errors, until)

    assert date_errors == {}
    assert cast(TimeTrackerMock, mock).set_errors == {}
    assert cast(TimeTrackerMock, mock).anchor == until


def test_scan_until_no_error():
    """
    Check that when no error is scanned, the anchor date is moved to
    `until` date.
    """
    mock = cast(TimeTracker, TimeTrackerMock(2025, anchor=dt.date(2025, 1, 9)))
    until = dt.date(2025, 1, 25)

    validator = CustomValidator([])  # No error if no checker

    date_errors = {}
    validator._scan_until(mock, date_errors, until)

    assert date_errors == {}
    assert cast(TimeTrackerMock, mock).set_errors == {}
    assert cast(TimeTrackerMock, mock).anchor == until


def test_full_validation():
    """
    Integration test of the `validate()` function. Define a set of existing
    application and tracker errors, use a checker that sets some custom
    application errors and check the results.
    """
    # Make the mock a virtual subclass of TimeTrackerAnalyzer
    TimeTrackerAnalyzer.register(TimeTrackerMock)

    # Existing application and tracker errors
    app_errors = {
        dt.date(2025, 1, 2): 10,
        dt.date(2025, 2, 5): 10,
        dt.date(2025, 1, 20): 20,
    }

    tracker_errors = {
        dt.date(2025, 1, 12): 40,
        dt.date(2025, 1, 20): 30,
    }

    # The custom checker sets error 110 each 11 days
    checker = CustomChecker(110, lambda _, date: date.day % 11 == 0)
    validator = CustomValidator([checker])

    scanned_errors = {
        dt.date(2025, 1, 11): 110,
        dt.date(2025, 1, 22): 110,
        dt.date(2025, 2, 11): 110,
    }

    merge_errors = {
        # Important: even if outside scanning range, all existing errors are read
        dt.date(2025, 1, 2): 10,
        dt.date(2025, 1, 11): 110,
        dt.date(2025, 1, 12): 40,
        dt.date(2025, 1, 20): 30,
        dt.date(2025, 1, 22): 110,
        dt.date(2025, 2, 5): 10,
        dt.date(2025, 2, 11): 110,
    }

    mock = cast(
        TimeTrackerAnalyzer,
        TimeTrackerMock(
            2025,
            anchor=dt.date(2025, 1, 10),
            app_errors=app_errors,
            tracker_errors=tracker_errors,
        ),
    )

    def to_error(eid: int):
        return AttendanceError(eid, mock.get_attendance_error_desc(eid))

    # Convert merge_errors to an AttendanceError dictionary
    merge_errors = {date: to_error(eid) for date, eid in merge_errors.items()}

    until = dt.datetime(2025, 2, 20, hour=8)  # Scan from [10.01 to 19.02]

    status = validator.validate(mock, until)

    assert status == AttendanceErrorStatus.ERROR
    assert validator.errors_by_date == merge_errors
    assert validator.worse_error == to_error(110)
    assert cast(TimeTrackerMock, mock).set_errors == scanned_errors
    assert cast(TimeTrackerMock, mock).anchor == dt.date(2025, 1, 11)
