#!/usr/bin/env python3
"""
File: time_tracker_model_test.py
Author: Bastian Cerf
Date: 13/04/2025
Description: 
    Unit test the TimeTrackerModel to validate expected behaviors.
Usage:
    Use pytest to execute the tests. You can run it by executing the command below in the TeamBridge/ folder.
    - pytest

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

import pytest
from time_tracker_model import *
from spreadsheets_repository import SpreadsheetsRepository
from spreadsheet_time_tracker import SpreadsheetTimeTracker
from typing import Generator
import logging

################################################
#               Tests constants                #
################################################

LOGGER = logging.getLogger(__name__)

TEST_EMPLOYEE_ID = "unit-test"
TEST_DATE = dt.date(year=2025, month=3, day=10) # 10 March 2025 is a monday

################################################
#                   Fixtures                   #
################################################

################################################
#                  Unit tests                  #
################################################

def test_clock_action(time_tracker_model):
    """
    """
    # Subscribe to the message bus and put the messages in a queue
    messages: list[ModelMessage] = []
    time_tracker_model.get_message_bus().observe(lambda msg: messages.append(msg))
    time_tracker_model.get_message_bus().observe(lambda msg: LOGGER.info(f"Received message from model: {msg}"))
    # Wait for the task to finish
    def wait_result() -> ModelMessage:
        # Run the model until a message is posted or timed out
        timeout = time.time() + 10.0
        while len(messages) == 0:
            time_tracker_model.run()
            assert time.time() < timeout
            time.sleep(0.1)
        # Return the posted message
        return messages.pop()
    
    # Register a clock in at 8h12
    time_tracker_model.start_clock_action_task(TEST_EMPLOYEE_ID, 
                                               dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=8, minute=12)))
    # Wait until the task finishes
    msg = wait_result()
    # Assert expected message
    assert isinstance(msg, EmployeeEvent)
    assert msg.id == TEST_EMPLOYEE_ID
    assert msg.clock_evt.time == dt.time(hour=8, minute=12)
    assert msg.clock_evt.action == ClockAction.CLOCK_IN

    # Register a clock out at 10h12
    time_tracker_model.start_clock_action_task(TEST_EMPLOYEE_ID, 
                                               dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=10, minute=12)))
    # Wait until the task finishes
    msg = wait_result()
    # Assert expected message
    assert isinstance(msg, EmployeeEvent)
    assert msg.id == TEST_EMPLOYEE_ID
    assert msg.clock_evt.time == dt.time(hour=10, minute=12)
    assert msg.clock_evt.action == ClockAction.CLOCK_OUT

    # Consultation of employee's data
    time_tracker_model.start_consultation_task(TEST_EMPLOYEE_ID, 
                                               dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=10, minute=12)))
    # Wait until the task finishes
    msg = wait_result()
    # Assert expected message
    assert isinstance(msg, EmployeeData)
    assert msg.id == TEST_EMPLOYEE_ID
    assert msg.daily_worked_time == dt.timedelta(hours=2)
