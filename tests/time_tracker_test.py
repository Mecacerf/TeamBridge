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
from spreadsheets_database import SpreadsheetsDatabase

################################################
#               Tests constants                #
################################################

# General tests configuration
TEST_DATE = dt.date(year=2025, month=3, day=9)
TEST_TIME = dt.time(hour=8, minute=10)
TEST_DATETIME = dt.datetime.combine(date=TEST_DATE, time=TEST_TIME)
TEST_EMPLOYEE_ID = "000"

# Spreadsheet Time Tracker
SPREADSHEET_SAMPLES_FOLDER = "samples/"
SPREADSHEET_CACHE_FOLDER = ".cache/samples-test"

################################################
#      Spreadsheet Time Tracker provider       #
################################################

def build_spreadsheet_time_tracker(employee_id: str, date: dt.date) -> ITodayTimeTracker:
    """
    Build an ITodayTimeTracker that uses spreadsheet files for data storage.

    Returns:
        ITodayTimeTracker: specific implementation
    """
    # Create the database provider 
    database = SpreadsheetsDatabase(SPREADSHEET_CACHE_FOLDER)
    # Create and return instance
    return SpreadsheetTimeTracker(database, employee_id, date)

def evaluate_spreadsheet_time_tracker(time_tracker: SpreadsheetTimeTracker, date: dt.datetime):
    """
    Evaluate the spreadsheet time tracker at given date and time.
    """
    # For test purpose, access private attributes
    # Get the init sheet in write mode
    init_sheet = time_tracker._workbook_wr.worksheets[SHEET_INIT]
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
    cache = pathlib.Path(SPREADSHEET_CACHE_FOLDER)
    # Check samples folder exists 
    if not samples.exists():
        raise FileNotFoundError(f"Samples folder not found at {samples.resolve()}")
    # Delete old cache folder if existing
    if cache.exists():
        def remove_readonly(func, path, exc_info):
            """Changes the file attribute and retries deletion if permission is denied."""
            import os
            os.chmod(path, 0o777) # Grant full permissions
            func(path) # Retry the function
        # Remove previous cache
        shutil.rmtree(cache, onexc=remove_readonly)   
    # Copy samples to cache
    shutil.copytree(samples, cache)

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
    employee, _ = default_time_tracker_provider

    # Try to access clock events directly
    with pytest.raises(IllegalReadException):
        employee.get_clock_events_today()

def test_initial_state(default_time_tracker_provider):
    """
    Check that the opened employee is not clocked in and hasn't worked today or this month.
    """
    # Unpack the provider
    employee, evaluate = default_time_tracker_provider
    # Evaluation is required before accessing employee's data
    evaluate(employee, TEST_DATETIME)

    assert employee.is_clocked_in_today() is False # Not clocked in
    assert not employee.get_clock_events_today() # No event today
    assert employee.get_worked_time_today() == dt.timedelta(hours=0, minutes=0, seconds=0) # No work today
    assert employee.get_monthly_balance() == dt.timedelta(hours=0, minutes=0, seconds=0) # No work this month

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

    # Evaluate before accessing next values
    # Evaluate at clock in time: no worked time for now
    evaluate(employee, dt.datetime.combine(date=TEST_DATE, time=clock_in_time))

    # Assert
    assert employee.is_clocked_in_today() is True # Now the employee is clocked in
    assert len(employee.get_clock_events_today()) == 1 # One clock event today
    
    event = employee.get_clock_events_today()[0] # Get clock event
    assert event.action == ClockAction.CLOCK_IN # Clock in event
    assert event.time == clock_in_time # At expected time

    # No worked time, the employee has just clocked in
    assert employee.get_worked_time_today() == dt.timedelta(hours=0, minutes=0, seconds=0)
    # No work this month
    assert employee.get_monthly_balance() == dt.timedelta(hours=0, minutes=0, seconds=0) 
    # Check worked time from 7h35 to 8h10 is 35 minutes
    evaluate(employee, dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=8, minute=10)))
    assert employee.get_worked_time_today(now=dt.time(hour=8, minute=10)) == dt.timedelta(minutes=35)

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

    # Refresh before accessing next values
    # Refresh at clock out time
    evaluate(employee, dt.datetime.combine(date=TEST_DATE, time=clock_out_time))

    # Assert
    assert employee.is_clocked_in_today() is False # Clocked out
    assert len(employee.get_clock_events_today()) == 2 # Two clock events today

    event = employee.get_clock_events_today()[0] # Get clock in event
    assert event.action == ClockAction.CLOCK_IN # Clock in event
    assert event.time == clock_in_time # At expected time

    event = employee.get_clock_events_today()[1] # Get clock out event
    assert event.action == ClockAction.CLOCK_OUT # Clock in event
    assert event.time == clock_out_time # At expected time

    # Monthly balance is updated the next day
    assert employee.get_monthly_balance() == dt.timedelta(hours=0, minutes=0, seconds=0)
    # Clocked in at 7h35 and clocked out at 12h10 results in 4h35 of work 
    assert employee.get_worked_time_today() == dt.timedelta(hours=4, minutes=35, seconds=0)
    # Checking the worked time at 12h40 doesn't change the result since the employee is clocked out
    evaluate(employee, dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=12, minute=40)))
    assert employee.get_worked_time_today() == dt.timedelta(hours=4, minutes=35, seconds=0)

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

    # Refresh before accessing next values
    # Refresh at last clock out time
    evaluate(employee, dt.datetime.combine(date=TEST_DATE, time=clock_out_time_2))

    # Assert
    assert employee.is_clocked_in_today() is False # Clocked out
    assert len(employee.get_clock_events_today()) == len(events)

    # Verify registered events
    for i, event in enumerate(employee.get_clock_events_today(), 0):
        # Assert clock type and time match
        assert event.action == events[i].action
        assert event.time == events[i].time

    # Monthly balance is updated the next day
    assert employee.get_monthly_balance() == dt.timedelta(hours=0, minutes=0, seconds=0)
    # The employee worked 7h45 today
    assert employee.get_worked_time_today() == dt.timedelta(hours=7, minutes=45, seconds=0)

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
    Try to open the same time tracker multiple times.
    """
    # Unpack the provider methods
    provider, evaluate = time_tracker_provider
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
    with pytest.raises(ValueError):
        employee.register_clock(event_in)

    # Time tracker is not readable
    assert not employee.is_readable()
    # Evaluate, check readable and close
    evaluate(employee, dt.datetime.combine(date=TEST_DATE, time=dt.time(hour=14)))
    assert employee.is_readable()
    employee.close()

    # Reopen and assert it is not readable
    employee = provider(TEST_EMPLOYEE_ID, TEST_DATE)
    assert not employee.is_readable()
    # Finally close
    employee.close()

def test_monthly_balance(time_tracker_provider):
    """
    Verify the monthly balance after a few days of work.
    """
    # Unpack the provider methods
    provider, evaluate = time_tracker_provider

    # Get the first day of the test month
    first_date = dt.date(year=TEST_DATE.year, month=TEST_DATE.month, day=2)
    # Open a time tracker at first day of the month and evaluate it at this date at 8h00
    employee = provider(TEST_EMPLOYEE_ID, first_date)
    evaluate(employee, dt.datetime.combine(date=first_date, time=dt.time(hour=8)))
    # Since no activity is logged for now, the balance is negative daily schedule
    print(f"balance: {employee.get_monthly_balance()}") 
    employee.close()

    # NOTE: TODO This test must be completed once the spreadsheet behaviour has been clarified.
