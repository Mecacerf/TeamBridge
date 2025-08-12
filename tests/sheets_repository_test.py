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
from pytest import MonkeyPatch
from pathlib import Path
import threading
import time
import logging

# Internal libraries
from .test_constants import *
from core.spreadsheets.sheets_repository import (
    SheetsRepoAccessor,
    FILE_LOCK_TIMEOUT,
    LOCK_FILE_EXTENSION,
)

logger = logging.getLogger(__name__)

# Local spreadsheet files cache folder
TEST_LOCAL_CACHE_FOLDER = str((Path(TEST_ASSETS_DST_FOLDER) / "local_cache").resolve())


@pytest.fixture
def repository(arrange_assets: None) -> SheetsRepoAccessor:
    """
    Pytest fixture that creates and configures the spreadsheets repository
    class instance.

    Args:
        arrange_assets: Prepare the assets folder for the test.
    """
    # The arrange_assets fixture already created a new test assets folder
    # Create a local cache folder inside it
    Path(TEST_LOCAL_CACHE_FOLDER).mkdir(exist_ok=False)

    # Use the test assets folder as remote repository
    return SheetsRepoAccessor(
        remote_repository=TEST_REPOSITORY_ROOT, local_cache=TEST_LOCAL_CACHE_FOLDER
    )


def test_repo_available(repository: SheetsRepoAccessor):
    """
    Check that the repository is available and reachable.
    """
    assert repository.check_repo_available()


def test_repo_unavailable(repository: SheetsRepoAccessor):
    """
    Check that the repository is unavailable if the folder has been
    deleted. The accessor may try to wakeup a potentially sleeping drive
    so this test can take some time.
    """
    import shutil

    shutil.rmtree(TEST_REPOSITORY_ROOT)
    assert not repository.check_repo_available()


def test_acquire_sheet(repository: SheetsRepoAccessor):
    """
    Test that a spreadsheet file is correctly acquired from the repository.
    Once acquired, the file is present in the local cache folder and a lock
    file exists in the repository.
    """
    sheet_path = repository.acquire_spreadsheet_file(TEST_EMPLOYEE_ID)

    local_cache_file = Path(TEST_LOCAL_CACHE_FOLDER) / TEST_SPREADSHEET_FILE
    repo_lock_file = Path(TEST_REPOSITORY_ROOT) / (
        TEST_SPREADSHEET_FILE + LOCK_FILE_EXTENSION
    )

    # Assert that acquired file is at the expected place
    assert str(local_cache_file.resolve()) == str(sheet_path.resolve())
    # Assert that file exists in local cache and is locked on repository
    assert sheet_path.exists()
    assert repo_lock_file.exists()


def test_acquire_sheet_fails(repository: SheetsRepoAccessor, monkeypatch: MonkeyPatch):
    """
    Stub the `shutil.copy2()` function that is used in the acquiring process
    to copy the sheet file from the repository to the local cache to fail
    every time. Ensure the function returns an error and correctly releases
    the lock file.
    """

    def stub_copy2(src, dst):
        logger.debug(f"Stub shutil.copy2() called with src='{src}' and dst='{dst}'.")
        raise OSError("Stub error")

    # Patch the specific shutil reference the module is holding
    import core.spreadsheets.sheets_repository as sheets_repo

    monkeypatch.setattr(sheets_repo.shutil, "copy2", stub_copy2)

    with pytest.raises(TimeoutError):
        repository.acquire_spreadsheet_file(TEST_EMPLOYEE_ID)

    local_cache_file = Path(TEST_LOCAL_CACHE_FOLDER) / TEST_SPREADSHEET_FILE
    repo_lock_file = Path(TEST_REPOSITORY_ROOT) / (
        TEST_SPREADSHEET_FILE + LOCK_FILE_EXTENSION
    )

    # Neither of the local file or the lock must exist
    assert not local_cache_file.exists()
    assert not repo_lock_file.exists()


def test_acquire_read_only(repository: SheetsRepoAccessor):
    """
    This is the same test as `test_acquire_sheet` but the file should not
    be locked on the remote repository.
    """
    sheet_path = repository.acquire_spreadsheet_file(TEST_EMPLOYEE_ID, readonly=True)

    local_cache_file = Path(TEST_LOCAL_CACHE_FOLDER) / (
        "readonly_" + TEST_SPREADSHEET_FILE
    )

    # Assert that acquired file is at the expected place
    assert str(local_cache_file.resolve()) == str(sheet_path.resolve())
    # Assert that file exists in local cache and is locked on repository
    assert sheet_path.exists()
    # Assert no lock file exists
    assert len(list(Path(TEST_LOCAL_CACHE_FOLDER).glob("*.lock"))) == 0


def test_acquire_twice(repository: SheetsRepoAccessor):
    """
    Acquire the same spreadsheet file twice and test that it fails the
    second time, correctly preventing multiple accesses to the same file.
    """
    repository.acquire_spreadsheet_file(TEST_EMPLOYEE_ID)
    with pytest.raises(TimeoutError):
        repository.acquire_spreadsheet_file(TEST_EMPLOYEE_ID)


def test_acquire_twice_read_only(repository: SheetsRepoAccessor):
    """
    Acquire the same spreadsheet file twice in read-only mode and test
    that it fails the second time, correctly preventing multiple accesses
    to the same file (by one program instance).
    """
    repository.acquire_spreadsheet_file(TEST_EMPLOYEE_ID, readonly=True)
    with pytest.raises(FileExistsError):
        repository.acquire_spreadsheet_file(TEST_EMPLOYEE_ID, readonly=True)


def test_acquire_sequentially(repository: SheetsRepoAccessor):
    """
    Start two processes that try to acquire the spreadsheet file concurrently.
    Test that the second process acquire the file only after the first process
    released it.
    """
    sheet_path = repository.acquire_spreadsheet_file(TEST_EMPLOYEE_ID)

    acquired = threading.Event()

    def process():
        """
        Second process tries to acquire the file but has to wait for the first
        process to release it.
        """
        repository.acquire_spreadsheet_file(TEST_EMPLOYEE_ID)
        acquired.set()

    thread = threading.Thread(target=process)
    thread.start()

    # Simulate some work and release the file
    time.sleep(FILE_LOCK_TIMEOUT / 2.0)
    repository.release_spreadsheet_file(sheet_path)

    thread.join()
    assert acquired.is_set()


def test_save_sheet(repository: SheetsRepoAccessor):
    """
    Acquire a spreadsheet file from the repository, modify it in the local
    cache and test the saving function. The file in the repository shall
    then be equal to the file in the local cache.
    """
    sheet_file = repository.acquire_spreadsheet_file(TEST_EMPLOYEE_ID)

    # Just write dummy text in the file and save it
    DUMMY_CONTENT = "I like coffee."
    with open(sheet_file, "w") as file:
        file.write(DUMMY_CONTENT)
    repository.save_spreadsheet_file(sheet_file)

    repo_file = Path(TEST_REPOSITORY_ROOT) / TEST_SPREADSHEET_FILE
    with open(repo_file, "r") as file:
        assert file.read(len(DUMMY_CONTENT)) == DUMMY_CONTENT


def test_save_sheet_fails(repository: SheetsRepoAccessor, monkeypatch: MonkeyPatch):
    """
    Stub the `os.replace()` function to always fail and check the saving
    process results in an error.
    """

    def stub_replace(src, dst):
        logger.debug(f"Stub os.replace() called with src='{src}' and dst='{dst}'.")
        raise OSError("Stub error")

    sheet_file = repository.acquire_spreadsheet_file(TEST_EMPLOYEE_ID)

    import core.spreadsheets.sheets_repository as sheets_repo

    monkeypatch.setattr(sheets_repo.os, "replace", stub_replace)

    with pytest.raises(TimeoutError):
        repository.save_spreadsheet_file(sheet_file)


def test_release_sheet(repository: SheetsRepoAccessor):
    """
    Acquire a spreadsheet file from the repository and release it. Test
    that the lock file doesn't exist, as well as the file in the local
    cache folder.
    """
    sheet_path = repository.acquire_spreadsheet_file(TEST_EMPLOYEE_ID)
    repository.release_spreadsheet_file(sheet_path)

    repo_lock_file = Path(TEST_ASSETS_DST_FOLDER) / (
        TEST_SPREADSHEET_FILE + LOCK_FILE_EXTENSION
    )

    assert not sheet_path.exists()
    assert not repo_lock_file.exists()


def test_release_sheet_fails(repository: SheetsRepoAccessor, monkeypatch: MonkeyPatch):
    """
    Stub the `Path.unlink()` method to make the release process fails and
    check proper exception is raised by the function.
    """
    sheet_path = repository.acquire_spreadsheet_file(TEST_EMPLOYEE_ID)

    def stub_unlink(self, *args, **kwargs):
        logger.debug(f"Stub Path.unlink() called on {self}.")
        raise PermissionError("Stub permission error")

    import core.spreadsheets.sheets_repository as sheets_repo

    monkeypatch.setattr(sheets_repo.pathlib.Path, "unlink", stub_unlink)

    with pytest.raises(TimeoutError):
        repository.release_spreadsheet_file(sheet_path)


def test_list_employee(repository: SheetsRepoAccessor):
    """
    Test that the test employee ID is listed.
    """
    ids = repository.list_employee_ids()
    assert any(emp_id == TEST_EMPLOYEE_ID for emp_id in ids)
