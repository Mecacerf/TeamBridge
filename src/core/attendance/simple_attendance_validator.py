#!/usr/bin/env python3
"""
File: simple_attendance_validator.py
Author: Bastian Cerf
Date: 20/07/2025
Description:
    Simple implementation of base classes provided in
    `attendance_validator.py`.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import logging
import datetime as dt
from typing import Optional, Sequence

# Internal libraries
from .attendance_validator import AttendanceChecker, AttendanceValidator
from core.time_tracker import TimeTracker, ClockEvent

logger = logging.getLogger(__name__)


class ContinuousWorkChecker(AttendanceChecker):
    """
    Verify that the employee didn't work more than the maximum allowed
    time without taking a break.
    """

    ERROR_ID = 10

    def __init__(self):
        super().__init__(self.ERROR_ID)

    def check_date(
        self,
        tracker: TimeTracker,
        date: dt.date,
        date_evts: Sequence[Optional[ClockEvent]],
    ) -> bool:
        max_time = tracker.max_continuous_work_time

        evt_pairs = [(e1, e2) for e1, e2 in zip(date_evts, date_evts[1:]) if e1 and e2]
        return any(self.__delta(e1.time, e2.time) >= max_time for e1, e2 in evt_pairs)

    def __delta(self, t1: dt.time, t2: dt.time) -> dt.timedelta:
        t1_delta = dt.timedelta(hours=t1.hour, minutes=t1.minute)
        t2_delta = dt.timedelta(hours=t2.hour, minutes=t2.minute)
        return max(dt.timedelta(0), t2_delta - t1_delta)


class ClockSequenceChecker(AttendanceChecker):
    """
    Verify that the clock events times are ordered chronologically.
    """

    ERROR_ID = 100

    def __init__(self):
        super().__init__(self.ERROR_ID)

    def check_date(
        self,
        tracker: TimeTracker,
        date: dt.date,
        date_evts: Sequence[Optional[ClockEvent]],
    ) -> bool:
        events = [evt for evt in date_evts if evt is not None]
        return any(e1.time >= e2.time for e1, e2 in zip(events, events[1:]))


class SimpleAttendanceValidator(AttendanceValidator):
    """
    Simple implementation of `AttendanceValidator` that checks that:
    - The maximal continuous work duration is not exceeded.
    - All clock events times are ordered chronologically.
    """

    def __init__(self):
        super().__init__([ContinuousWorkChecker(), ClockSequenceChecker()])
