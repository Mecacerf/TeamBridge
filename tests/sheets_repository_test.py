#!/usr/bin/env python3
"""
File: sheets_repository_test.py
Author: Bastian Cerf
Date: 18/05/2025
Description: 
    Unit test of the spreadsheets repository module.    

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import pytest
from pathlib import Path
import threading

# Internal libraries
from tests.test_constants import *
from src.core.spreadsheets.sheets_repository import *

# Local spreadsheet files cache folder
TEST_LOCAL_CACHE_FOLDER = str((Path(TEST_ASSETS_DST_FOLDER) / "local_cache").resolve())

@pytest.fixture
def repository(arrange_assets):
    """
    Pytest fixture that creates and configures the spreadsheets repository
    module.

    Args:
        arrange_assets: Prepare the assets folder for the test 
    """
    # The arrange_assets fixture already created a new test assets folder
    # Create a local cache folder inside it
    Path(TEST_LOCAL_CACHE_FOLDER).mkdir(exist_ok=False)

    # Use the test assets folder as remote repository
    configure(remote_repository=TEST_ASSETS_DST_FOLDER,
              local_cache=TEST_LOCAL_CACHE_FOLDER)
    
def test_acquire_sheet(repository):
    """
    Test that a spreadsheet file is correctly acquired from the repository.
    Once acquired, the file is present in the local cache folder and a lock
    file exists in the repository.
    """    
    sheet_path = acquire_spreadsheet_file(TEST_EMPLOYEE_ID)

    local_cache_file = (Path(TEST_LOCAL_CACHE_FOLDER) / Path(TEST_SPREADSHEET_FILE))
    repo_lock_file = (Path(TEST_ASSETS_DST_FOLDER) / Path(TEST_SPREADSHEET_FILE + LOCK_FILE_EXTENSION))

    # Assert that acquired file is at the expected place
    assert str(local_cache_file.resolve()) == str(sheet_path.resolve())
    # Assert that file exists in local cache and is locked on repository
    assert sheet_path.exists()
    assert repo_lock_file.exists()

def test_acquire_twice(repository):
    """
    Acquire the same spreadsheet file twice and test that it fails the
    second time, correctly preventing multiple accesses to the same file.
    """
    acquire_spreadsheet_file(TEST_EMPLOYEE_ID)
    with pytest.raises(TimeoutError):
        acquire_spreadsheet_file(TEST_EMPLOYEE_ID)

def test_acquire_sequentially(repository):
    """
    Start two processes that try to acquire the spreadsheet file concurrently.
    Test that the second process acquire the file only after the first process
    released it. 
    """
    sheet_path = acquire_spreadsheet_file(TEST_EMPLOYEE_ID)

    acquired = threading.Event()
    def process():
        """
        Second process tries to acquire the file but has to wait for the first
        process to release it.
        """
        acquire_spreadsheet_file(TEST_EMPLOYEE_ID)
        acquired.set()

    thread = threading.Thread(target=process)
    thread.start()
    
    # Simulate some work and release the file
    time.sleep(FILE_LOCK_TIMEOUT / 2.0)
    release_spreadsheet_file(sheet_path)

    thread.join()
    assert acquired.is_set()

def test_save_sheet(repository):
    """
    Acquire a spreadsheet file from the repository, modify it in the local cache 
    and test the saving function. The file in the repository shall then be equal
    to the file in the local cache.
    """
    sheet_file = acquire_spreadsheet_file(TEST_EMPLOYEE_ID)

    # Just write dummy text in the file and save it
    DUMMY_CONTENT = "I like coffee."
    with open(sheet_file, 'w') as file:
        file.write(DUMMY_CONTENT)
    save_spreadsheet_file(sheet_file)

    repo_file = Path(TEST_ASSETS_DST_FOLDER) / Path(TEST_SPREADSHEET_FILE) 
    with open(repo_file, 'r') as file:
        assert file.read(len(DUMMY_CONTENT)) == DUMMY_CONTENT

def test_release_sheet(repository):
    """
    Acquire a spreadsheet file from the repository and release it. Test that
    the lock file doesn't exist, as well as the file in the local cache folder.
    """
    sheet_path = acquire_spreadsheet_file(TEST_EMPLOYEE_ID)
    release_spreadsheet_file(sheet_path)

    repo_lock_file = (Path(TEST_ASSETS_DST_FOLDER) / Path(TEST_SPREADSHEET_FILE + LOCK_FILE_EXTENSION))

    assert not sheet_path.exists()
    assert not repo_lock_file.exists()

def test_list_employee(repository):
    """
    Test that the test employee ID is the only one listed.
    """
    ids = list_employee_ids()
    assert len(ids) == 1
    assert ids[0] == TEST_EMPLOYEE_ID
