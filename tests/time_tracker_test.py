#!/usr/bin/env python3
"""
File: time_tracker_test.py
Author: Bastian Cerf
Date: 18/05/2025
Description: 
    Unit test of the time tracker module.
    TODO: polish

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import pytest
import logging

# Internal libraries
from .test_constants import *
from core.time_tracker_factory import *
from core.time_tracker import *

from core.spreadsheets.sheet_time_tracker_factory import *

LOGGER = logging.getLogger(__name__)

@pytest.fixture(params=[
    SheetTimeTrackerFactory(TEST_ASSETS_DST_FOLDER)
])
def factory(request, arrange_assets) -> TimeTrackerFactory:
    """
    """
    return request.param

def test_open_time_tracker(factory):
    """
    """
    with factory.create(TEST_EMPLOYEE_ID) as employee:
        LOGGER.info(f"{employee.firstname} {employee.name} {employee.data_year}")
        employee.register_clock(ClockEvent(dt.time(hour=8), ClockAction.CLOCK_OUT))
        employee.register_clock(ClockEvent(dt.time(hour=7), ClockAction.CLOCK_OUT))
        LOGGER.info(f"{employee.clock_events}")
        LOGGER.info(f"readable {employee.readable}")
        employee.evaluate()
        LOGGER.info(f"readable {employee.readable}")
        LOGGER.info(f"{employee.read_remaining_vacation()}")
        employee.save()

    LOGGER.info(f"List {factory.list_employee_ids()}")
