#!/usr/bin/env python3

# Standard libraries
import pytest
import logging
import os
import datetime as dt
import shutil
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Internal libraries
from .test_constants import *
from core.spreadsheets.sheet_time_tracker_factory import SheetTimeTrackerFactory
from core.time_tracker import TimeTrackerOpenException

ALBERTO_ID = "888"
ROBERTO_ID = "999"
MARCELLO_ID = "111"


@pytest.fixture
def factory(arrange_assets: None) -> SheetTimeTrackerFactory:
    """
    Get a `SheetTimeTrackerFactory` instance for the test.
    """
    factory = SheetTimeTrackerFactory(repository_path=TEST_REPOSITORY_ROOT)
    factory._setup(TEST_REPOSITORY_ROOT)  # Make sure to reset the singleton
    return factory


def test_not_dir(arrange_assets: None):
    """
    Verify that a sheet factory cannot be created using a file as repository.
    """
    with pytest.raises(NotADirectoryError):
        SheetTimeTrackerFactory(Path(TEST_REPOSITORY_ROOT) / TEST_SPREADSHEET_FILE)


def test_list_employee_ids(factory: SheetTimeTrackerFactory):
    """
    Check that the factory returns the expected employee ids.
    """
    actual = factory.list_employee_ids()
    expected = [
        "111",  #  Marcello
        "777",  #  unit-test
        "888",  #  Alberto
        "999",  #  Roberto
        "222",  #  unit-test-error
        "333",  #  Wrong version
    ]

    assert set(actual) == set(expected)


def test_list_employee_ids_year(factory: SheetTimeTrackerFactory):
    """
    Check that the factory returns the expected employee ids for the
    year 2025.
    """
    actual = factory.list_employee_ids(filter_year=2025)
    expected = [
        "888",  #  Alberto
        "999",  #  Roberto
        # Employees in root folder are always returned
        "777",  #  unit-test
        "222",  #  unit-test-error
        "333",  #  Wrong version
    ]

    assert set(actual) == set(expected)


def test_list_employee_ids_new_year(factory: SheetTimeTrackerFactory):
    """
    Check that the factory returns the expected employee ids for a year
    that is not yet registered.
    """
    # Correct the folder name 2000 -> 2020
    os.replace(
        Path(TEST_REPOSITORY_ROOT) / "2000-error",
        Path(TEST_REPOSITORY_ROOT) / "2020-ok",
    )

    actual = factory.list_employee_ids(filter_year=dt.date(2020, 1, 1))
    expected = [
        "888",  #  Alberto
        "111",  #  Marcello
        # Employees in root folder are always returned
        "777",  #  unit-test
        "222",  #  unit-test-error
        "333",  #  Wrong version
    ]

    assert set(actual) == set(expected)


def test_alberto_tracker(factory: SheetTimeTrackerFactory):
    """
    Open the time tracker for employee '888-Alberto':
    - 2024: should work
    - 2025: should work
    - 2026: not found

    Make sure the correct tracker has been returned by checking the
    tracked year property.
    """
    with factory.create(ALBERTO_ID, 2024) as tracker:
        assert tracker.tracked_year == 2024

    with factory.create(ALBERTO_ID, 2025) as tracker:
        assert tracker.tracked_year == 2025

    with pytest.raises(TimeTrackerOpenException, match="2026"):
        factory.create(ALBERTO_ID, 2026)


def test_roberto_tracker(factory: SheetTimeTrackerFactory):
    """
    Open the time tracker for employee '888-Alberto':
    - 2024: should work
    - 2025: should work
    - 1999: not found

    Make sure the correct tracker has been returned by checking the
    tracked year property.
    """
    with factory.create(ROBERTO_ID, 2024) as tracker:
        assert tracker.tracked_year == 2024

    with factory.create(ROBERTO_ID, 2025) as tracker:
        assert tracker.tracked_year == 2025

    with pytest.raises(TimeTrackerOpenException, match="1999"):
        factory.create(ROBERTO_ID, 1999)


def test_double_marcello(factory: SheetTimeTrackerFactory):
    """
    Opening Marcello's file in the 2000 repository should return a
    TimeTrackerOpenException raised from a FileNotFoundError because two
    files have the same ID.
    """
    with pytest.raises(TimeTrackerOpenException) as excinfo:
        factory.create(MARCELLO_ID, 2000)

    # File not found -> more than one file exist for given ID
    assert isinstance(excinfo.value.__cause__, FileNotFoundError)


def test_alberto_wrong_folder(factory: SheetTimeTrackerFactory):
    """
    Open Alberto file in year folder 2000. It should result in an
    exception saying the file in the repository targets year 2020.

    Correct the repository file name from '2000-error' to '2020-ok'
    and try to reopen. The cache should automatically update and the
    opening should success.
    """
    with pytest.raises(TimeTrackerOpenException, match="Year mismatch"):
        factory.create(ALBERTO_ID, 2000)

    # Correct the folder name 2000 -> 2020
    os.replace(
        Path(TEST_REPOSITORY_ROOT) / "2000-error",
        Path(TEST_REPOSITORY_ROOT) / "2020-ok",
    )

    with factory.create(ALBERTO_ID, 2020) as tracker:
        assert tracker.tracked_year == 2020


def test_root_repo_wrong_year(factory: SheetTimeTrackerFactory):
    """
    Try to open a tracker from the root repository by specifying the
    wrong year.
    """
    with pytest.raises(TimeTrackerOpenException, match="Cannot find a file"):
        factory.create(TEST_EMPLOYEE_ID, 1969)


def test_remove_year_folder(factory: SheetTimeTrackerFactory):
    """
    Remove a year folder and verify the factory doesn't try to return
    it.
    """
    with factory.create(ALBERTO_ID, 2024) as tracker:
        assert tracker.tracked_year == 2024

    shutil.rmtree(Path(TEST_REPOSITORY_ROOT) / "2024", ignore_errors=False)

    with pytest.raises(TimeTrackerOpenException, match="2024"):
        factory.create(ALBERTO_ID, 2024)


def test_concurrent_create(factory: SheetTimeTrackerFactory):
    """
    Open multiple trackers simultaneously and verify they are opened as
    expected.
    """
    TEST_DATA = [
        (2024, ALBERTO_ID),
        (2025, ALBERTO_ID),
        (2024, ROBERTO_ID),
        (2025, ROBERTO_ID),
        (2025, TEST_EMPLOYEE_ID),
        (1969, ALBERTO_ID),  #  1969 doesn't exist and will trigger a rescan
        (1969, ALBERTO_ID),
        (1969, ALBERTO_ID),
        (1969, ALBERTO_ID),
    ]

    def create(id: str, year: int):
        if year == 1969:
            with pytest.raises(TimeTrackerOpenException):
                factory.create(id, year)
        else:
            with factory.create(id, year) as tracker:
                assert tracker.tracked_year == year

    with ThreadPoolExecutor(max_workers=10) as pool:
        pool.map(create, *zip(*((test[1], test[0]) for test in TEST_DATA)))
