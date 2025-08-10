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
from typing import Optional, Sequence, Final

# Internal libraries
from .attendance_validator import AttendanceChecker, AttendanceValidator
from core.time_tracker import TimeTracker, ClockEvent, ClockAction

logger = logging.getLogger(__name__)


########################################################################
#                   External attendance errors ids                     #
########################################################################


ERROR_MIDNIGHT_ROLLOVER_ID: Final = 30


########################################################################
#                           Custom checkers                            #
########################################################################


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

        # Pair clock-ins and clock-outs
        evt_pairs = [(e1, e2) for e1, e2 in zip(date_evts, date_evts[1:]) if e1 and e2]
        dt_pairs = [
            (dt.datetime.combine(date, e1.time), dt.datetime.combine(date, e2.time))
            for e1, e2 in evt_pairs
        ]

        # If the last event of the day is a midnight rollover, try to pair it
        # with the clock-out of the next day.
        if (
            evt_pairs
            and evt_pairs[-1][1] is ClockEvent.midnight_rollover()
            and date < dt.date(date.year, 12, 31)
        ):
            tomorrow = date + dt.timedelta(days=1)
            tomorrow_evts = tracker.get_clocks(tomorrow)
            # First event is a clock-in at 00:00, second is the clock-out
            if len(tomorrow_evts) > 1 and tomorrow_evts[1]:
                # Replace the last clock-out of the datetimes pairs
                dt_pairs[-1] = (
                    dt_pairs[-1][0],
                    dt.datetime.combine(tomorrow, tomorrow_evts[1].time),
                )

        return any(dt2 - dt1 >= max_time for dt1, dt2 in dt_pairs)


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
        evts = [evt for evt in date_evts if evt is not None]

        if (
            evts
            and evts[-1] is ClockEvent.midnight_rollover()
            and date < dt.date(date.year, 12, 31)
        ):
            # The next day first event must be a clock-in at 00:00
            tomorrow_evts = tracker.get_clocks(date + dt.timedelta(days=1))
            clock_in = ClockEvent(dt.time(hour=0), ClockAction.CLOCK_IN)
            if not tomorrow_evts or tomorrow_evts[0] != clock_in:
                return True

        return any(e1.time >= e2.time for e1, e2 in zip(evts, evts[1:]))


class SimpleAttendanceValidator(AttendanceValidator):
    """
    Simple implementation of `AttendanceValidator` that checks that:
    - The maximal continuous work duration is not exceeded.
    - All clock events times are ordered chronologically.
    """

    def __init__(self):
        super().__init__([ContinuousWorkChecker(), ClockSequenceChecker()])
