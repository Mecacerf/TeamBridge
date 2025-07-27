#!/usr/bin/env python3
"""
File: attendance_checkers_test.py
Author: Bastian Cerf
Date: 23/07/2025
Description:
    Unit tests for the attendance checkers modules.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
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

    def __init__(self, evts):
        self._evts = evts

    def get_clocks(self, _) -> list[Optional[ClockEvent]]:
        return self._evts

    @property
    def max_continuous_work_time(self) -> dt.timedelta:
        return dt.timedelta(hours=6)


def test_continuous_work_checker_ok():
    """
    Check that the error is not present after 5h59 of continuous work.
    """
    mock = cast(
        TimeTracker,
        TimeTrackerMock(
            [
                ClockEvent(dt.time(hour=8), ClockAction.CLOCK_IN),
                ClockEvent(dt.time(hour=13, minute=59), ClockAction.CLOCK_OUT),
                None,
                ClockEvent(dt.time(hour=23), ClockAction.CLOCK_OUT),
            ]
        ),
    )

    any_date = dt.date.today()
    checker = ContinuousWorkChecker()
    assert checker.error_id == ContinuousWorkChecker.ERROR_ID
    assert not checker.check_date(mock, any_date, mock.get_clocks(any_date))


def test_continuous_work_checker_not_ok():
    """
    Check that the error is present after 6h of continuous work.
    """
    mock = cast(
        TimeTracker,
        TimeTrackerMock(
            [
                ClockEvent(dt.time(hour=8), ClockAction.CLOCK_IN),
                ClockEvent(dt.time(hour=10, minute=32), ClockAction.CLOCK_OUT),
                None,
                ClockEvent(dt.time(hour=11), ClockAction.CLOCK_OUT),
                ClockEvent(dt.time(hour=11, minute=30), ClockAction.CLOCK_IN),
                ClockEvent(dt.time(hour=17, minute=30), ClockAction.CLOCK_OUT),
                ClockEvent(dt.time(hour=23), ClockAction.CLOCK_IN),
            ]
        ),
    )

    any_date = dt.date.today()
    checker = ContinuousWorkChecker()
    assert checker.error_id == ContinuousWorkChecker.ERROR_ID
    assert checker.check_date(mock, any_date, mock.get_clocks(any_date))


def test_evts_order_ok():
    """
    Check that the error is not present for an ordered dataset.
    """
    mock = cast(
        TimeTracker,
        TimeTrackerMock(
            [
                ClockEvent(dt.time(hour=8), ClockAction.CLOCK_IN),
                ClockEvent(dt.time(hour=10, minute=32), ClockAction.CLOCK_OUT),
                None,
                ClockEvent(dt.time(hour=11), ClockAction.CLOCK_OUT),
                ClockEvent(dt.time(hour=11, minute=30), ClockAction.CLOCK_IN),
                ClockEvent(dt.time(hour=17, minute=30), ClockAction.CLOCK_OUT),
                ClockEvent(dt.time(hour=23), ClockAction.CLOCK_IN),
                ClockEvent(dt.time(hour=23, minute=1), ClockAction.CLOCK_OUT),
            ]
        ),
    )

    any_date = dt.date.today()
    checker = ClockSequenceChecker()
    assert checker.error_id == ClockSequenceChecker.ERROR_ID
    assert not checker.check_date(mock, any_date, mock.get_clocks(any_date))


def test_evts_order_ok_midnight():
    """
    Check that the error is not present for an ordered dataset with 
    midnight rollover.
    """
    mock = cast(
        TimeTracker,
        TimeTrackerMock(
            [
                ClockEvent(dt.time(hour=8), ClockAction.CLOCK_IN),
                ClockEvent(dt.time(hour=10, minute=32), ClockAction.CLOCK_OUT),
                None,
                ClockEvent(dt.time(hour=11), ClockAction.CLOCK_OUT),
                ClockEvent(dt.time(hour=11, minute=30), ClockAction.CLOCK_IN),
                ClockEvent(dt.time(hour=17, minute=30), ClockAction.CLOCK_OUT),
                ClockEvent(dt.time(hour=23), ClockAction.CLOCK_IN),
                ClockEvent.midnight_rollover()
            ]
        ),
    )

    any_date = dt.date.today()
    checker = ClockSequenceChecker()
    assert checker.error_id == ClockSequenceChecker.ERROR_ID
    assert not checker.check_date(mock, any_date, mock.get_clocks(any_date))


def test_evts_order_not_ok():
    """
    Check that the error is present for an unordered dataset.
    """
    mock = cast(
        TimeTracker,
        TimeTrackerMock(
            [
                ClockEvent(dt.time(hour=8), ClockAction.CLOCK_IN),
                ClockEvent(dt.time(hour=10, minute=32), ClockAction.CLOCK_OUT),
                None,
                ClockEvent(dt.time(hour=11), ClockAction.CLOCK_OUT),
                ClockEvent(dt.time(hour=11, minute=30), ClockAction.CLOCK_IN),
                ClockEvent(dt.time(hour=17, minute=30), ClockAction.CLOCK_OUT),
                ClockEvent(dt.time(hour=23), ClockAction.CLOCK_IN),
                ClockEvent(dt.time(hour=23), ClockAction.CLOCK_OUT),  # Same time
            ]
        ),
    )

    any_date = dt.date.today()
    checker = ClockSequenceChecker()
    assert checker.error_id == ClockSequenceChecker.ERROR_ID
    assert checker.check_date(mock, any_date, mock.get_clocks(any_date))
