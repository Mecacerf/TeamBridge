#!/usr/bin/env python3
"""
File: teambridge_model_test.py
Author: Bastian Cerf
Date: 13/04/2025
Description:
    Unit test the TeamBridgeScheduler to validate expected behaviors.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import time
import logging

logger = logging.getLogger(__name__)

# Internal libraries
from .test_constants import *
from model.teambridge_scheduler import *

########################################################################
#                           Tests constants                            #
########################################################################

# Has already clock-in: 07:45, clock-out: 09:50, clock-in: 10:00
TEST_DATE = dt.date(year=2025, month=2, day=11)

########################################################################
#                            Unit tests                                #
########################################################################


# Wait for the task to finish
def wait_result(scheduler: TeamBridgeScheduler, handle: int) -> Optional[IModelMessage]:
    # Poll the model until a message is posted or timed out
    timeout = time.time() + 40.0
    while not scheduler.available(handle):
        assert scheduler.get_result(handle) is None
        assert time.time() < timeout
        time.sleep(0.1)
    # Return the task message
    message = scheduler.get_result(handle)
    logger.info(f"Got model message: {message}")
    return message


def test_clock_action(scheduler: TeamBridgeScheduler):
    """
    Clock in and out the test employee, check expected messages are
    received. Finally perform a consultation.
    """
    # Register a clock out at 12h15 to close the day work
    handle = scheduler.start_clock_action_task(
        TEST_EMPLOYEE_ID,
        dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=12, minute=15)),
    )
    # Wait until the task finishes
    msg = wait_result(scheduler, handle)
    # Assert expected message
    assert isinstance(msg, EmployeeEvent)
    assert msg.id == TEST_EMPLOYEE_ID
    assert msg.clock_evt.time == dt.time(hour=12, minute=15)
    assert msg.clock_evt.action == ClockAction.CLOCK_OUT

    # Consultation of employee's data at 15h
    handle = scheduler.start_consultation_task(
        TEST_EMPLOYEE_ID,
        dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=15, minute=0)),
    )
    # Wait until the task finishes
    msg = wait_result(scheduler, handle)
    # Assert expected message
    assert isinstance(msg, EmployeeData)
    assert msg.id == TEST_EMPLOYEE_ID
    assert msg.day_worked_time == dt.timedelta(hours=4, minutes=20)


def test_midnight_rollover(factory: TimeTrackerFactory, scheduler: TeamBridgeScheduler):
    """
    Register a clock-in event before midnight and a clock-out after
    midnight and check that a midnight rollover has been registered.
    """
    # Register a clock out at 12h15
    handle = scheduler.start_clock_action_task(
        TEST_EMPLOYEE_ID,
        dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=12, minute=15)),
        ClockAction.CLOCK_OUT,
    )
    # Wait until the task finishes
    assert isinstance(wait_result(scheduler, handle), EmployeeEvent)

    # Register a clock in at 22h00
    handle = scheduler.start_clock_action_task(
        TEST_EMPLOYEE_ID,
        dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=22, minute=0)),
        ClockAction.CLOCK_IN,
    )
    # Wait until the task finishes
    assert isinstance(wait_result(scheduler, handle), EmployeeEvent)

    # Register a clock event tomorrow at 2:00
    # A midnight rollover should be done
    tomorrow = TEST_DATE + dt.timedelta(days=1)
    handle = scheduler.start_clock_action_task(
        TEST_EMPLOYEE_ID, dt.datetime.combine(date=tomorrow, time=dt.time(hour=2))
    )
    # Wait until the task finishes
    assert isinstance(wait_result(scheduler, handle), EmployeeEvent)

    with factory.create(TEST_EMPLOYEE_ID, TEST_DATE) as tracker:
        # Check that the last event is a clock at midnight (special value)
        evts = tracker.get_clocks(TEST_DATE)
        assert evts and evts[-1] is ClockEvent.midnight_rollover()
        # The first event of tomorrow is a clock-in at midnight
        evts = tracker.get_clocks(tomorrow)
        assert evts and evts[0] == ClockEvent(dt.time(0, 0), ClockAction.CLOCK_IN)
        # And the last event of tomorrow is indeed a clock-out at 2:00
        assert evts[-1] == ClockEvent(dt.time(hour=2), ClockAction.CLOCK_OUT)
        # Check that warning has been set
        assert tracker.get_attendance_error(tomorrow) > 0
