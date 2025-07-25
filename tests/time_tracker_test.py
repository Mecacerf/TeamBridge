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
from core.time_tracker import (
    ClockEvent,
    ClockAction,
    TimeTrackerAnalysisException,
    TimeTrackerWriteException,
    TimeTrackerReadException,
    TimeTrackerValueException,
    TimeTrackerSaveException,
    TimeTrackerDateException,
)

# Time tracker factories
from core.spreadsheets.sheet_time_tracker_factory import *

logger = logging.getLogger(__name__)

########################################################################
#                              Fixtures                                #
########################################################################


@pytest.fixture(
    params=[
        # New factories can be added here as lambdas
        lambda: SheetTimeTrackerFactory(TEST_REPOSITORY_ROOT)
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
    return request.param()


########################################################################
#                         Dataset information                          #
########################################################################


@dataclass
class CaseData:
    """
    Structure for a test case data. The structure holds the test date
    and time and the expected values for that datetime.
    """

    datetime: dt.datetime

    date_events: list[ClockEvent]
    date_schedule: dt.timedelta
    date_worked: dt.timedelta
    date_balance: dt.timedelta
    date_vacation: float
    date_absence: float
    date_error_soft: int
    date_error_sys: int

    month_schedule: dt.timedelta
    month_daily_schedule: dt.timedelta
    month_worked: dt.timedelta
    month_balance: dt.timedelta
    month_vacation: float

    ytd_balance: dt.timedelta
    yty_balance: dt.timedelta
    year_vacation: float
    rem_vacation: float


@pytest.fixture
def testcase(request: FixtureRequest) -> CaseData:
    """Get a test case data by its fixture name."""
    name = request.param
    return request.getfixturevalue(name)


@pytest.fixture
def tc_first_work_day() -> CaseData:
    """Test case data for the first work day of the year (1st January 2025)."""
    return CaseData(
        datetime=dt.datetime(year=2025, month=1, day=1, hour=18),
        date_events=[
            ClockEvent(dt.time(hour=7, minute=45), ClockAction.CLOCK_IN),
            ClockEvent(dt.time(hour=9, minute=50), ClockAction.CLOCK_OUT),
            ClockEvent(dt.time(hour=10, minute=0), ClockAction.CLOCK_IN),
            ClockEvent(dt.time(hour=12, minute=30), ClockAction.CLOCK_OUT),
            ClockEvent(dt.time(hour=13, minute=15), ClockAction.CLOCK_IN),
            ClockEvent(dt.time(hour=17, minute=10), ClockAction.CLOCK_OUT),
        ],
        date_schedule=dt.timedelta(hours=8, minutes=17),
        date_worked=dt.timedelta(hours=8, minutes=30),
        date_balance=dt.timedelta(minutes=13),
        date_vacation=0.0,
        date_absence=0.0,
        date_error_soft=0,
        date_error_sys=0,
        # Scheduled time, worked time and vacation for the month don't depend
        # on the date. They are always the sum for the whole month, even though
        # the test datetime is for the 1st.
        month_schedule=dt.timedelta(hours=169, minutes=48, seconds=30),
        month_worked=dt.timedelta(hours=167, minutes=35),
        month_daily_schedule=dt.timedelta(hours=8, minutes=17),
        month_vacation=1.5,
        # Balance does depend on the test datetime. It is the same as the day
        # balance since the test date is the 01.01.25.
        month_balance=dt.timedelta(minutes=13),
        # Opening balance is 2 hours, add the 13 minutes of the date
        ytd_balance=dt.timedelta(hours=2, minutes=13),
        yty_balance=dt.timedelta(hours=2),
        # Year / remaining vacation doesn't depend on current date
        year_vacation=2.0,  # Planned
        rem_vacation=20,  # Remaining
    )


@pytest.fixture
def tc_month_closing():
    """
    Test case data for the 31.01.25 after the last employee's clock out
    event.
    """
    return CaseData(
        datetime=dt.datetime(year=2025, month=1, day=31, hour=18),
        date_events=[
            ClockEvent(dt.time(hour=7, minute=45), ClockAction.CLOCK_IN),
            ClockEvent(dt.time(hour=9, minute=50), ClockAction.CLOCK_OUT),
            ClockEvent(dt.time(hour=10, minute=0), ClockAction.CLOCK_IN),
            ClockEvent(dt.time(hour=12, minute=30), ClockAction.CLOCK_OUT),
            ClockEvent(dt.time(hour=13, minute=15), ClockAction.CLOCK_IN),
            ClockEvent(dt.time(hour=17, minute=40), ClockAction.CLOCK_OUT),
        ],
        date_schedule=dt.timedelta(hours=8, minutes=17),
        date_worked=dt.timedelta(hours=9),
        date_balance=dt.timedelta(minutes=43),
        date_vacation=0.0,
        date_absence=0.0,
        date_error_soft=0,
        date_error_sys=0,
        # Scheduled time, worked time and vacation for the month don't depend
        # on the date. They are always the sum for the whole month, even though
        # the test datetime is for the 1st.
        month_schedule=dt.timedelta(hours=169, minutes=48, seconds=30),
        month_worked=dt.timedelta(hours=167, minutes=35),
        month_daily_schedule=dt.timedelta(hours=8, minutes=17),
        month_vacation=1.5,
        # Balance does depend on the test datetime but relates to the whole
        # month since the test date is the 31.01.25.
        month_balance=dt.timedelta(hours=-2, minutes=-13, seconds=-30),
        ytd_balance=dt.timedelta(minutes=-13, seconds=-30),
        yty_balance=dt.timedelta(minutes=-56, seconds=-30),
        # Year / remaining vacation doesn't depend on current date
        year_vacation=2.0,  # Planned
        rem_vacation=20,  # Remaining
    )


@pytest.fixture
def tc_clocked_in():
    """
    Test case data for an ongoing day where the employee is still
    working (clocked in). The test date and time is the 11.02.25 at 11h.
    No clock events exist in the dataset after this date.
    """
    return CaseData(
        datetime=dt.datetime(year=2025, month=2, day=11, hour=11),
        date_events=[
            ClockEvent(dt.time(hour=7, minute=45), ClockAction.CLOCK_IN),
            ClockEvent(dt.time(hour=9, minute=50), ClockAction.CLOCK_OUT),
            ClockEvent(dt.time(hour=10, minute=0), ClockAction.CLOCK_IN),
        ],
        date_schedule=dt.timedelta(hours=8, minutes=17),
        date_worked=dt.timedelta(hours=3, minutes=5),
        date_balance=dt.timedelta(hours=-5, minutes=-12),
        date_vacation=0.0,
        date_absence=0.0,
        date_error_soft=0,
        date_error_sys=0,
        # Scheduled, vacation and worked time doesn't depend on current date
        month_schedule=dt.timedelta(hours=161, minutes=31, seconds=30),
        month_worked=dt.timedelta(hours=55, minutes=55),
        month_daily_schedule=dt.timedelta(hours=8, minutes=17),
        month_vacation=0.5,
        # Month balance, year-to-date and year-to-yesterday depend on current date
        month_balance=dt.timedelta(hours=-2, minutes=-4),
        ytd_balance=dt.timedelta(hours=-2, minutes=-17, seconds=-30),
        yty_balance=dt.timedelta(hours=2, minutes=54, seconds=30),
        # Year / remaining vacation doesn't depend on current date
        year_vacation=2.0,
        rem_vacation=20,
    )


@pytest.fixture
def tc_work_at_midnight():
    """
    Test case data for a day where the employee worked after midnight.
    The system must automatically register a clock-out at 00:00 on the
    day and a clock-in at 00:00 on the next day. The clock-out is
    actually registered at 24:00:00, which is read as 00:00 by the
    time tracker.
    """
    return CaseData(
        # The time can be arbitrarily chosen, the last clock-out is registered
        datetime=dt.datetime(year=2025, month=1, day=7, hour=21),
        date_events=[
            ClockEvent(dt.time(hour=7, minute=45), ClockAction.CLOCK_IN),
            ClockEvent(dt.time(hour=9, minute=50), ClockAction.CLOCK_OUT),
            ClockEvent(dt.time(hour=10, minute=0), ClockAction.CLOCK_IN),
            ClockEvent(dt.time(hour=12, minute=30), ClockAction.CLOCK_OUT),
            ClockEvent(dt.time(hour=13, minute=15), ClockAction.CLOCK_IN),
            ClockEvent(dt.time(hour=15, minute=0), ClockAction.CLOCK_OUT),
            ClockEvent(dt.time(hour=22, minute=0), ClockAction.CLOCK_IN),
            ClockEvent.midnight_rollover(),
        ],
        date_schedule=dt.timedelta(hours=8, minutes=17),
        date_worked=dt.timedelta(hours=8, minutes=20),
        date_balance=dt.timedelta(hours=0, minutes=3),
        date_vacation=0.0,
        date_absence=0.0,
        date_error_soft=0,
        date_error_sys=0,
        # Scheduled, vacation and worked time doesn't depend on current date
        month_schedule=dt.timedelta(hours=169, minutes=48, seconds=30),
        month_worked=dt.timedelta(hours=167, minutes=35),
        month_daily_schedule=dt.timedelta(hours=8, minutes=17),
        month_vacation=1.5,
        # Month balance, year-to-date and year-to-yesterday depend on current date
        month_balance=dt.timedelta(hours=1, minutes=30),
        ytd_balance=dt.timedelta(hours=3, minutes=30),
        yty_balance=dt.timedelta(hours=3, minutes=27),
        # Year / remaining vacation doesn't depend on current date
        year_vacation=2.0,
        rem_vacation=20,
    )


@pytest.fixture
def tc_vacation():
    """
    Test case data for a day where the employee is on vacation.
    """
    return CaseData(
        # The time can be arbitrarily chosen, the last clock-out is registered
        datetime=dt.datetime(year=2025, month=1, day=23, hour=15),
        date_events=[],
        date_schedule=dt.timedelta(hours=0, minutes=0),
        date_worked=dt.timedelta(hours=0, minutes=0),
        date_balance=dt.timedelta(hours=0, minutes=0),
        date_vacation=1.0,
        date_absence=0.0,
        date_error_soft=0,
        date_error_sys=0,
        # Scheduled, vacation and worked time doesn't depend on current date
        month_schedule=dt.timedelta(hours=169, minutes=48, seconds=30),
        month_worked=dt.timedelta(hours=167, minutes=35),
        month_daily_schedule=dt.timedelta(hours=8, minutes=17),
        month_vacation=1.5,
        # Month balance, year-to-date and year-to-yesterday depend on current date
        month_balance=dt.timedelta(hours=-4, minutes=-32),
        ytd_balance=dt.timedelta(hours=-2, minutes=-32),
        yty_balance=dt.timedelta(hours=-2, minutes=-32),
        # Year / remaining vacation doesn't depend on current date
        year_vacation=2.0,
        rem_vacation=20,
    )


@pytest.fixture
def tc_sickness():
    """
    Test case data for a day where the employee is on paid absence.
    """
    return CaseData(
        # The time can be arbitrarily chosen, the last clock-out is registered
        datetime=dt.datetime(year=2025, month=1, day=30, hour=15),
        date_events=[],
        date_schedule=dt.timedelta(hours=0, minutes=0),
        date_worked=dt.timedelta(hours=0, minutes=0),
        date_balance=dt.timedelta(hours=0, minutes=0),
        date_vacation=0.0,
        date_absence=1.0,
        date_error_soft=0,
        date_error_sys=0,
        # Scheduled, vacation and worked time doesn't depend on current date
        month_schedule=dt.timedelta(hours=169, minutes=48, seconds=30),
        month_worked=dt.timedelta(hours=167, minutes=35),
        month_daily_schedule=dt.timedelta(hours=8, minutes=17),
        month_vacation=1.5,
        # Month balance, year-to-date and year-to-yesterday depend on current date
        month_balance=dt.timedelta(hours=-2, minutes=-56, seconds=-30),
        ytd_balance=dt.timedelta(hours=0, minutes=-56, seconds=-30),
        yty_balance=dt.timedelta(hours=0, minutes=-56, seconds=-30),
        # Year / remaining vacation doesn't depend on current date
        year_vacation=2.0,
        rem_vacation=20,
    )


########################################################################
#                            Unit tests                                #
########################################################################


def test_open(factory: TimeTrackerFactory, tc_first_work_day: CaseData):
    """
    Open the time tracker using a context manager and check that expected
    attributes exist.
    """
    with factory.create(TEST_EMPLOYEE_ID, tc_first_work_day.datetime) as tracker:
        assert tracker.employee_id == TEST_EMPLOYEE_ID
        assert tracker.name == TEST_EMPLOYEE_NAME
        assert tracker.firstname == TEST_EMPLOYEE_FIRSTNAME


def test_basic_info(factory: TimeTrackerFactory, tc_first_work_day: CaseData):
    """
    Open the time tracker and check basic employee information.
    """
    with factory.create(TEST_EMPLOYEE_ID, tc_first_work_day.datetime) as tracker:
        assert tracker.tracked_year == tc_first_work_day.datetime.year
        assert tracker.opening_day_schedule == dt.timedelta(hours=8, minutes=17)
        assert tracker.opening_vacation_days == 22
        assert tracker.opening_balance == dt.timedelta(hours=2)
        assert tracker.max_continuous_work_time == dt.timedelta(hours=6)


def test_analyze(factory: TimeTrackerFactory, tc_first_work_day: CaseData):
    """
    Verifies that the data analysis allows to access the reading
    functions.
    """
    with factory.create(TEST_EMPLOYEE_ID, tc_first_work_day.datetime) as tracker:
        assert tracker.analyzed is False
        tracker.analyze(tc_first_work_day.datetime)
        assert tracker.analyzed is True
        # This read doesn't raise
        tracker.read_day_worked_time(tc_first_work_day.datetime)


@pytest.mark.parametrize(
    "testcase",
    ["tc_first_work_day", "tc_clocked_in", "tc_month_closing", "tc_work_at_midnight"],
    indirect=True,
)
def test_get_clock_events(factory: TimeTrackerFactory, testcase: CaseData):
    """
    Get the clock events for the date and check they are the same as the
    expected ones.
    """
    with factory.create(TEST_EMPLOYEE_ID, testcase.datetime) as tracker:
        assert tracker.get_clocks(testcase.datetime) == testcase.date_events


def test_is_clocked_in(
    factory: TimeTrackerFactory,
    tc_clocked_in: CaseData,
    tc_first_work_day: CaseData,
):
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
    ["tc_first_work_day", "tc_vacation", "tc_sickness"],
    indirect=True,
)
def test_get_day_data(factory: TimeTrackerFactory, testcase: CaseData):
    """
    Get the date information that doesn't require an analysis and verify
    they have the expected values.
    """
    with factory.create(TEST_EMPLOYEE_ID, testcase.datetime) as tracker:
        day_absence = tracker.get_paid_absence(testcase.datetime)
        day_vacation = tracker.get_vacation(testcase.datetime)
        day_error_soft = tracker.get_attendance_error(testcase.datetime)
        day_error_desc = tracker.get_attendance_error_desc(testcase.date_error_soft)

        assert day_absence == approx(testcase.date_absence)
        assert day_vacation == approx(testcase.date_vacation)
        assert day_error_soft == testcase.date_error_soft
        assert day_error_desc == TEST_ERRORS_TABLE[testcase.date_error_soft]


@pytest.mark.parametrize(
    "testcase",
    ["tc_first_work_day"],  # Only one test case is enough
    indirect=True,
)
def test_get_day_data_readonly(factory: TimeTrackerFactory, testcase: CaseData):
    """
    Get the date information that doesn't require an analysis and verify
    they have the expected values. Open the tracker in read-only mode.
    """
    with factory.create(TEST_EMPLOYEE_ID, testcase.datetime, readonly=True) as tracker:
        day_absence = tracker.get_paid_absence(testcase.datetime)
        day_vacation = tracker.get_vacation(testcase.datetime)
        day_error_soft = tracker.get_attendance_error(testcase.datetime)
        day_error_desc = tracker.get_attendance_error_desc(testcase.date_error_soft)

        assert day_absence == approx(testcase.date_absence)
        assert day_vacation == approx(testcase.date_vacation)
        assert day_error_soft == testcase.date_error_soft
        assert day_error_desc == TEST_ERRORS_TABLE[testcase.date_error_soft]


@pytest.mark.parametrize(
    "testcase",
    [
        "tc_first_work_day",
        "tc_clocked_in",
        "tc_month_closing",
        "tc_work_at_midnight",
        "tc_vacation",
        "tc_sickness",
    ],
    indirect=True,
)
def test_read_day_data(factory: TimeTrackerFactory, testcase: CaseData):
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
        day_error_sys = tracker.read_day_attendance_error(testcase.datetime)

        assert day_schedule == testcase.date_schedule
        assert day_balance == testcase.date_balance
        assert day_worked_time == testcase.date_worked
        assert day_error_sys == testcase.date_error_sys

        # Check that the relation between scheduled time, worked time and
        # balance is respected
        assert day_schedule + day_balance == day_worked_time


@pytest.mark.parametrize(
    "testcase",
    [
        "tc_first_work_day",
        "tc_clocked_in",
        "tc_month_closing",
        "tc_work_at_midnight",
        "tc_vacation",
        "tc_sickness",
    ],
    indirect=True,
)
def test_read_month_data(factory: TimeTrackerFactory, testcase: CaseData):
    """
    Analyze the time tracker for the given date and read the month
    information. Verifies the read values are equal to the expected ones
    from the dataset.
    """
    with factory.create(TEST_EMPLOYEE_ID, testcase.datetime) as tracker:
        tracker.analyze(testcase.datetime)

        month_schedule = tracker.read_month_schedule(testcase.datetime)
        month_daily_schedule = tracker.read_month_expected_daily_schedule(
            testcase.datetime
        )
        month_balance = tracker.read_month_balance(testcase.datetime)
        month_worked_time = tracker.read_month_worked_time(testcase.datetime)
        month_vacation = tracker.read_month_vacation(testcase.datetime)

        assert month_schedule == testcase.month_schedule
        assert month_daily_schedule == testcase.month_daily_schedule
        assert month_balance == testcase.month_balance
        assert month_worked_time == testcase.month_worked
        assert month_vacation == approx(testcase.month_vacation)


@pytest.mark.parametrize(
    "testcase",
    [
        "tc_first_work_day",
        "tc_clocked_in",
        "tc_month_closing",
        "tc_work_at_midnight",
        "tc_vacation",
        "tc_sickness",
    ],
    indirect=True,
)
def test_year_to_date_balance(factory: TimeTrackerFactory, testcase: CaseData):
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
    [
        "tc_first_work_day",
        "tc_clocked_in",
        "tc_month_closing",
        "tc_work_at_midnight",
        "tc_vacation",
        "tc_sickness",
    ],
    indirect=True,
)
def test_year_vacation(factory: TimeTrackerFactory, testcase: CaseData):
    """
    Analyze the time tracker for the given date and read the total
    year vacation and the remaining vacation. Verifies that they are
    equal to the expected ones.
    """
    with factory.create(TEST_EMPLOYEE_ID, testcase.datetime) as tracker:
        tracker.analyze(testcase.datetime)

        year_vacation = tracker.read_year_vacation()
        rem_vacation = tracker.read_year_remaining_vacation()

        assert year_vacation == approx(testcase.year_vacation)
        assert rem_vacation == approx(testcase.rem_vacation)

        # Check that the relation between total vacation, remaining vacation
        # and initial vacation is respected
        assert year_vacation + rem_vacation == approx(tracker.opening_vacation_days)


def test_register_evt(factory: TimeTrackerFactory, tc_clocked_in: CaseData):
    """
    Register a clock-out event to finish the work day. Verify it has been
    registered by comparing with the last clock event of the day.
    """
    event = ClockEvent(dt.time(hour=12, minute=40), ClockAction.CLOCK_OUT)

    with factory.create(TEST_EMPLOYEE_ID, tc_clocked_in.datetime) as tracker:
        tracker.register_clock(tc_clocked_in.datetime, event)
        assert tracker.get_clocks(tc_clocked_in.datetime)[-1] == event
        tracker.save()  # Just to see the test result in the test cache


def test_write_evts(factory: TimeTrackerFactory, tc_first_work_day: CaseData):
    """
    Write a set of clock events for the day and verify they have been
    registered.
    """
    evts: list[Optional[ClockEvent]] = [
        None,  # Missing first event
        ClockEvent(dt.time(hour=10, minute=15), ClockAction.CLOCK_OUT),
        ClockEvent(dt.time(hour=22, minute=18), ClockAction.CLOCK_IN),
        ClockEvent.midnight_rollover(),  # Still working at midnight
    ]
    # Note that evts is intentionally smaller than the existing events. It
    # allows to check that write_clocks() correctly overrides all existing
    # entries.

    with factory.create(TEST_EMPLOYEE_ID, tc_first_work_day.datetime) as tracker:
        tracker.write_clocks(tc_first_work_day.datetime, evts)
        assert tracker.get_clocks(tc_first_work_day.datetime) == evts
        tracker.save()  # Just to see the test result in the test cache


def test_save(factory: TimeTrackerFactory, tc_first_work_day: CaseData):
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


@pytest.mark.parametrize(
    "testcase",
    ["tc_first_work_day"],  # Only one test is enough to check errors
    indirect=True,
)
def test_readonly_exc(factory: TimeTrackerFactory, testcase: CaseData):
    """
    Open the time tracker in read-only mode and check setters and
    `read_` methods are not accessible.
    """
    with factory.create(TEST_EMPLOYEE_ID, testcase.datetime, readonly=True) as tracker:
        with pytest.raises(TimeTrackerWriteException):
            tracker.set_vacation(testcase.datetime, 0.5)
        with pytest.raises(TimeTrackerWriteException):
            tracker.register_clock(
                testcase.datetime,
                ClockEvent.midnight_rollover(),
            )
        with pytest.raises(TimeTrackerWriteException):
            tracker.write_clocks(testcase.datetime, list(testcase.date_events))

        with pytest.raises(TimeTrackerAnalysisException):
            tracker.analyze(testcase.datetime)
        with pytest.raises(TimeTrackerReadException):
            tracker.read_day_schedule(testcase.datetime)

        with pytest.raises(TimeTrackerSaveException):
            tracker.save()


def test_error_employee(factory: TimeTrackerFactory):
    """
    Open the error employee and read the errors for the 01.01.25 and
    02.01.25.
    """
    DT_01_01_25 = dt.datetime(year=TEST_ERROR_EMPLOYEE_YEAR, month=1, day=1, hour=16)
    DT_02_01_25 = dt.datetime(year=TEST_ERROR_EMPLOYEE_YEAR, month=1, day=2, hour=16)
    DT_03_01_25 = dt.datetime(year=TEST_ERROR_EMPLOYEE_YEAR, month=1, day=3, hour=16)

    ERROR_MISSING_ENTRY = 110
    ERROR_ENTRY = 120

    with factory.create(TEST_ERROR_EMPLOYEE_ID, DT_02_01_25) as tracker:

        tracker.analyze(DT_02_01_25)
        assert tracker.read_day_attendance_error(DT_01_01_25) == ERROR_ENTRY
        assert tracker.read_day_attendance_error(DT_03_01_25) == ERROR_ENTRY

        # The missing entry error doesn't show up for current day
        assert tracker.read_day_attendance_error(DT_02_01_25) == 0
        assert tracker.read_year_attendance_error() == ERROR_ENTRY

        tracker.analyze(DT_03_01_25)
        assert tracker.read_day_attendance_error(DT_01_01_25) == ERROR_ENTRY
        assert tracker.read_day_attendance_error(DT_02_01_25) == ERROR_MISSING_ENTRY
        assert tracker.read_day_attendance_error(DT_03_01_25) == ERROR_ENTRY

        assert tracker.read_year_attendance_error() == ERROR_ENTRY

        with pytest.raises(TimeTrackerValueException):
            tracker.get_clocks(DT_01_01_25)

        with pytest.raises(TimeTrackerValueException):
            tracker.get_vacation(DT_03_01_25)
        with pytest.raises(TimeTrackerValueException):
            tracker.get_paid_absence(DT_03_01_25)


def test_error_description(factory: TimeTrackerFactory):
    """
    Check the lookup table function works.
    """
    DT_01_01_25 = dt.datetime(year=TEST_ERROR_EMPLOYEE_YEAR, month=1, day=1, hour=16)

    with factory.create(TEST_ERROR_EMPLOYEE_ID, DT_01_01_25) as tracker:

        for id, desc in TEST_ERRORS_TABLE.items():
            assert tracker.get_attendance_error_desc(id) == desc

        with pytest.raises(TimeTrackerValueException):
            tracker.get_attendance_error_desc(-1)


def test_set_paid_absence(factory: TimeTrackerFactory, tc_sickness: CaseData):
    """
    Modify the paid absence ratio on the test date and check the
    scheduled time changes as expected.
    """
    with factory.create(TEST_EMPLOYEE_ID, tc_sickness.datetime) as tracker:

        tracker.set_paid_absence(tc_sickness.datetime, 0.0)
        assert tracker.get_paid_absence(tc_sickness.datetime) == approx(0.0)

        tracker.analyze(tc_sickness.datetime)
        schedule = tracker.read_day_schedule(tc_sickness.datetime)
        assert schedule == tracker.opening_day_schedule

        tracker.set_paid_absence(tc_sickness.datetime, 0.5)
        tracker.analyze(tc_sickness.datetime)
        schedule = tracker.read_day_schedule(tc_sickness.datetime)
        assert schedule == (tracker.opening_day_schedule / 2)


def test_set_vacation(factory: TimeTrackerFactory, tc_vacation: CaseData):
    """
    Modify the vacation ratio on the test date and verify the scheduled
    time changes as expected. Check the vacation counter as well.
    """
    with factory.create(TEST_EMPLOYEE_ID, tc_vacation.datetime) as tracker:

        tracker.set_vacation(tc_vacation.datetime, 0.0)
        assert tracker.get_vacation(tc_vacation.datetime) == approx(0.0)

        tracker.analyze(tc_vacation.datetime)
        schedule = tracker.read_day_schedule(tc_vacation.datetime)
        assert schedule == tracker.opening_day_schedule

        tracker.set_vacation(tc_vacation.datetime, 0.5)
        tracker.analyze(tc_vacation.datetime)
        schedule = tracker.read_day_schedule(tc_vacation.datetime)
        assert schedule == (tracker.opening_day_schedule / 2)

        month_vacation = tracker.read_month_vacation(tc_vacation.datetime)
        assert month_vacation == approx(tc_vacation.month_vacation - 0.5)
        year_vacation = tracker.read_year_vacation()
        assert year_vacation == approx(tc_vacation.year_vacation - 0.5)


def test_set_attendance_error(factory: TimeTrackerFactory, tc_month_closing: CaseData):
    """
    Write a software error at the test date and check by reading the date
    and the year attendance error.
    """
    CUSTOM_SOFT_ERROR = 10

    with factory.create(TEST_EMPLOYEE_ID, tc_month_closing.datetime) as tracker:

        tracker.set_attendance_error(tc_month_closing.datetime, CUSTOM_SOFT_ERROR)
        date_error = tracker.get_attendance_error(tc_month_closing.datetime)
        assert date_error == CUSTOM_SOFT_ERROR

        tracker.analyze(tc_month_closing.datetime)
        # Since there is no error more critical, the year error must also
        # be CUSTOM_SOFT_ERROR
        year_error = tracker.read_year_attendance_error()
        assert year_error == CUSTOM_SOFT_ERROR


def test_register_max_evts(factory: TimeTrackerFactory, tc_vacation: CaseData):
    """
    Register the maximal number of events for an empty date and check
    the overflow correctly raise an error.
    """
    with factory.create(TEST_EMPLOYEE_ID, tc_vacation.datetime) as tracker:

        # Prepare the events list and write them
        events: list[ClockEvent | None] = []

        datetime = dt.datetime.combine(tc_vacation.datetime.date(), dt.time(hour=6))
        action = ClockAction.CLOCK_IN

        for _ in range(0, tracker.max_clock_events_per_day):
            event = ClockEvent(datetime.time(), action)
            events.append(event)

            action = (
                ClockAction.CLOCK_OUT
                if action is ClockAction.CLOCK_IN
                else ClockAction.CLOCK_IN
            )
            datetime += dt.timedelta(minutes=5)

        tracker.write_clocks(datetime, events)

        # Try to write one more event and check it fails
        overflow = ClockEvent(datetime.time(), action)

        with pytest.raises(TimeTrackerWriteException):
            tracker.register_clock(datetime, overflow)

        events.append(overflow)
        with pytest.raises(TimeTrackerWriteException):
            tracker.write_clocks(datetime, events)


def test_reset_analyzed(factory: TimeTrackerFactory, tc_first_work_day: CaseData):
    """
    Check that the `analyzed` property changes to `False` after a
    modification is done.
    """
    with factory.create(TEST_EMPLOYEE_ID, tc_first_work_day.datetime) as tracker:

        tracker.analyze(tc_first_work_day.datetime)
        tracker.set_attendance_error(tc_first_work_day.datetime, 0)
        assert not tracker.analyzed

        tracker.analyze(tc_first_work_day.datetime)
        tracker.set_paid_absence(tc_first_work_day.datetime, 0.0)
        assert not tracker.analyzed

        tracker.analyze(tc_first_work_day.datetime)
        tracker.set_vacation(tc_first_work_day.datetime, 0.0)
        assert not tracker.analyzed

        tracker.analyze(tc_first_work_day.datetime)
        tracker.register_clock(
            tc_first_work_day.datetime,
            ClockEvent(dt.time(hour=6), ClockAction.CLOCK_IN),
        )
        assert not tracker.analyzed

        tracker.analyze(tc_first_work_day.datetime)
        tracker.write_clocks(
            tc_first_work_day.datetime,
            [ClockEvent(dt.time(hour=6), ClockAction.CLOCK_IN)],
        )
        assert not tracker.analyzed


def test_wrong_version(factory: TimeTrackerFactory):
    """
    Try to open a time tracker that is not using the correct implementation
    version.
    """
    with pytest.raises(TimeTrackerOpenException):
        with factory.create(TEST_WRONG_VERSION_ID, TEST_WRONG_VERSION_YEAR):
            assert False, "Should have failed"


def test_date_out_of_year(factory: TimeTrackerFactory, tc_first_work_day: CaseData):
    """
    Verify that an error is raised when trying to read/write a date out of
    the time tracker's year.
    """
    with factory.create(TEST_EMPLOYEE_ID, tc_first_work_day.datetime) as tracker:
        tracker.analyze(tc_first_work_day.datetime)

        ref = tc_first_work_day.datetime
        wrong_date = dt.date(year=ref.year - 1, month=ref.month, day=ref.day)

        with pytest.raises(TimeTrackerDateException):
            tracker.get_clocks(wrong_date)
        with pytest.raises(TimeTrackerDateException):
            tracker.read_day_schedule(wrong_date)
        with pytest.raises(TimeTrackerDateException):
            tracker.read_month_schedule(wrong_date)
        with pytest.raises(TimeTrackerDateException):
            tracker.set_last_validation_anchor(wrong_date)
        with pytest.raises(TimeTrackerDateException):
            tracker.analyze(
                dt.datetime.combine(wrong_date, tc_first_work_day.datetime.time())
            )


def test_validation_anchor(factory: TimeTrackerFactory, tc_first_work_day: CaseData):
    """
    Verify that the can be written and read correctly.
    """
    anchor_date = dt.date(tc_first_work_day.datetime.year, 5, 3)
    with factory.create(TEST_EMPLOYEE_ID, tc_first_work_day.datetime) as tracker:

        tracker.set_last_validation_anchor(anchor_date)
        assert tracker.get_last_validation_anchor() == anchor_date
