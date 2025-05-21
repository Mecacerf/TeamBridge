#!/usr/bin/env python3
"""
File: time_tracker_test.py
Author: Bastian Cerf
Date: 18/05/2025
Description:
    Unit tests for the time tracker module.

    These tests are implementation-agnostic and follow a black-box testing approach.
    For instance, values are written and read exclusively through the time tracker
    interface to verify correctness—without accessing the underlying storage directly
    (e.g., spreadsheets, databases, etc.). This strategy ensures that all time tracker
    implementations can be tested uniformly, focusing on their observable behavior.

    The tests assume that a known dataset is already present in the data storage
    system. To inspect the test data, it is recommended to open the corresponding
    unit test spreadsheet file.

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

# Time tracker factories
from core.spreadsheets.sheet_time_tracker_factory import *

LOGGER = logging.getLogger(__name__)

# Test constants
TEST_DATE = dt.date(year=2025, month=2, day=11)
TEST_TIME = dt.time(hour=10, minute=45)

@pytest.fixture(params=[
    SheetTimeTrackerFactory(TEST_ASSETS_DST_FOLDER)
])
def factory(request, arrange_assets) -> TimeTrackerFactory:
    """
    Fixture that provides a TimeTrackerFactory instance for use in tests.

    Each test using this fixture will be executed once per factory specified
    in the `params` list. This allows testing with different factory implementations.

    Returns:
        TimeTrackerFactory: An instance of a time tracker factory.
    """
    return request.param

def test_open(factory):
    """
    Open the time tracker using a context manager and check that expected
    attributes exist.
    """
    with factory.create(TEST_EMPLOYEE_ID, TEST_DATE) as emp:
        assert emp.employee_id == TEST_EMPLOYEE_ID
        assert emp.current_date == TEST_DATE

def test_base_info(factory):
    """
    Open the time tracker and check base information such as the name, firstname and year the
    data belongs to.
    """ 
    with factory.create(TEST_EMPLOYEE_ID) as emp:
        assert emp.firstname == "Meca"
        assert emp.name == "Cerf"
        assert emp.data_year == TEST_DATE.year

def test_date_context(factory):
    """
    Open a time tracker and use a context manager to temporarily change the current date.
    Make sure the first date is restored once the context manager is closed.
    """
    with factory.create(TEST_EMPLOYEE_ID, TEST_DATE) as emp:

        work_date = TEST_DATE + dt.timedelta(days=1)
        with emp.date_context(work_date):
            assert emp.current_date == work_date
        assert emp.current_date == TEST_DATE










    # with factory.create(TEST_EMPLOYEE_ID) as emp:
    #     emp.evaluate()

    #     def format_dt(td: dt.timedelta):
    #         # Ensure the information is available
    #         if not isinstance(td, dt.timedelta):
    #             return "indisponible"
    #         # Available, format time
    #         total_minutes = int(td.total_seconds() // 60)
    #         sign = "-" if total_minutes < 0 else ""
    #         abs_minutes = abs(total_minutes)
    #         hours, minutes = divmod(abs_minutes, 60)
    #         return f"{sign}{hours:02}:{minutes:02}"

    #     emp.current_date = dt.date(year=emp.data_year, month=2, day=11)
    #     LOGGER.info(f"Balance {format_dt(emp.read_year_balance())} year {format_dt(emp.read_year_balance_until_yesterday())}")

    # with factory.create(TEST_EMPLOYEE_ID) as employee:
    #     LOGGER.info(f"{employee.firstname} {employee.name} {employee.data_year}")
    #     employee.register_clock(ClockEvent(dt.time(hour=8), ClockAction.CLOCK_OUT))
    #     employee.register_clock(ClockEvent(dt.time(hour=10), ClockAction.CLOCK_OUT))
    #     LOGGER.info(f"Clock events: {", ".join([evt for evt in map(str, employee.clock_events)])}")
    #     LOGGER.info(f"readable {employee.readable}")
    #     employee.evaluate()
    #     LOGGER.info(f"readable {employee.readable}")
    #     LOGGER.info(f"{employee.read_remaining_vacation()}")
    #     employee.register_clock(ClockEvent(dt.time(hour=6), ClockAction.CLOCK_IN))
    #     employee.register_clock(ClockEvent(dt.time(hour=9), ClockAction.CLOCK_IN))
    #     employee.save()
    #     LOGGER.info(f"readable {employee.readable}")

    # with factory.create(TEST_EMPLOYEE_ID) as employee:
    #     LOGGER.info(f"Clock events: {", ".join([evt for evt in map(str, employee.clock_events)])}")
    #     LOGGER.info(f"{employee.check_date_error()}")

    LOGGER.info(f"List {factory.list_employee_ids()}")
