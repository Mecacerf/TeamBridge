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

TEST_DATE = dt.date(year=2025, month=3, day=10)  # 10 March 2025 is a monday

########################################################################
#                            Unit tests                                #
########################################################################


def test_clock_action(scheduler: TeamBridgeScheduler):
    """
    Clock in and out the test employee, check expected messages are
    received. Finally perform a consultation.
    """

    # Wait for the task to finish
    def wait_result(handle: int) -> Optional[IModelMessage]:
        # Poll the model until a message is posted or timed out
        timeout = time.time() + 10.0
        while not scheduler.available(handle):
            assert scheduler.get_result(handle) is None
            assert time.time() < timeout
            time.sleep(0.1)
        # Return the task message
        message = scheduler.get_result(handle)
        logger.info(f"Got model message: {message}")
        return message

    # Register a clock in at 8h12
    handle = scheduler.start_clock_action_task(
        TEST_EMPLOYEE_ID,
        dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=8, minute=12)),
    )
    # Wait until the task finishes
    msg = wait_result(handle)
    # Assert expected message
    assert isinstance(msg, EmployeeEvent)
    assert msg.id == TEST_EMPLOYEE_ID
    assert msg.clock_evt.time == dt.time(hour=8, minute=12)
    assert msg.clock_evt.action == ClockAction.CLOCK_IN

    # Register a clock out at 10h12
    handle = scheduler.start_clock_action_task(
        TEST_EMPLOYEE_ID,
        dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=10, minute=12)),
    )
    # Wait until the task finishes
    msg = wait_result(handle)
    # Assert expected message
    assert isinstance(msg, EmployeeEvent)
    assert msg.id == TEST_EMPLOYEE_ID
    assert msg.clock_evt.time == dt.time(hour=10, minute=12)
    assert msg.clock_evt.action == ClockAction.CLOCK_OUT

    # Consultation of employee's data
    handle = scheduler.start_consultation_task(
        TEST_EMPLOYEE_ID,
        dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=10, minute=12)),
    )
    # Wait until the task finishes
    msg = wait_result(handle)
    # Assert expected message
    assert isinstance(msg, EmployeeData)
    assert msg.id == TEST_EMPLOYEE_ID
    assert msg.daily_worked_time == dt.timedelta(hours=2)
