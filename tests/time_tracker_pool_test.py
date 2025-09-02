#!/usr/bin/env python3
"""
File: time_tracker_pool_test.py
Author: Bastian Cerf
Date: 02/09/2025
Description:
    Unit test the time tracker pool module.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard library
from datetime import date, datetime
import pytest
from typing import cast
import threading
import time
import datetime as dt

# Internal libraries
from core.time_tracker import (
    TimeTrackerAnalyzer,
    TimeTrackerOpenException,
    TimeTrackerReadException,
)
from core.time_tracker_pool import TimeTrackerPool
from core.time_tracker_factory import TimeTrackerFactory


TEST_ID = "test123"
TEST_YEAR = 2025


class StubTracker:

    def __init__(self, id: str, year: int, tracker_id: int) -> None:
        self._employee_id = id
        self._year = year
        self._tracker_id = tracker_id
        self.closed = False

    @property
    def employee_id(self) -> str:
        return self._employee_id

    @property
    def tracked_year(self) -> int:
        return self._year

    def read_day_balance(self, date: dt.date):
        raise TimeTrackerReadException()

    def close(self):
        self.closed = True

    def __str__(self) -> str:
        return f"StubTracker[id={self._employee_id}, year={self._year}, tracker_id={self._tracker_id}]"

    def __eq__(self, value: object) -> bool:
        if isinstance(value, StubTracker):
            return self._tracker_id == value._tracker_id
        return False


class StubFactory(TimeTrackerFactory):

    def _setup(self):
        self._tracker_id = 0
        self._lock = threading.Lock()

    def _create(
        self, employee_id: str, year: int, readonly: bool
    ) -> TimeTrackerAnalyzer:
        with self._lock:
            self._tracker_id += 1
            return cast(
                TimeTrackerAnalyzer,
                StubTracker(employee_id, year, self._tracker_id),
            )

    def list_employee_ids(
        self, filter_year: int | date | datetime | None = None
    ) -> list[str]:
        return []


@pytest.fixture
def factory() -> TimeTrackerFactory:
    """
    Get a stub tracker factory.
    """
    return StubFactory()


@pytest.fixture
def pool(factory: TimeTrackerFactory):
    """
    Get a time tracker pool with high rate garbage collector (to make
    testing faster). Time trackers are collected after 500ms.
    """
    pool = TimeTrackerPool(factory, gc_delay=0.5)
    yield pool
    pool.close()


def test_tracker_reuse(pool: TimeTrackerPool):
    """
    Check that the same time tracker is reused within multiple
    context manager blocks.
    """
    tracker = None
    with pool.acquire(TEST_ID, TEST_YEAR) as tracker:
        pass

    with pool.acquire(TEST_ID, TEST_YEAR) as context:
        assert tracker == context

    with pool.acquire(TEST_ID, TEST_YEAR + 1) as context:
        assert tracker != context


def test_tracker_close(pool: TimeTrackerPool):
    """
    Check the garbage collector closes the tracker after no usage.
    """
    tracker = None
    with pool.acquire(TEST_ID, TEST_YEAR) as tracker:
        pass

    time.sleep(0.7)  # Wait for the GC to collect the staging tracker
    assert cast(StubTracker, tracker).closed


def test_pool_close(pool: TimeTrackerPool):
    """
    Close the pool and verifies all trackers are closed.
    """
    # Add a staging tracker
    with pool.acquire(TEST_ID, TEST_YEAR) as current:
        tracker1 = current

    # Create another tracker
    with pool.acquire(TEST_ID, TEST_YEAR + 1) as current:
        tracker2 = current

        pool.close(wait=True)
        assert cast(StubTracker, tracker1).closed  # Staging tracker closed

        # In use tracker cannot be closed until release
        assert not cast(StubTracker, current).closed
    assert cast(StubTracker, tracker2).closed


def test_tracker_in_use(pool: TimeTrackerPool):
    """
    Check that a tracker in use is unavailable.
    """
    with pool.acquire(TEST_ID, TEST_YEAR):
        with pytest.raises(TimeTrackerOpenException):
            with pool.acquire(TEST_ID, TEST_YEAR):
                pass


def test_closed_pool(pool: TimeTrackerPool):
    pool.close()
    with pytest.raises(RuntimeError):
        pool.acquire(TEST_ID, TEST_YEAR)


def test_context_manager_error(pool: TimeTrackerPool):
    """
    Check that the time tracker is closed if an error occurs in the
    context manager block.
    """
    date = dt.date(year=TEST_YEAR, day=1, month=1)

    tracker = None
    with pytest.raises(TimeTrackerReadException):
        with pool.acquire(TEST_ID, date) as tracker:
            tracker.read_day_balance(date)

    assert cast(StubTracker, tracker).closed
