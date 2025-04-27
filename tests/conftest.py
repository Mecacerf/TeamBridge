#!/usr/bin/env python3
"""
File: conftest.py
Author: Bastian Cerf
Date: 13/04/2025
Description: 
    Common configuration for unit tests.
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
from teambridge_model import TeamBridgeModel
from teambridge_viewmodel import TeamBridgeViewModel
from barcode_scanner import BarcodeScanner

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
#               Common fixtures                #
################################################

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

@pytest.fixture
def teambridge_model(arrange_spreadsheet_time_tracker) -> Generator[TeamBridgeModel, None, None]:
    """
    Create a configured teambridge model instance.
    """
    # Create the model using a SpreadsheetTimeTracker
    repository = SpreadsheetsRepository(SPREADSHEET_SAMPLES_TEST_FOLDER)
    time_tracker_provider=lambda date, code: SpreadsheetTimeTracker(repository=repository, employee_id=code, date=date)
    model = TeamBridgeModel(time_tracker_provider=time_tracker_provider)
    # Yield and close automatically
    yield model
    model.close()

@pytest.fixture
def teambridge_viewmodel(teambridge_model, monkeypatch) -> Generator[TeamBridgeViewModel, None, None]:
    """
    Create a configured teambridge viewmodel instance.
    """
    # Create a barcode scanner
    scanner = BarcodeScanner()
    def void(**kwargs): pass
    monkeypatch.setattr(scanner, "close", void)
    # Create a viewmodel
    viewmodel = TeamBridgeViewModel(teambridge_model, 
                                    scanner=scanner, 
                                    cam_idx=0,
                                    scan_rate=10,
                                    debug_mode=True)
    # Yield and close automatically
    # The scanner is also given in order to use monkeypatch to mock its functionalities
    yield (viewmodel, scanner)
    viewmodel.close()