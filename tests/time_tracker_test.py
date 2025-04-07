#!/usr/bin/env python3
"""
File: time_tracker_test.py
Author: Bastian Cerf
Date: 17/02/2025
Description: 
    Unit test the ITodayTimeTracker interface implementations to validate expected behaviors.
Usage:
    Use pytest to execute the tests. You can run it by executing the command below in the TeamBridge/ folder.
    - pytest

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# General imports
import pytest
import datetime as dt
from typing import Callable
from collections.abc import Generator
from time_tracker_interface import ITodayTimeTracker, ClockEvent, ClockAction, IllegalReadException
# Specific implementation imports
from spreadsheet_time_tracker import SpreadsheetTimeTracker, CELL_DATE, CELL_HOUR, SHEET_INIT
from spreadsheets_repository import SpreadsheetsRepository

################################################
#               Tests constants                #
################################################

# General tests configuration
TEST_EMPLOYEE_ID = "unit-test"
# Test date and time
TEST_DATE = dt.date(year=2025, month=3, day=10) # 10 March 2025 is a monday
TEST_TIME = dt.time(hour=8, minute=10)
TEST_DATETIME = dt.datetime.combine(date=TEST_DATE, time=TEST_TIME)
# Expected values at configured date and time
# Daily schedule for a day of the week
TEST_DAILY_SCHEDULE = dt.timedelta(hours=8, minutes=17)
# Total time the employee should have worked from the beginning of the month
# Equal to number of working days times daily schedule
TEST_MONTHLY_BALANCE_NO_WORK = (TEST_DAILY_SCHEDULE * 6)

# Spreadsheet Time Tracker
SPREADSHEET_SAMPLES_FOLDER = "tests/assets/"
SPREADSHEET_SAMPLES_TEST_FOLDER = ".cache/samples/"
SPREADSHEET_LOCAL_CACHE_TEST_FOLDER = ".cache/local-cache/"
SPREADSHEET_TEST_FILE_NAME = f"{TEST_EMPLOYEE_ID}-template.xlsx"

################################################
#      Spreadsheet Time Tracker provider       #
################################################

def build_spreadsheet_time_tracker(employee_id: str, date: dt.date) -> ITodayTimeTracker:
    """
    Build an ITodayTimeTracker that uses spreadsheet files for data storage.

    Returns:
        ITodayTimeTracker: specific implementation
    """
    # Ensure the 
    # Create the database provider 
    database = SpreadsheetsRepository(repository_path=SPREADSHEET_SAMPLES_TEST_FOLDER, 
                                    local_cache=SPREADSHEET_LOCAL_CACHE_TEST_FOLDER)
    # Create and return instance
    return SpreadsheetTimeTracker(database, employee_id, date)

def evaluate_spreadsheet_time_tracker(time_tracker: SpreadsheetTimeTracker, date: dt.datetime):
    """
    Evaluate the spreadsheet time tracker at given date and time.
    """
    # For test purpose, access private attributes
    # Get the raw init sheet 
    init_sheet = time_tracker._workbook_raw.worksheets[SHEET_INIT]
    # Overwrite the TODAY() function by the test date and time
    # Write the date
    init_sheet[CELL_DATE] = date.date()
    # Write the time
    init_sheet[CELL_HOUR] = date.time()
    # Commit and evaluate
    # Known limitation: in order to save the modified cells, a commit is required, while the
    # actual evaluate() method that is used directly from the time tracker interface  doesn't
    # automatically commit.
    time_tracker.commit()
    time_tracker.evaluate()

@pytest.fixture
def arrange_spreadsheet_time_tracker():
    """
    Prepare the cache folder that will be used to store temporary spreadsheet file(s) for the tests.
    """
    import shutil, pathlib
    # Get source samples and cache folder
    samples = pathlib.Path(SPREADSHEET_SAMPLES_FOLDER)
    samples_cache = pathlib.Path(SPREADSHEET_SAMPLES_TEST_FOLDER)
    local_cache = pathlib.Path(SPREADSHEET_LOCAL_CACHE_TEST_FOLDER)
    # Check samples folder exists 
    if not samples.exists():
        raise FileNotFoundError(f"Samples folder not found at {samples.resolve()}")
    
    # Remove with privileges
    def remove_readonly(func, path, exc_info):
            """Changes the file attribute and retries deletion if permission is denied."""
            import os
            os.chmod(path, 0o777) # Grant full permissions
            func(path) # Retry the function

    # Delete old cache folder if existing
    if samples_cache.exists():
        shutil.rmtree(samples_cache, onexc=remove_readonly)
    # Delete local cache folder if last time tracker wasn't correctly closed
    if local_cache.exists():
        shutil.rmtree(local_cache, onexc=remove_readonly)   
    # Copy samples to test samples cache
    shutil.copytree(samples, samples_cache)

#################################################
# Time tracker implementation provider fixtures #
#################################################

@pytest.fixture(params=[
    # List of (implementation provider methods, evaluate method)
    (build_spreadsheet_time_tracker, evaluate_spreadsheet_time_tracker)
])
def time_tracker_provider(request, 
                          arrange_spreadsheet_time_tracker
                          ) -> tuple[Callable[[str, dt.date], ITodayTimeTracker], Callable[[ITodayTimeTracker, dt.datetime], None]]:
    """
    Parametrized fixture for retrieving instances of time tracker implementations.

    Returns:
        tuple: tuple containing the two functions described below
        tuple[0]: call the provider method to get a time tracker instance that is using the implementation under test
        tuple[1]: call this method to evaluate the time tracker under test at given date and time
    """
    return request.param

@pytest.fixture
def default_time_tracker_provider(time_tracker_provider) -> Generator[tuple[ITodayTimeTracker, Callable[[ITodayTimeTracker, dt.datetime], None]], None, None]:
    """
    Get a default time tracker opened for default test employee at default test date.
    Automatically manages opening and closing.

    Returns:
        tuple: tuple containing two objects described below
        tuple[0]: the time tracker instance
        tuple[1]: call this method to evaluate the time tracker under test at given date and time
    """
    # Unpack the provider methods
    provider, evaluate = time_tracker_provider
    # Create the time tracker for the default employee 
    employee = provider(TEST_EMPLOYEE_ID, TEST_DATE)
    # Give the time tracker and the evaluation method to the test
    yield (employee, evaluate)
    # Close the time tracker
    employee.close()

################################################
#           Time tracker unit tests            #
################################################

def test_open_employee(default_time_tracker_provider):
    """
    Try to open the employee template data and retrieve his firstname and name.
    Expected firstname, name: Meca, Cerf
    """
    # Unpack the provider
    employee, _ = default_time_tracker_provider

    # Check expected firstname and name
    assert employee.get_firstname() == "Meca"
    assert employee.get_name() == "Cerf"

def test_read_unavailable(default_time_tracker_provider):
    """
    The read functions are not available before first evaluation.
    """
    # Unpack the provider
    employee, evaluate = default_time_tracker_provider
    # Readable is initially False
    assert employee.is_readable() is False
    # Try to access worked time directly
    with pytest.raises(IllegalReadException):
        employee.get_daily_worked_time()
    # Try to access monthly balance directly
    with pytest.raises(IllegalReadException):
        employee.get_monthly_balance()
    # Try to access daily schedule
    with pytest.raises(IllegalReadException):
        employee.get_daily_schedule()
    # Try to access daily balance
    with pytest.raises(IllegalReadException):
        employee.get_daily_balance()

def test_evaluation(default_time_tracker_provider):
    """
    Evaluate the employee's time tracker and check initial state.
    """
    # Unpack the provider
    employee, evaluate = default_time_tracker_provider

    # Always accessible
    assert employee.is_clocked_in_today() is False # Not clocked in
    assert not employee.get_clock_events_today() # No event today

    # Evaluation is required before accessing employee's evaluated data
    assert employee.is_readable() is False
    evaluate(employee, TEST_DATETIME)
    assert employee.is_readable() is True

    # Check initial state
    # Check daily schedule 
    assert employee.get_daily_schedule() == TEST_DAILY_SCHEDULE
    # No work today
    assert employee.get_daily_worked_time().total_seconds() == 0
    # Should work for the daily schedule
    assert employee.get_daily_balance() == -TEST_DAILY_SCHEDULE
    # No work this month, complete month until the date is due
    assert employee.get_monthly_balance() == -TEST_MONTHLY_BALANCE_NO_WORK

def test_clock_in(default_time_tracker_provider):
    """
    Clock in the employee and verify the registration.
    """
    # Unpack the provider
    employee, evaluate = default_time_tracker_provider
    
    # Act
    # The write functions shall be accessible even though the time tracker is not readable
    # Create clock in event at 7h35
    clock_in_time = dt.time(hour=7, minute=35)
    event = ClockEvent(clock_in_time, ClockAction.CLOCK_IN)
    # Register event
    employee.register_clock(event)
    employee.commit()

    # Assert
    assert employee.is_clocked_in_today() is True # Now the employee is clocked in
    assert len(employee.get_clock_events_today()) == 1 # One clock event today

    event = employee.get_clock_events_today()[0] # Get clock event
    assert event.action == ClockAction.CLOCK_IN # Clock in event
    assert event.time == clock_in_time # At expected time

    # Evaluate before accessing next values
    # Evaluate at clock in time: no worked time for now
    evaluate(employee, dt.datetime.combine(date=TEST_DATE, time=clock_in_time))

    # No worked time, the employee has just clocked in
    assert employee.get_daily_worked_time().total_seconds() == 0
    assert employee.get_daily_balance() == -TEST_DAILY_SCHEDULE

    # Evaluate at 8h10
    evaluate(employee, dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=8, minute=10)))

    # Check worked time from 7h35 to 8h10 is 35 minutes
    worked_time = dt.timedelta(minutes=35)
    assert employee.get_daily_worked_time() == worked_time
    # Daily balance has lost 35 minutes on the daily schedule, as well as monthly balance
    assert employee.get_daily_balance() == (worked_time - employee.get_daily_schedule())
    assert employee.get_monthly_balance() == (worked_time - TEST_MONTHLY_BALANCE_NO_WORK)

def test_clock_out(default_time_tracker_provider):
    """
    Clock in / clock out sequence and verify registrations.
    """
    # Unpack the provider
    employee, evaluate = default_time_tracker_provider
    
    # Act
    # Create clock in event at 7h35 
    clock_in_time = dt.time(hour=7, minute=35)
    event_in = ClockEvent(clock_in_time, ClockAction.CLOCK_IN)
    # Create clock out event at 12h10
    clock_out_time = dt.time(hour=12, minute=10)
    event_out = ClockEvent(clock_out_time, ClockAction.CLOCK_OUT)
    # Register events
    employee.register_clock(event_in)
    employee.register_clock(event_out)
    employee.commit()

    # Assert
    assert employee.is_clocked_in_today() is False # Clocked out
    assert len(employee.get_clock_events_today()) == 2 # Two clock events today

    event = employee.get_clock_events_today()[0] # Get clock in event
    assert event.action == ClockAction.CLOCK_IN # Clock in event
    assert event.time == clock_in_time # At expected time

    event = employee.get_clock_events_today()[1] # Get clock out event
    assert event.action == ClockAction.CLOCK_OUT # Clock in event
    assert event.time == clock_out_time # At expected time

    # Evaluate before accessing next values
    # Evaluate at clock out time
    evaluate(employee, dt.datetime.combine(date=TEST_DATE, time=clock_out_time))

    # Clocked in at 7h35 and clocked out at 12h10 results in 4h35 of work 
    worked_time = dt.timedelta(hours=4, minutes=35, seconds=0)
    assert employee.get_daily_worked_time() == worked_time
    assert employee.get_daily_balance() == (worked_time - employee.get_daily_schedule())
    assert employee.get_monthly_balance() == (worked_time - TEST_MONTHLY_BALANCE_NO_WORK)

    # Checking the worked time at 12h40 doesn't change the result since the employee is clocked out
    evaluate(employee, dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=12, minute=40)))
    assert employee.get_daily_worked_time() == worked_time

def test_full_day(default_time_tracker_provider):
    """
    Work for a full day with midday break including a little break at 10h and check results.
    Clock in: 8h
    Clock out: 10h
    Clock in: 10h15
    Clock out: 12h20
    Clock in: 13h
    Clock out: 16h40
    Worked time: 2h + 2h05 + 3h40 = 7h45 
    """
    # Unpack the provider
    employee, evaluate = default_time_tracker_provider
    
    # Act
    # Create clock in/out events
    clock_in_time_0 = dt.time(hour=8)
    event_in_0 = ClockEvent(clock_in_time_0, ClockAction.CLOCK_IN)
    clock_out_time_0 = dt.time(hour=10)    
    event_out_0 = ClockEvent(clock_out_time_0, ClockAction.CLOCK_OUT)
    clock_in_time_1 = dt.time(hour=10, minute=15)
    event_in_1 = ClockEvent(clock_in_time_1, ClockAction.CLOCK_IN)
    clock_out_time_1 = dt.time(hour=12, minute=20)
    event_out_1 = ClockEvent(clock_out_time_1, ClockAction.CLOCK_OUT)
    clock_in_time_2 = dt.time(hour=13)
    event_in_2 = ClockEvent(clock_in_time_2, ClockAction.CLOCK_IN)
    clock_out_time_2 = dt.time(hour=16, minute=40)
    event_out_2 = ClockEvent(clock_out_time_2, ClockAction.CLOCK_OUT)

    # Create events list
    events = [event_in_0, event_out_0, event_in_1, event_out_1, event_in_2, event_out_2]
    
    # Register events
    for event in events:
        employee.register_clock(event)
    # Save events
    employee.commit()

    # Assert
    assert employee.is_clocked_in_today() is False # Clocked out
    assert len(employee.get_clock_events_today()) == len(events)

    # Verify registered events
    for i, event in enumerate(employee.get_clock_events_today(), 0):
        # Assert clock type and time match
        assert event.action == events[i].action
        assert event.time == events[i].time

    # Evaluate before accessing next values
    # Evaluate at last clock out time
    evaluate(employee, dt.datetime.combine(date=TEST_DATE, time=clock_out_time_2))

    # The employee worked 7h45 today
    worked_time = dt.timedelta(hours=7, minutes=45, seconds=0)
    assert employee.get_daily_worked_time() == worked_time
    assert employee.get_daily_balance() == (worked_time - employee.get_daily_schedule())
    assert employee.get_monthly_balance() == (worked_time - TEST_MONTHLY_BALANCE_NO_WORK)

def test_wrong_clock_action(default_time_tracker_provider):
    """
    Test to clock out while not clocked in, double clock in and double clock out must all fail.
    """
    # Unpack the provider
    employee, _ = default_time_tracker_provider

    # Try to clock out while not clocked in
    event_out = ClockEvent(dt.time(hour=8, minute=20), ClockAction.CLOCK_OUT)

    # Assert that it throws an error
    with pytest.raises(ValueError):
        employee.register_clock(event_out)

    # Try double clock in at the same time
    event_in = ClockEvent(dt.time(hour=8, minute=20), ClockAction.CLOCK_IN)

    # First register works
    employee.register_clock(event_in)
    employee.commit()
    # Second clock in throws an error
    with pytest.raises(ValueError):
        employee.register_clock(event_in)

    # Register clock out event at 11h
    event_out = ClockEvent(dt.time(hour=11), ClockAction.CLOCK_OUT)
    # First register work
    employee.register_clock(event_out)
    employee.commit()

    # Clock out again at 11h01
    event_out = ClockEvent(dt.time(hour=11, minute=1), ClockAction.CLOCK_OUT)
    # Second clock out throws an error, since the employee is already clocked out
    with pytest.raises(ValueError):
        employee.register_clock(event_out)

def test_unordered_clock_events(default_time_tracker_provider):
    """
    Try to register unordered clock events and verify that it throws errors.
    """
    # Unpack the provider
    employee, _ = default_time_tracker_provider
    
    # Register a clock in at 11h
    event_in = ClockEvent(dt.time(hour=11), ClockAction.CLOCK_IN)
    employee.register_clock(event_in)
    employee.commit()

    # Register a clock out at 8h must throw an error
    event_out = ClockEvent(dt.time(hour=8), ClockAction.CLOCK_OUT)
    with pytest.raises(ValueError):
        employee.register_clock(event_out)

def test_multiple_openings(time_tracker_provider):
    """
    Try to open the same time tracker multiple times without evaluating it and see
    if the clock events correctly persist. 
    """
    # Unpack the provider methods
    provider, _ = time_tracker_provider
    # Open a time tracker
    employee = provider(TEST_EMPLOYEE_ID, TEST_DATE)

    # Write a clock in action
    event_in = ClockEvent(dt.time(hour=10), ClockAction.CLOCK_IN)
    employee.register_clock(event_in)
    employee.commit()

    # Close and reopen
    employee.close()
    employee = provider(TEST_EMPLOYEE_ID, TEST_DATE)

    # Writing a new clock in event should fail
    event_in = ClockEvent(dt.time(hour=11), ClockAction.CLOCK_IN)
    with pytest.raises(ValueError, match="while expecting a"):
        employee.register_clock(event_in)

    # Write a clock out event
    event_out = ClockEvent(dt.time(hour=11), ClockAction.CLOCK_OUT)
    employee.register_clock(event_out)
    employee.commit()

    # Close and reopen
    employee.close()
    employee = provider(TEST_EMPLOYEE_ID, TEST_DATE)

    # Check that the two events have been correctly registered
    assert employee.is_clocked_in_today() is False
    events = employee.get_clock_events_today()
    assert events[0].action == ClockAction.CLOCK_IN
    assert events[0].time == dt.time(hour=10)
    assert events[1].action == ClockAction.CLOCK_OUT
    assert events[1].time == dt.time(hour=11)
    # Close
    employee.close()

def test_monthly_daily_balance(time_tracker_provider):
    """
    Verify the monthly and daily balance.
    """
    # Unpack the provider methods
    provider, evaluate = time_tracker_provider

    # Get first day of the month at 8h, it is a saturday
    datetime = dt.datetime(year=TEST_DATE.year, month=TEST_DATE.month, day=1, hour=8)
    # Open a time tracker at test date
    employee = provider(TEST_EMPLOYEE_ID, datetime.date())
    # Evaluate the time tracker at first day of the month, which is a weekend.
    evaluate(employee, datetime)
    # The monthly and daily balances shall be 0
    employee.get_monthly_balance().total_seconds() == 0
    employee.get_daily_balance().total_seconds() == 0

    # Move to monday
    datetime = dt.datetime(year=TEST_DATE.year, month=TEST_DATE.month, day=3, hour=8)
    # Evaluate the time tracker
    evaluate(employee, datetime)
    # Since one working day is due, the monthly balance is the daily schedule, as well as teh daily balance
    employee.get_monthly_balance() == -employee.get_daily_schedule()
    employee.get_daily_balance() == -employee.get_daily_schedule()

    # Close the time tracker
    employee.close()

#################################################
# Spreadsheets Time tracker specific unit tests #
#################################################

def test_spreadsheet_time_tracker_write(arrange_spreadsheet_time_tracker):
    """
    Open, write and close a SpreadsheetTimeTracker and verify the document.
    """
    # Define test constants
    DATE = dt.date(year=2025, day=12, month=3)
    CLOCK_IN_CELL_AT_DATE = 'G20'
    CLOCK_OUT_CELL_AT_DATE = 'H20'
    # Build the time tracker by directly accessing the build function
    employee = build_spreadsheet_time_tracker(TEST_EMPLOYEE_ID, DATE)
    # Write a clock in event
    event_in = ClockEvent(dt.time(hour=8, minute=35), ClockAction.CLOCK_IN)
    employee.register_clock(event_in)
    # Write a clock out event
    event_out = ClockEvent(dt.time(hour=9, minute=45), ClockAction.CLOCK_OUT)
    employee.register_clock(event_out)
    # Commit and close
    employee.commit()
    employee.close()

    # Get file path
    from pathlib import Path
    file_path = Path(SPREADSHEET_SAMPLES_TEST_FOLDER) / Path(SPREADSHEET_TEST_FILE_NAME)
    # Use openpyxl to verify the file
    import openpyxl
    workbook = openpyxl.load_workbook(filename=file_path)
    # Get sheet for test month
    month_sheet = workbook.worksheets[DATE.month] # Assuming sheet 0 is init
    # Check values
    assert month_sheet[CLOCK_IN_CELL_AT_DATE].value == dt.time(hour=8, minute=35)
    assert month_sheet[CLOCK_OUT_CELL_AT_DATE].value == dt.time(hour=9, minute=45)
