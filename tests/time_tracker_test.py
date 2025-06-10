#!/usr/bin/env python3
"""
File: time_tracker_test.py
Author: Bastian Cerf
Date: 18/05/2025
Description:
    Unit tests for the time tracker module.

    These tests are implementation-agnostic and follow a black-box testing
    approach. For instance, values are written and read exclusively through
    the time tracker interface to verify correctness—without accessing the
    underlying storage directly (e.g., spreadsheets, databases, etc.). This
    strategy ensures that all time tracker implementations can be tested
    uniformly, focusing on their observable behavior.

    The tests assume that a known dataset is already present in the data
    storage system. To inspect the test data, it is recommended to open the
    corresponding unit test spreadsheet file.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import pytest
from pytest import approx  # pyright: ignore[reportUnknownVariableType]
from pytest import FixtureRequest
import logging
from dataclasses import dataclass
import datetime as dt
from typing import Optional

# Internal libraries
from .test_constants import *
from core.time_tracker_factory import TimeTrackerFactory
from core.time_tracker import ClockEvent, ClockAction

# Time tracker factories
from core.spreadsheets.sheet_time_tracker_factory import *

LOGGER = logging.getLogger(__name__)

########################################################################
#                              Fixtures                                #
########################################################################


@pytest.fixture(
    params=[
        # New factories can be added here
        SheetTimeTrackerFactory(TEST_ASSETS_DST_FOLDER)
    ]
)
def factory(request: FixtureRequest, arrange_assets: None) -> TimeTrackerFactory:
    """
    Fixture that provides a TimeTrackerFactory instance for use in tests.

    Each test using this fixture will be executed once per factory
    specified in the `params` list. This allows testing with different
    factory implementations.

    Returns:
        TimeTrackerFactory: An instance of a time tracker factory.
    """
    return request.param


########################################################################
#                         Dataset information                          #
########################################################################


@dataclass
class TestCaseData:
    """Structure for a test case data"""

    datetime: dt.datetime

    date_evt_times: list[dt.time]
    date_schedule: dt.timedelta
    date_worked: dt.timedelta
    date_balance: dt.timedelta
    date_vacation: float

    month_schedule: dt.timedelta
    month_worked: dt.timedelta
    month_balance: dt.timedelta
    month_vacation: float

    ytd_balance: dt.timedelta
    yty_balance: dt.timedelta
    year_vacation: float
    rem_vacation: float


@pytest.fixture
def testcase(request: FixtureRequest) -> TestCaseData:
    name = request.param
    return request.getfixturevalue(name)


@pytest.fixture
def tc_first_work_day() -> TestCaseData:
    """Test case data for the first work day of the year."""
    return TestCaseData(
        datetime=dt.datetime(year=2025, month=1, day=1, hour=18),
        date_evt_times=[
            dt.time(hour=7, minute=45),
            dt.time(hour=9, minute=50),
            dt.time(hour=10, minute=0),
            dt.time(hour=12, minute=30),
            dt.time(hour=13, minute=15),
            dt.time(hour=17, minute=10),
        ],
        date_schedule=dt.timedelta(hours=8, minutes=17),
        date_worked=dt.timedelta(hours=8, minutes=30),
        date_balance=dt.timedelta(minutes=13),
        date_vacation=0.0,
        # Scheduled, vacation and worked time doesn't depend on current date
        month_schedule=dt.timedelta(hours=182, minutes=14),
        month_worked=dt.timedelta(hours=180),
        month_vacation=1.5,
        # Balance does: since date is 01.01.25, month and date balances are equal
        month_balance=dt.timedelta(minutes=13),
        # Initial balance is 2 hours, add the 13 minutes of the date
        ytd_balance=dt.timedelta(hours=2, minutes=13),
        yty_balance=dt.timedelta(hours=2),
        # Year / remaining vacation doesn't depend on current date
        year_vacation=2.0,  # Planned
        rem_vacation=20,    # Remaining
    )


@pytest.fixture
def tc_clocked_in():
    """Test case data for an ongoing day where the employee is working."""
    return TestCaseData(
        datetime=dt.datetime(year=2025, month=2, day=11, hour=11),
        date_evt_times=[
            dt.time(hour=7, minute=45),
            dt.time(hour=9, minute=50),
            dt.time(hour=10, minute=0),
        ],
        date_schedule=dt.timedelta(hours=8, minutes=17),
        date_worked=dt.timedelta(hours=3, minutes=5),
        date_balance=dt.timedelta(hours=-5, minutes=-12),
        date_vacation=0.0,
        # Scheduled, vacation and worked time doesn't depend on current date
        month_schedule=dt.timedelta(hours=149, minutes=6),
        month_worked=dt.timedelta(hours=55, minutes=55),
        month_vacation=0.5,
        month_balance=dt.timedelta(hours=-2, minutes=-4),
        ytd_balance=dt.timedelta(hours=-2, minutes=17),
        yty_balance=dt.timedelta(hours=2, minutes=55),
        # Year / remaining vacation doesn't depend on current date
        year_vacation=2.0,
        rem_vacation=20,
    )


# @pytest.fixture
# def tc_midnight_rollover():
#     """Test case data for a day where an employee works at midnight."""
#     return TestCaseData()


# @pytest.fixture
# def date_until_midnight() -> DateData:
#     """Get the date data for a day with midnight rollover.

#     Clock events for the date:
#         07:45	09:50	10:00	12:30	13:15	15:00	22:00	00:00
#     Day schedule / Worked time / Balance / Vacation:
#         8:17          8:20        0:03       0.0
#     """
#     return DateData(
#         datetime=dt.datetime(year=2025, month=1, day=7, hour=23, minute=59),
#         evt_times=[
#             dt.time(hour=7, minute=45),
#             dt.time(hour=9, minute=50),
#             dt.time(hour=10, minute=0),
#             dt.time(hour=12, minute=30),
#             dt.time(hour=13, minute=15),
#             dt.time(hour=15, minute=0),
#             dt.time(hour=22, minute=0),
#             dt.time(hour=0, minute=0),
#         ],
#         schedule=dt.timedelta(hours=8, minutes=17),
#         worked=dt.timedelta(hours=8, minutes=20),
#         balance=dt.timedelta(minutes=3),
#         vacation=0.0,
#     )

########################################################################
#                            Unit tests                                #
########################################################################


def test_open(factory: TimeTrackerFactory, tc_first_work_day: TestCaseData):
    """
    Open the time tracker using a context manager and check that expected
    attributes exist.
    """
    with factory.create(TEST_EMPLOYEE_ID, tc_first_work_day.datetime) as tracker:
        assert tracker.employee_id == TEST_EMPLOYEE_ID
        assert tracker.name == TEST_EMPLOYEE_NAME       
        assert tracker.firstname == TEST_EMPLOYEE_FIRSTNAME


def test_basic_info(factory: TimeTrackerFactory, tc_first_work_day: TestCaseData):
    """
    Open the time tracker and check basic employee information.
    """
    with factory.create(TEST_EMPLOYEE_ID, tc_first_work_day.datetime) as tracker:
        assert tracker.tracked_year == tc_first_work_day.datetime.year
        assert tracker.opening_day_schedule == dt.timedelta(hours=8, minutes=17)
        assert tracker.opening_vacation_days == 22
        assert tracker.opening_balance == dt.timedelta(hours=2)


def test_analyze(factory: TimeTrackerFactory, tc_first_work_day: TestCaseData):
    """
    Verifies that the data analysis allows to access the reading
    functions.
    """
    with factory.create(TEST_EMPLOYEE_ID, tc_first_work_day.datetime) as tracker:
        assert tracker.analyzed is False
        tracker.analyze(tc_first_work_day.datetime)
        assert tracker.analyzed is True


@pytest.mark.parametrize(
    "testcase",
    ["tc_first_work_day", "tc_clocked_in"],
    indirect=True,
)
def test_get_clock_events(factory: TimeTrackerFactory, testcase: TestCaseData):
    """
    Get the clock events for the date and check they are the same as the
    expected ones.
    """
    with factory.create(TEST_EMPLOYEE_ID, testcase.datetime) as tracker:
        evt_times = [evt.time if evt else None for evt in tracker.get_clocks(testcase.datetime)]
        assert evt_times == testcase.date_evt_times


def test_is_clocked_in(factory: TimeTrackerFactory, tc_clocked_in: TestCaseData, tc_first_work_day: TestCaseData):
    """
    Open the time tracker at a date that is still in progress and verify
    that the employee is clocked in. Additionally, check that the
    employee is clocked out on a past day.
    """
    with factory.create(TEST_EMPLOYEE_ID, tc_clocked_in.datetime) as tracker:
        assert tracker.is_clocked_in(tc_clocked_in.datetime)
        assert not tracker.is_clocked_in(tc_first_work_day.datetime)


@pytest.mark.parametrize(
    "testcase",
    ["tc_first_work_day", "tc_clocked_in"],
    indirect=True,
)
def test_read_day_data(factory: TimeTrackerFactory, testcase: TestCaseData):
    """
    Analyze the time tracker for the given date and read the day
    information. Verifies the read values are equal to the expected ones
    from the dataset.
    """
    with factory.create(TEST_EMPLOYEE_ID, testcase.datetime) as tracker:
        tracker.analyze(testcase.datetime)

        day_schedule = tracker.read_day_schedule(testcase.datetime)
        day_balance = tracker.read_day_balance(testcase.datetime)
        day_worked_time = tracker.read_day_worked_time(testcase.datetime)
        day_vacation = tracker.get_vacation(testcase.datetime)

        assert day_schedule == testcase.date_schedule
        assert day_balance == testcase.date_balance
        assert day_worked_time == testcase.date_worked
        assert day_vacation == approx(testcase.date_vacation)

        # Check that the relation between scheduled time, worked time and
        # balance is respected
        assert day_schedule + day_balance == day_worked_time


@pytest.mark.parametrize(
    "testcase",
    ["tc_first_work_day", "tc_clocked_in"],
    indirect=True,
)
def test_read_month_data(factory: TimeTrackerFactory, testcase: TestCaseData):
    """
    Analyze the time tracker for the given date and read the month
    information. Verifies the read values are equal to the expected ones
    from the dataset.
    """
    with factory.create(TEST_EMPLOYEE_ID, testcase.datetime) as tracker:
        tracker.analyze(testcase.datetime)

        month_schedule = tracker.read_month_schedule(testcase.datetime)
        month_balance = tracker.read_month_balance(testcase.datetime)
        month_worked_time = tracker.read_month_worked_time(testcase.datetime)
        month_vacation = tracker.read_month_vacation(testcase.datetime)

        assert month_schedule == testcase.month_schedule
        assert month_balance == testcase.month_balance
        assert month_worked_time == testcase.month_worked
        assert month_vacation == approx(testcase.month_vacation)

        # Check that the relation between scheduled time, worked time and
        # balance is respected
        assert month_schedule + month_balance == month_worked_time


@pytest.mark.parametrize(
    "testcase",
    ["tc_first_work_day", "tc_clocked_in"],
    indirect=True,
)
def test_year_to_date_balance(factory: TimeTrackerFactory, testcase: TestCaseData):
    """
    Analyze the time tracker for the given date and read the year-to-
    date and year-to-yesterday balances. Verifies that they are equal
    to the expected ones.
    """
    with factory.create(TEST_EMPLOYEE_ID, testcase.datetime) as tracker:
        tracker.analyze(testcase.datetime)
        assert tracker.read_year_to_date_balance() == testcase.ytd_balance
        assert tracker.read_year_to_yesterday_balance() == testcase.yty_balance


@pytest.mark.parametrize(
    "testcase",
    ["tc_first_work_day", "tc_clocked_in"],
    indirect=True,
)
def test_year_vacation(factory: TimeTrackerFactory, testcase: TestCaseData):
    """
    Analyze the time tracker for the given date and read the total
    year vacation and the remaining vacation. Verifies that they are
    equal to the expected ones.
    """
    with factory.create(TEST_EMPLOYEE_ID, testcase.datetime) as tracker:
        tracker.analyze(testcase.datetime)

        year_vacation = tracker.read_year_vacation()
        rem_vacation = tracker.read_remaining_vacation()

        assert year_vacation == approx(testcase.year_vacation)
        assert rem_vacation == approx(testcase.rem_vacation)

        # Check that the relation between total vacation, remaining vacation
        # and initial vacation is respected
        assert year_vacation + rem_vacation == approx(tracker.opening_vacation_days)


def test_register_evt(factory: TimeTrackerFactory, tc_clocked_in: TestCaseData):
    """
    Register a clock-out event to finish the work day. Verify it has been
    registered by comparing with the last clock event of the day.
    """
    event = ClockEvent(dt.time(hour=12, minute=40), ClockAction.CLOCK_OUT)

    with factory.create(TEST_EMPLOYEE_ID, tc_clocked_in.datetime) as tracker:
        tracker.register_clock(tc_clocked_in.datetime, event)
        assert tracker.get_clocks(tc_clocked_in.datetime)[-1] == event


def test_write_evts(factory: TimeTrackerFactory, tc_first_work_day: TestCaseData):
    """
    Write a set of clock events for the day and verify they have been
    registered.
    """
    evts: list[Optional[ClockEvent]] = [
        None,  # Missing first event
        ClockEvent(dt.time(hour=10), ClockAction.CLOCK_OUT),
        ClockEvent(dt.time(hour=10, minute=15), ClockAction.CLOCK_IN),
        ClockEvent(dt.time(hour=13), ClockAction.CLOCK_OUT),
        ClockEvent(dt.time(hour=14), ClockAction.CLOCK_IN),
        ClockEvent(dt.time(hour=16), ClockAction.CLOCK_OUT),
    ]

    with factory.create(TEST_EMPLOYEE_ID, tc_first_work_day.datetime) as tracker:
        tracker.write_clocks(tc_first_work_day.datetime, evts)
        assert tracker.get_clocks(tc_first_work_day.datetime) == evts


def test_save(factory: TimeTrackerFactory, tc_first_work_day: TestCaseData):
    """
    Register a new clock event for a date, save and close
    the time tracker. Reopen it and verify the clock event still exists.
    """
    event = ClockEvent(dt.time(hour=18, minute=40), ClockAction.CLOCK_IN)

    with factory.create(TEST_EMPLOYEE_ID, tc_first_work_day.datetime) as tracker:
        tracker.register_clock(tc_first_work_day.datetime, event)
        tracker.save()

    with factory.create(TEST_EMPLOYEE_ID, tc_first_work_day.datetime) as tracker:
        assert tracker.get_clocks(tc_first_work_day.datetime)[-1] == event


# TODO: integration tests / edge case tests


# @pytest.mark.skip(reason="Not implemented")
# def test_clock_event_register_and_evaluate(factory: TimeTrackerFactory):
#     with factory.create(TEST_EMPLOYEE_ID, None) as tracker:
#         event = ClockEvent(time=dt.time(9, 0), action=ClockAction.CLOCK_IN)
#         tracker.register_clock(event)
#         tracker.evaluate()
#         assert tracker.readable
#         events = tracker.get_clock_events()
#         assert events[0] == event


# @pytest.mark.skip(reason="Not implemented")
# def test_day_schedule_and_balance(factory: TimeTrackerFactory):
#     with factory.create(TEST_EMPLOYEE_ID, None) as tracker:
#         tracker.evaluate()
#         schedule = tracker.read_day_schedule()
#         worked = tracker.read_day_worked_time()
#         balance = tracker.read_day_balance()
#         assert isinstance(schedule, dt.timedelta)
#         assert isinstance(worked, dt.timedelta)
#         assert isinstance(balance, dt.timedelta)


# @pytest.mark.skip(reason="Not implemented")
# def test_day_vacation(factory: TimeTrackerFactory):
#     with factory.create(TEST_EMPLOYEE_ID, None) as tracker:
#         tracker.evaluate()
#         vacation = tracker.read_day_vacation()
#         assert 0.0 <= vacation <= 1.0


# @pytest.mark.skip(reason="Not implemented")
# def test_year_to_yesterday_balance(factory: TimeTrackerFactory):
#     with factory.create(TEST_EMPLOYEE_ID, None) as tracker:
#         tracker.evaluate()
#         ytd = tracker.read_year_to_date_balance()
#         yty = tracker.read_year_to_yesterday_balance()
#         assert ytd >= yty


# @pytest.mark.skip(reason="Not implemented")
# def test_attendance_validator_basic(factory: TimeTrackerFactory):
#     with factory.create(TEST_EMPLOYEE_ID, None) as tracker:
#         tracker.evaluate()
#         validator = AttendanceValidator(tracker)
#         err = validator.check_date(None)
#         assert err in (None, CLOCK_EVENT_MISSING, CLOCK_EVENTS_UNORDERED)


# --- Edge case stubs below ---


@pytest.mark.skip(reason="Not implemented")
def test_clock_event_out_of_order(factory: TimeTrackerFactory):
    # Expect: validator detects unordered events
    pass


@pytest.mark.skip(reason="Not implemented")
def test_missing_clock_out(factory: TimeTrackerFactory):
    # Expect: validator detects missing clock-out
    pass


@pytest.mark.skip(reason="Not implemented")
def test_register_more_than_max_events(factory: TimeTrackerFactory):
    # Expect: TimeTrackerWriteException raised
    pass


@pytest.mark.skip(reason="Not implemented")
def test_access_read_methods_before_evaluation(factory: TimeTrackerFactory):
    # Expect: TimeTrackerReadException raised
    pass


@pytest.mark.skip(reason="Not implemented")
def test_set_data_datetime_invalidates_readable(factory: TimeTrackerFactory):
    # Expect: readable becomes False after data_datetime is changed
    pass


@pytest.mark.skip(reason="Not implemented")
def test_vacation_calculation_with_future_dates(factory: TimeTrackerFactory):
    # Ensure vacation read logic includes future dates correctly
    pass


@pytest.mark.skip(reason="Not implemented")
def test_context_manager_closes_tracker(factory: TimeTrackerFactory):
    # Expect: no exception raised when closing
    pass
