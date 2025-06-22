#!/usr/bin/env python3
"""
File: teambridge_model_test.py
Author: Bastian Cerf
Date: 13/04/2025
Description:
    Unit test the TeamBridgeScheduler to validate expected behaviors.
Usage:
    Use pytest to execute the tests. You can run it by executing the command below in the TeamBridge/ folder.
    - pytest

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

from model.teambridge_scheduler import *
import time
import logging

################################################
#               Tests constants                #
################################################

logger = logging.getLogger(__name__)

TEST_EMPLOYEE_ID = "unit-test"
TEST_DATE = dt.date(year=2025, month=3, day=10)  # 10 March 2025 is a monday

################################################
#                   Fixtures                   #
################################################

################################################
#                  Unit tests                  #
################################################


def test_clock_action(teambridge_model):
    """ """

    # Wait for the task to finish
    def wait_result(handle: int) -> IModelMessage:
        # Poll the model until a message is posted or timed out
        timeout = time.time() + 10.0
        while not teambridge_model.available(handle):
            assert teambridge_model.get_result(handle) is None
            assert time.time() < timeout
            time.sleep(0.1)
        # Return the task message
        message = teambridge_model.get_result(handle)
        logger.info(f"Got model message: {message}")
        return message

    # Register a clock in at 8h12
    handle = teambridge_model.start_clock_action_task(
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
    handle = teambridge_model.start_clock_action_task(
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
    handle = teambridge_model.start_consultation_task(
        TEST_EMPLOYEE_ID,
        dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=10, minute=12)),
    )
    # Wait until the task finishes
    msg = wait_result(handle)
    # Assert expected message
    assert isinstance(msg, EmployeeData)
    assert msg.id == TEST_EMPLOYEE_ID
    assert msg.daily_worked_time == dt.timedelta(hours=2)
