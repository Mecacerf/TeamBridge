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
from core.time_tracker import (
    TimeTracker,
    TimeTrackerAnalyzer,
    TimeTrackerDateException,
    ClockEvent,
    DateRange,
    DateOrDateRange,
    IntOrPerDate,
)
from core.attendance.attendance_validator import (
    AttendanceChecker,
    AttendanceValidator,
    AttendanceErrorStatus,
    AttendanceError,
    ErrorsReadMode,
)

logger = logging.getLogger(__name__)

########################################################################
#                     Attendance Validator Tests                       #
########################################################################


class CustomValidator(AttendanceValidator):

    def __init__(self, checkers: list[AttendanceChecker]):
        super().__init__(checkers)


class CustomChecker(AttendanceChecker):

    def __init__(
        self,
        error_id: int,
        func: Callable[[TimeTracker, dt.date, list[Optional[ClockEvent]]], bool],
    ):
        super().__init__(error_id)
        self._func = func

    def check_date(
        self, tracker: TimeTracker, date: dt.date, evts: list[Optional[ClockEvent]]
    ) -> bool:
        return self._func(tracker, date, evts)


class TimeTrackerMock:

    def __init__(
        self,
        year: int,
        anchor: Optional[dt.date] = None,
        clk_evts: Optional[list[Optional[ClockEvent]]] = None,
        app_errors: Optional[dict[dt.date, int]] = None,
        tracker_errors: Optional[dict[dt.date, int]] = None,
        year_error: Optional[int] = None,
    ):
        self._year = year

        self.anchor = dt.datetime.now().date()
        if anchor:
            self.anchor = anchor

        self._clk_evts = []
        if clk_evts:
            self._clk_evts = clk_evts

        self._errors = {}
        if app_errors:
            self._app_errors = app_errors

        self._tracker_errors = {}
        if tracker_errors:
            self._tracker_errors = tracker_errors

        self._year_error = 0
        if year_error:
            self._year_error = year_error

        self.set_errors = {}

    def __str__(self):
        return f"{self.__class__.__name__}"

    @property
    def tracked_year(self) -> int:
        return self._year

    def analyze(self, datetime: dt.datetime):
        logger.info(f"{self!s} analyzed for {datetime}.")

    @property
    def analyzed(self):
        return True

    def get_clocks(self, _: dt.date) -> list[Optional[ClockEvent]]:
        return self._clk_evts

    def save(self):
        logger.info(f"{self!s} saved.")

    def get_last_validation_anchor(self) -> dt.date:
        return self.anchor

    def get_attendance_error(self, date: DateOrDateRange) -> IntOrPerDate:
        if isinstance(date, dt.date):
            return self._app_errors.get(date, 0)
        return {date: self._app_errors.get(date, 0) for date in date.iter_days()}

    def get_attendance_error_desc(self, error_id: int) -> str:
        return f"Mock error {error_id}"

    def read_day_attendance_error(self, date: DateOrDateRange) -> IntOrPerDate:
        if isinstance(date, dt.date):
            return self._tracker_errors.get(date, 0)
        return {date: self._tracker_errors.get(date, 0) for date in date.iter_days()}

    def read_year_attendance_error(self) -> int:
        return self._year_error

    def set_attendance_error(self, date: dt.date, error_id: int):
        self.set_errors[date] = error_id

    def set_last_validation_anchor(self, date: dt.date):
        self.anchor = date


def test_existing_errors_simple_tracker():
    """
    Test the private `_read_existing_errors` of the validator. It should
    return the application errors contained in the given range.
    """
    dates_rng = DateRange(dt.date(2025, 1, 1), dt.date(2025, 2, 10))

    mock = cast(
        TimeTracker,
        TimeTrackerMock(
            2025,
            app_errors={
                dt.date(2025, 1, 2): 10,
                dt.date(2025, 2, 5): 10,
                dt.date(2025, 1, 20): 20,
                dt.date(2025, 2, 26): 20,  # Out of range
            },
        ),
    )

    expected_errors = {
        dt.date(2025, 1, 2): 10,
        dt.date(2025, 2, 5): 10,
        dt.date(2025, 1, 20): 20,
    }

    validator = CustomValidator([])
    date_errors = {}
    validator._read_existing_errors(mock, date_errors, dates_rng)

    assert date_errors == expected_errors


def test_existing_errors_tracker_analyzer():
    """
    Test the private `_read_existing_errors` of the validator. It should
    return the merge of the application errors and the time tracker
    analyzer errors, with the highest error selected for each day.
    """

    # Make a mock class that virtually extends TimeTrackerAnalyzer
    class TimeTrackerAnalyzerMock(TimeTrackerMock):
        pass

    TimeTrackerAnalyzer.register(TimeTrackerAnalyzerMock)

    dates_rng = DateRange(dt.date(2025, 1, 2), dt.date(2025, 2, 10))

    mock = cast(
        TimeTrackerAnalyzer,
        TimeTrackerAnalyzerMock(
            2025,
            app_errors={
                dt.date(2025, 1, 1): 10,  # Out of range
                dt.date(2025, 1, 2): 10,
                dt.date(2025, 2, 5): 10,
                dt.date(2025, 1, 20): 20,
            },
            tracker_errors={
                dt.date(2025, 1, 12): 40,
                dt.date(2025, 1, 20): 30,
                dt.date(2025, 2, 20): 30,  # Out of range
            },
            year_error=40,  # The analyzer provides the highest error
        ),
    )

    expected_errors = {
        dt.date(2025, 1, 2): 10,
        dt.date(2025, 1, 20): 30,  # The highest error is selected for the date
        dt.date(2025, 2, 5): 10,
        dt.date(2025, 1, 12): 40,
    }

    validator = CustomValidator([])
    date_errors = {}
    validator._read_existing_errors(mock, date_errors, dates_rng)

    assert date_errors == expected_errors


def test_existing_errors_tracker_analyzer_abort():
    """
    Test the private `_read_existing_errors` of the validator. It should
    abort the read process if the analyzer says that the year error (most
    critical error registered) is 0.
    """

    # Make a mock class that virtually extends TimeTrackerAnalyzer
    class TimeTrackerAnalyzerMock(TimeTrackerMock):
        pass

    TimeTrackerAnalyzer.register(TimeTrackerAnalyzerMock)

    dates_rng = DateRange(dt.date(2025, 1, 2), dt.date(2025, 2, 10))

    mock = cast(
        TimeTrackerAnalyzer,
        TimeTrackerAnalyzerMock(
            2025,
            app_errors={
                # Put something in the list to verify it doesn't appear
                # in the results.
                dt.date(2025, 1, 20): 20,
            },
            tracker_errors={
                dt.date(2025, 1, 12): 40,
            },
            year_error=0,
        ),
    )

    expected_errors = {}

    validator = CustomValidator([])
    date_errors = {}
    validator._read_existing_errors(mock, date_errors, dates_rng)

    assert date_errors == expected_errors


def test_scan_11_days_range():
    """
    Setup 3 checkers in the validator that create a known errors sequence.
    Scan for 11 days and verify the sequence.
    """
    start_date = dt.date(2025, 1, 9)
    end_date = dt.date(2025, 1, 20)
    mock = cast(TimeTracker, TimeTrackerMock(2025, anchor=start_date))

    # First checker sets error 10 each 5 days
    checker1 = CustomChecker(10, lambda _, date, __: date.day % 5 == 0)
    # Second checker sets error 20 to pair days
    checker2 = CustomChecker(20, lambda _, date, __: date.day % 2 == 0)
    # Third checker sets error 30 each four days
    checker3 = CustomChecker(30, lambda _, date, __: date.day % 4 == 0)

    validator = CustomValidator([checker1, checker2, checker3])

    results = {
        dt.date(2025, 1, 10): 20,
        dt.date(2025, 1, 12): 30,
        dt.date(2025, 1, 14): 20,
        dt.date(2025, 1, 15): 10,
        dt.date(2025, 1, 16): 30,
        dt.date(2025, 1, 18): 20,
    }

    # Anchor date moves to the first date with an error
    new_anchor = dt.date(2025, 1, 10)

    date_errors = {}
    error_date = validator._scan_range(
        mock, date_errors, DateRange(start_date, end_date)
    )

    assert date_errors == results
    assert error_date == new_anchor
    # Check errors have been written in the tracker
    assert cast(TimeTrackerMock, mock).set_errors == results


def test_scan_until_nothing():
    """
    Check that nothing is scanned if the validation anchor is the same
    day as `until` date.
    """
    start_date = dt.date(2025, 1, 9)
    end_date = dt.date(2025, 1, 9)
    mock = cast(TimeTracker, TimeTrackerMock(2025, anchor=start_date))

    validator = CustomValidator([])

    date_errors = {}
    error_date = validator._scan_range(
        mock, date_errors, DateRange(start_date, end_date)
    )

    assert date_errors == {}
    assert error_date == None
    assert cast(TimeTrackerMock, mock).set_errors == {}


def test_scan_until_no_error():
    """
    Check that when no error is scanned, the anchor date is moved to
    teh last date of the range.
    """
    start_date = dt.date(2025, 1, 9)
    end_date = dt.date(2025, 1, 20)
    mock = cast(TimeTracker, TimeTrackerMock(2025, anchor=start_date))

    validator = CustomValidator([])  # No error if no checker

    date_errors = {}
    error_date = validator._scan_range(
        mock, date_errors, DateRange(start_date, end_date)
    )

    assert date_errors == {}
    assert error_date == end_date
    assert cast(TimeTrackerMock, mock).set_errors == {}


def test_validation_wrong_anchor():
    """
    Check that the validator raises an exception if the validation anchor
    date is at the wrong year.
    """
    mock = cast(TimeTracker, TimeTrackerMock(2025, anchor=dt.date(2023, 1, 1)))

    validator = CustomValidator([])
    with pytest.raises(TimeTrackerDateException):
        # Wrong anchor date
        validator.validate(mock, dt.datetime(mock.tracked_year, 1, 1))


def test_validation_wrong_until():
    """
    Check that the validator raises an exception if the `until`
    date is at the wrong year.
    """
    mock = cast(TimeTracker, TimeTrackerMock(2025, anchor=dt.date(2025, 1, 1)))

    validator = CustomValidator([])
    with pytest.raises(TimeTrackerDateException):
        # Wrong until date
        validator.validate(mock, dt.datetime(2023, 1, 1))


def test_full_validation_month_mode():
    """
    Integration test of the `validate()` function. Define a set of existing
    application and tracker errors, use a checker that sets some custom
    application errors and check the results.
    """

    # Make a mock class that virtually extends TimeTrackerAnalyzer
    class TimeTrackerAnalyzerMock(TimeTrackerMock):
        pass

    TimeTrackerAnalyzer.register(TimeTrackerAnalyzerMock)

    # Scan from [10.01 to 19.02]
    anchor_date = dt.date(2025, 1, 10)
    until = dt.datetime(2025, 2, 20, hour=8)

    # Existing application and tracker errors
    # In month mode, only errors of February will be reported
    app_errors = {
        dt.date(2025, 1, 2): 10,  # Out of reading range
        dt.date(2025, 2, 5): 10,
        dt.date(2025, 2, 20): 20,
        dt.date(2025, 3, 10): 40,  # Out of reading range
    }

    tracker_errors = {
        dt.date(2025, 1, 12): 40,  # Out of reading range
        dt.date(2025, 2, 20): 30,
        dt.date(2025, 3, 15): 50,  # Out of reading range
    }

    # The custom checker sets error 110 each 11 days
    checker = CustomChecker(110, lambda _, date, __: date.day % 11 == 0)
    validator = CustomValidator([checker])

    # Scan from [10.01 to 19.02]
    scanned_errors = {
        dt.date(2025, 1, 11): 110,
        dt.date(2025, 1, 22): 110,
        dt.date(2025, 2, 11): 110,
    }

    expected_errors = {
        dt.date(2025, 2, 5): 10,  # Reported by reading existing
        dt.date(2025, 2, 20): 30,  # Reported by reading existing
        dt.date(2025, 1, 11): 110,  # Reported by scan
        dt.date(2025, 1, 22): 110,  # Reported by scan
        dt.date(2025, 2, 11): 110,  # Reported by scan
    }

    # After validation, anchor date is moved to the first day in error
    moved_anchor_date = dt.date(2025, 1, 11)

    mock = cast(
        TimeTrackerAnalyzer,
        TimeTrackerAnalyzerMock(
            2025,
            anchor=anchor_date,
            app_errors=app_errors,
            tracker_errors=tracker_errors,
            year_error=40,  # The analyzer reports the worse error up to February
        ),
    )

    def to_error(eid: int):
        return AttendanceError(eid, mock.get_attendance_error_desc(eid))

    # Convert errors to an AttendanceError dictionary for comparison
    expected_errors = {date: to_error(eid) for date, eid in expected_errors.items()}

    status = validator.validate(mock, until, ErrorsReadMode.MONTH_ONLY)

    assert status == AttendanceErrorStatus.ERROR  # ID 110 is an error
    assert validator.date_errors == expected_errors
    assert validator.dominant_error == to_error(110)
    assert cast(TimeTrackerMock, mock).set_errors == scanned_errors
    assert cast(TimeTrackerMock, mock).anchor == moved_anchor_date


def test_full_validation_year_mode():
    """
    Integration test of the `validate()` function. Define a set of existing
    application and tracker errors, use a checker that sets some custom
    application errors and check the results.
    """

    # Make a mock class that virtually extends TimeTrackerAnalyzer
    class TimeTrackerAnalyzerMock(TimeTrackerMock):
        pass

    TimeTrackerAnalyzer.register(TimeTrackerAnalyzerMock)

    # Scan from [10.01 to 19.02]
    anchor_date = dt.date(2025, 1, 10)
    until = dt.datetime(2025, 2, 20, hour=8)

    # Existing application and tracker errors
    # In year mode, all errors are reported
    app_errors = {
        dt.date(2025, 1, 2): 10,
        dt.date(2025, 2, 5): 10,
        dt.date(2025, 2, 20): 20,
        dt.date(2025, 3, 10): 40,
    }

    tracker_errors = {
        dt.date(2025, 1, 12): 40,
        dt.date(2025, 2, 20): 30,
        dt.date(2025, 3, 15): 50,
    }

    # The custom checker sets error 110 each 11 days
    checker = CustomChecker(110, lambda _, date, __: date.day % 11 == 0)
    validator = CustomValidator([checker])

    # Scan from [10.01 to 19.02]
    scanned_errors = {
        dt.date(2025, 1, 11): 110,
        dt.date(2025, 1, 22): 110,
        dt.date(2025, 2, 11): 110,
    }

    expected_errors = {
        dt.date(2025, 1, 2): 10,  # Reported by reading existing
        dt.date(2025, 2, 5): 10,  # Reported by reading existing
        dt.date(2025, 3, 10): 40,  # Reported by reading existing
        dt.date(2025, 1, 12): 40,  # Reported by reading existing
        dt.date(2025, 2, 20): 30,  # Reported by reading existing
        dt.date(2025, 3, 15): 50,  # Reported by reading existing
        dt.date(2025, 1, 11): 110,  # Reported by scan
        dt.date(2025, 1, 22): 110,  # Reported by scan
        dt.date(2025, 2, 11): 110,  # Reported by scan
    }

    # After validation, anchor date is moved to the first day in error
    # But it cannot move backward
    moved_anchor_date = dt.date(2025, 1, 11)

    mock = cast(
        TimeTrackerAnalyzer,
        TimeTrackerAnalyzerMock(
            2025,
            anchor=anchor_date,
            app_errors=app_errors,
            tracker_errors=tracker_errors,
            year_error=40,  # The analyzer reports the worse error up to February
        ),
    )

    def to_error(eid: int):
        return AttendanceError(eid, mock.get_attendance_error_desc(eid))

    # Convert errors to an AttendanceError dictionary for comparison
    expected_errors = {date: to_error(eid) for date, eid in expected_errors.items()}

    status = validator.validate(mock, until, ErrorsReadMode.WHOLE_YEAR)

    assert status == AttendanceErrorStatus.ERROR  # ID 110 is an error
    assert validator.date_errors == expected_errors
    assert validator.dominant_error == to_error(110)
    assert cast(TimeTrackerMock, mock).set_errors == scanned_errors
    assert cast(TimeTrackerMock, mock).anchor == moved_anchor_date


def test_full_validation_validation_range_mode():
    """
    Integration test of the `validate()` function. Define a set of existing
    application and tracker errors, use a checker that sets some custom
    application errors and check the results.
    """

    # Make a mock class that virtually extends TimeTrackerAnalyzer
    class TimeTrackerAnalyzerMock(TimeTrackerMock):
        pass

    TimeTrackerAnalyzer.register(TimeTrackerAnalyzerMock)

    # Scan from [10.01 to 19.02]
    anchor_date = dt.date(2025, 1, 10)
    until = dt.datetime(2025, 2, 20, hour=8)

    # Existing application and tracker errors
    # The same range is used for scanning and reading existing errors
    app_errors = {
        dt.date(2025, 1, 2): 10,  # Out of reading range
        dt.date(2025, 2, 5): 10,
        dt.date(2025, 2, 20): 20,  # Out of reading range
        dt.date(2025, 3, 10): 40,  # Out of reading range
    }

    tracker_errors = {
        dt.date(2025, 1, 12): 40,
        dt.date(2025, 2, 20): 30,  # Out of reading range
        dt.date(2025, 3, 15): 50,  # Out of reading range
    }

    # The custom checker sets error 110 each 11 days
    checker = CustomChecker(110, lambda _, date, __: date.day % 11 == 0)
    validator = CustomValidator([checker])

    # Scan from [10.01 to 19.02]
    scanned_errors = {
        dt.date(2025, 1, 11): 110,
        dt.date(2025, 1, 22): 110,
        dt.date(2025, 2, 11): 110,
    }

    expected_errors = {
        dt.date(2025, 2, 5): 10,  # Reported by reading existing
        dt.date(2025, 1, 12): 40,  # Reported by reading existing
        dt.date(2025, 1, 11): 110,  # Reported by scan
        dt.date(2025, 1, 22): 110,  # Reported by scan
        dt.date(2025, 2, 11): 110,  # Reported by scan
    }

    # After validation, anchor date is moved to the first day in error
    moved_anchor_date = dt.date(2025, 1, 11)

    mock = cast(
        TimeTrackerAnalyzer,
        TimeTrackerAnalyzerMock(
            2025,
            anchor=anchor_date,
            app_errors=app_errors,
            tracker_errors=tracker_errors,
            year_error=40,  # The analyzer reports the worse error up to February
        ),
    )

    def to_error(eid: int):
        return AttendanceError(eid, mock.get_attendance_error_desc(eid))

    # Convert errors to an AttendanceError dictionary for comparison
    expected_errors = {date: to_error(eid) for date, eid in expected_errors.items()}

    status = validator.validate(mock, until, ErrorsReadMode.VALIDATION_RANGE_ONLY)

    assert status == AttendanceErrorStatus.ERROR  # ID 110 is an error
    assert validator.date_errors == expected_errors
    assert validator.dominant_error == to_error(110)
    assert cast(TimeTrackerMock, mock).set_errors == scanned_errors
    assert cast(TimeTrackerMock, mock).anchor == moved_anchor_date


def test_full_validation_no_read_mode():
    """
    Integration test of the `validate()` function. Define a set of existing
    application and tracker errors, use a checker that sets some custom
    application errors and check the results.
    """

    # Make a mock class that virtually extends TimeTrackerAnalyzer
    class TimeTrackerAnalyzerMock(TimeTrackerMock):
        pass

    TimeTrackerAnalyzer.register(TimeTrackerAnalyzerMock)

    # Scan from [10.01 to 19.02]
    anchor_date = dt.date(2025, 1, 10)
    until = dt.datetime(2025, 2, 20, hour=8)

    # Existing application and tracker errors
    app_errors = {
        dt.date(2025, 1, 2): 10,  # Out of reading range
        dt.date(2025, 2, 5): 10,  # Out of reading range
        dt.date(2025, 2, 20): 20,  # Out of reading range
        dt.date(2025, 3, 10): 40,  # Out of reading range
    }

    tracker_errors = {
        dt.date(2025, 1, 12): 40,  # Out of reading range
        dt.date(2025, 2, 20): 30,  # Out of reading range
        dt.date(2025, 3, 15): 50,  # Out of reading range
    }

    # The custom checker sets error 110 each 11 days
    checker = CustomChecker(110, lambda _, date, __: date.day % 11 == 0)
    validator = CustomValidator([checker])

    # Scan from [10.01 to 19.02]
    scanned_errors = {
        dt.date(2025, 1, 11): 110,
        dt.date(2025, 1, 22): 110,
        dt.date(2025, 2, 11): 110,
    }

    expected_errors = {
        dt.date(2025, 1, 11): 110,  # Reported by scan
        dt.date(2025, 1, 22): 110,  # Reported by scan
        dt.date(2025, 2, 11): 110,  # Reported by scan
    }

    # After validation, anchor date is moved to the first day in error
    moved_anchor_date = dt.date(2025, 1, 11)

    mock = cast(
        TimeTrackerAnalyzer,
        TimeTrackerAnalyzerMock(
            2025,
            anchor=anchor_date,
            app_errors=app_errors,
            tracker_errors=tracker_errors,
            year_error=40,  # The analyzer reports the worse error up to February
        ),
    )

    def to_error(eid: int):
        return AttendanceError(eid, mock.get_attendance_error_desc(eid))

    # Convert errors to an AttendanceError dictionary for comparison
    expected_errors = {date: to_error(eid) for date, eid in expected_errors.items()}

    status = validator.validate(mock, until, ErrorsReadMode.NO_READ)

    assert status == AttendanceErrorStatus.ERROR  # ID 110 is an error
    assert validator.date_errors == expected_errors
    assert validator.dominant_error == to_error(110)
    assert cast(TimeTrackerMock, mock).set_errors == scanned_errors
    assert cast(TimeTrackerMock, mock).anchor == moved_anchor_date


def test_full_validation_month_mode_simple_tracker_has_error():
    """
    Integration test of the `validate()` function. Define a set of existing
    application and tracker errors, use a checker that sets some custom
    application errors and check the results.
    """
    # Scan from [10.01 to 19.02]
    anchor_date = dt.date(2025, 1, 10)
    until = dt.datetime(2025, 2, 20, hour=8)

    # Existing application and tracker errors
    # In month mode, only errors of February will be reported
    app_errors = {
        dt.date(2025, 1, 2): 10,  # Out of reading range
        dt.date(2025, 2, 5): 10,
        dt.date(2025, 2, 20): 120,  # Error will prevent scan
        dt.date(2025, 3, 10): 40,  # Out of reading range
    }

    # The custom checker sets error 110 each 11 days
    checker = CustomChecker(110, lambda _, date, __: date.day % 11 == 0)
    validator = CustomValidator([checker])

    # Scan from [10.01 to 19.02]
    scanned_errors = {}

    expected_errors = {
        dt.date(2025, 2, 5): 10,  # Reported by reading existing
        dt.date(2025, 2, 20): 120,  # Reported by reading existing
    }

    # Anchor date hasn't moved because no scan was performed
    moved_anchor_date = anchor_date

    mock = cast(
        TimeTracker,
        TimeTrackerMock(
            2025,
            anchor=anchor_date,
            app_errors=app_errors,
            year_error=40,  # The analyzer reports the worse error up to February
        ),
    )

    def to_error(eid: int):
        return AttendanceError(eid, mock.get_attendance_error_desc(eid))

    # Convert errors to an AttendanceError dictionary for comparison
    expected_errors = {date: to_error(eid) for date, eid in expected_errors.items()}

    status = validator.validate(mock, until, ErrorsReadMode.MONTH_ONLY)

    assert status == AttendanceErrorStatus.ERROR  # ID 120 is an error
    assert validator.date_errors == expected_errors
    assert validator.dominant_error == to_error(120)
    assert cast(TimeTrackerMock, mock).set_errors == scanned_errors
    assert cast(TimeTrackerMock, mock).anchor == moved_anchor_date
