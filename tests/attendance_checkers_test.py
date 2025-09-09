#!/usr/bin/env python3

# Standard libraries
import pytest
from typing import Optional, cast
import datetime as dt
import logging

# Internal libraries
from .test_constants import *
from core.time_tracker import TimeTracker, ClockEvent, ClockAction
from core.attendance.simple_attendance_validator import (
    ContinuousWorkChecker,
    ClockSequenceChecker,
)

logger = logging.getLogger(__name__)

########################################################################
#                     Attendance Checkers Tests                        #
########################################################################


class TimeTrackerMock:

    def __init__(self, evts: dict[dt.date, list[Optional[ClockEvent]]]):
        self._evts = evts

    def get_clocks(self, date: dt.date) -> list[Optional[ClockEvent]]:
        return self._evts.get(date, [])

    @property
    def max_continuous_work_time(self) -> dt.timedelta:
        return dt.timedelta(hours=6)


@pytest.fixture
def any_date():
    return dt.date(2025, 5, 6)  # Anything except 31.12


def test_continuous_work_checker_ok(any_date: dt.date):
    """
    Check that the error is not present after 5h59 of continuous work or
    for an empty day.
    """
    any_date_1 = any_date + dt.timedelta(days=1)

    mock = cast(
        TimeTracker,
        TimeTrackerMock(
            {
                any_date: [
                    ClockEvent(dt.time(hour=8), ClockAction.CLOCK_IN),
                    ClockEvent(dt.time(hour=13, minute=59), ClockAction.CLOCK_OUT),
                    None,
                    ClockEvent(dt.time(hour=23), ClockAction.CLOCK_OUT),
                ]
            }
        ),
    )

    checker = ContinuousWorkChecker()
    assert checker.error_id == ContinuousWorkChecker.ERROR_ID
    assert not checker.check_date(mock, any_date, mock.get_clocks(any_date))
    assert not checker.check_date(mock, any_date_1, mock.get_clocks(any_date_1))


def test_continuous_work_checker_not_ok(any_date: dt.date):
    """
    Check that the error is present after 6h of continuous work.
    """
    mock = cast(
        TimeTracker,
        TimeTrackerMock(
            {
                any_date: [
                    ClockEvent(dt.time(hour=8), ClockAction.CLOCK_IN),
                    ClockEvent(dt.time(hour=10, minute=32), ClockAction.CLOCK_OUT),
                    None,
                    ClockEvent(dt.time(hour=11), ClockAction.CLOCK_OUT),
                    ClockEvent(dt.time(hour=11, minute=30), ClockAction.CLOCK_IN),
                    ClockEvent(dt.time(hour=17, minute=30), ClockAction.CLOCK_OUT),
                    ClockEvent(dt.time(hour=23), ClockAction.CLOCK_IN),
                ]
            }
        ),
    )

    checker = ContinuousWorkChecker()
    assert checker.error_id == ContinuousWorkChecker.ERROR_ID
    assert checker.check_date(mock, any_date, mock.get_clocks(any_date))


def test_continuous_work_checker_not_ok_midnight(any_date: dt.date):
    """
    Check that the error is present after 6h of continuous work with a
    midnight rollover. The error is reported the first day.
    """
    any_date_1 = any_date + dt.timedelta(days=1)

    mock = cast(
        TimeTracker,
        TimeTrackerMock(
            {
                any_date: [
                    ClockEvent(dt.time(hour=21), ClockAction.CLOCK_IN),
                    ClockEvent.midnight_rollover(),
                ],
                any_date_1: [
                    ClockEvent(dt.time(hour=0), ClockAction.CLOCK_IN),
                    ClockEvent(dt.time(hour=3), ClockAction.CLOCK_OUT),
                ],
            }
        ),
    )

    checker = ContinuousWorkChecker()
    assert checker.error_id == ContinuousWorkChecker.ERROR_ID
    assert checker.check_date(mock, any_date, mock.get_clocks(any_date))
    assert not checker.check_date(mock, any_date_1, mock.get_clocks(any_date_1))


def test_evts_order_ok(any_date: dt.date):
    """
    Check that the error is not present for an ordered dataset or an empty
    dataset.
    """
    any_date_1 = any_date + dt.timedelta(days=1)

    mock = cast(
        TimeTracker,
        TimeTrackerMock(
            {
                any_date: [
                    ClockEvent(dt.time(hour=8), ClockAction.CLOCK_IN),
                    ClockEvent(dt.time(hour=10, minute=32), ClockAction.CLOCK_OUT),
                    None,
                    ClockEvent(dt.time(hour=11), ClockAction.CLOCK_OUT),
                    ClockEvent(dt.time(hour=11, minute=30), ClockAction.CLOCK_IN),
                    ClockEvent(dt.time(hour=17, minute=30), ClockAction.CLOCK_OUT),
                    ClockEvent(dt.time(hour=23), ClockAction.CLOCK_IN),
                    ClockEvent(dt.time(hour=23, minute=1), ClockAction.CLOCK_OUT),
                ]
            }
        ),
    )

    checker = ClockSequenceChecker()
    assert checker.error_id == ClockSequenceChecker.ERROR_ID
    assert not checker.check_date(mock, any_date, mock.get_clocks(any_date))
    assert not checker.check_date(mock, any_date_1, mock.get_clocks(any_date_1))


def test_evts_order_ok_midnight(any_date: dt.date):
    """
    Check that the error is not present for an ordered dataset with
    midnight rollover.
    """
    mock = cast(
        TimeTracker,
        TimeTrackerMock(
            {
                any_date: [
                    ClockEvent(dt.time(hour=8), ClockAction.CLOCK_IN),
                    ClockEvent(dt.time(hour=10, minute=32), ClockAction.CLOCK_OUT),
                    None,
                    ClockEvent(dt.time(hour=11), ClockAction.CLOCK_OUT),
                    ClockEvent(dt.time(hour=11, minute=30), ClockAction.CLOCK_IN),
                    ClockEvent(dt.time(hour=17, minute=30), ClockAction.CLOCK_OUT),
                    ClockEvent(dt.time(hour=23), ClockAction.CLOCK_IN),
                    ClockEvent.midnight_rollover(),  # Trigger a check the next day
                ],
                any_date
                + dt.timedelta(days=1): [
                    ClockEvent(dt.time(hour=0), ClockAction.CLOCK_IN),
                    ClockEvent(dt.time(hour=5), ClockAction.CLOCK_OUT),
                ],
            }
        ),
    )

    checker = ClockSequenceChecker()
    assert checker.error_id == ClockSequenceChecker.ERROR_ID
    assert not checker.check_date(mock, any_date, mock.get_clocks(any_date))


def test_evts_order_not_ok(any_date: dt.date):
    """
    Check that the error is present for an unordered dataset.
    """
    mock = cast(
        TimeTracker,
        TimeTrackerMock(
            {
                any_date: [
                    ClockEvent(dt.time(hour=8), ClockAction.CLOCK_IN),
                    ClockEvent(dt.time(hour=10, minute=32), ClockAction.CLOCK_OUT),
                    None,
                    ClockEvent(dt.time(hour=11), ClockAction.CLOCK_OUT),
                    ClockEvent(dt.time(hour=11, minute=30), ClockAction.CLOCK_IN),
                    ClockEvent(dt.time(hour=17, minute=30), ClockAction.CLOCK_OUT),
                    ClockEvent(dt.time(hour=23), ClockAction.CLOCK_IN),
                    ClockEvent(dt.time(hour=23), ClockAction.CLOCK_OUT),  # Same time
                ]
            }
        ),
    )

    checker = ClockSequenceChecker()
    assert checker.error_id == ClockSequenceChecker.ERROR_ID
    assert checker.check_date(mock, any_date, mock.get_clocks(any_date))


def test_evts_order_not_ok_midnight(any_date: dt.date):
    """
    Check that the error is present for a dataset with a midnight rollover
    that is not followed by a clock-in at midnight.
    """
    any_date_1 = any_date + dt.timedelta(days=1)

    mock = cast(
        TimeTracker,
        TimeTrackerMock(
            {
                any_date: [
                    ClockEvent(dt.time(hour=8), ClockAction.CLOCK_IN),
                    ClockEvent.midnight_rollover(),  # Trigger a check the next day
                ],
                any_date_1: [
                    # Should start with a clock-in at 00:00
                    ClockEvent(dt.time(hour=0, minute=1), ClockAction.CLOCK_IN),
                ],
            }
        ),
    )

    checker = ClockSequenceChecker()
    assert checker.error_id == ClockSequenceChecker.ERROR_ID
    # The error is reported the first day
    assert checker.check_date(mock, any_date, mock.get_clocks(any_date))
    assert not checker.check_date(mock, any_date_1, mock.get_clocks(any_date_1))


def test_evts_order_not_ok_midnight_missing(any_date: dt.date):
    """
    Check that the error is present for a dataset with a midnight rollover
    that is not followed by a clock-in at midnight (missing event).
    """
    any_date_1 = any_date + dt.timedelta(days=1)

    mock = cast(
        TimeTracker,
        TimeTrackerMock(
            {
                any_date: [
                    ClockEvent(dt.time(hour=8), ClockAction.CLOCK_IN),
                    ClockEvent.midnight_rollover(),  # Trigger a check the next day
                ]
                # We assume the HR forgot to fill the next day
            }
        ),
    )

    checker = ClockSequenceChecker()
    assert checker.error_id == ClockSequenceChecker.ERROR_ID
    # The error is reported the first day
    assert checker.check_date(mock, any_date, mock.get_clocks(any_date))
    assert not checker.check_date(mock, any_date_1, mock.get_clocks(any_date_1))
