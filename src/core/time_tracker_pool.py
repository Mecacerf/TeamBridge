#!/usr/bin/env python3
"""
File: time_tracker_pool.py
Author: Bastian Cerf
Date: 02/09/2025
Description:
    A pool of time tracker objects that internally manages their
    lifecycle. Useful to reuse the same time tracker multiple times
    without having to setup it again each time.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
from typing import Type, Optional
from types import TracebackType
from threading import Lock, Thread, Event
import datetime as dt
import time
import logging

# Internal libraries
from core.time_tracker import TimeTrackerAnalyzer, TimeTrackerOpenException
from core.time_tracker_factory import TimeTrackerFactory

logger = logging.getLogger(__name__)

GARBAGE_COLLECTOR_DELAY = 20.0

########################################################################
#                    Time tracker wrapper object                       #
########################################################################


class TimeTrackerWrapper:
    """Hold a pooled time tracker reference."""

    def __init__(self, tracker: TimeTrackerAnalyzer, pool: "TimeTrackerPool"):
        self._tracker = tracker
        self._pool = pool
        self._expires_at = float("inf")

    def __enter__(self) -> TimeTrackerAnalyzer:
        return self._tracker

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        if exc_type is None:
            self._expires_at = time.time() + GARBAGE_COLLECTOR_DELAY
            self._pool._release(self)
        else:
            # discard the object on error
            self._pool._discard(self)
        return False  # don’t suppress exceptions


########################################################################
#                           Time tracker pool                          #
########################################################################


class TimeTrackerPool:
    """Hold a pool of time tracker objects."""

    def __init__(self, factory: TimeTrackerFactory):
        self._factory = factory

        # Note: None is used as a flag to indicate 'in use' state
        self._pool: dict[str, Optional[TimeTrackerWrapper]] = {}
        self._lock = Lock()

        # Start garbage collector
        self._gc_thread = Thread(target=self.__gc_task, name="TimeTrackerGC")
        self._gc_run = Event()
        self._gc_run.set()
        self._gc_thread.start()

    def acquire(
        self, employee_id: str, year: int | dt.date | dt.datetime
    ) -> TimeTrackerWrapper:
        """
        Acquire a time tracker for the given employee ID and year.

        The time tracker is taken from the pool if available or created
        if not.

        If a `date` or `datetime` object is passed, only the year component
        is considered. A `TimeTrackerDateException` is raised if no tracker
        exists for that year.

        Args:
            employee_id (str): Unique identifier for the employee.
            year (int | date | datetime): Year to open the time tracker for.
            readonly (bool): Optionally specify a read-only flag.

        Returns:
            TimeTrackerWrapper: A wrapper on the time tracker.

        Raises:
            TimeTrackerOpenException: If the time tracker fails to open.
            TimeTrackerDateException: If no time tracker is found for the year.
            See chained exceptions for specific failure reasons.
        """
        if not self._gc_run.is_set():
            raise RuntimeError("Pool has been closed.")

        # Normalize year for comparison
        if isinstance(year, (dt.date, dt.datetime)):
            year = year.year

        with self._lock:
            # Check if the time tracker already exists in the pool
            if employee_id in self._pool:
                wrapper = self._pool[employee_id]
                if not wrapper:
                    raise TimeTrackerOpenException(
                        f"Tracker for '{employee_id}' is in use."
                    )
                elif wrapper._tracker.tracked_year == year:
                    self._pool[employee_id] = None
                    logger.debug(
                        f"{wrapper._tracker!s} at year {year} found in the pool."
                    )
                    return wrapper

            # The time tracker doesn't exist in the pool and must be created
            wrapper = TimeTrackerWrapper(self._factory.create(employee_id, year), self)
            self._pool[employee_id] = None
            logger.debug(f"{wrapper._tracker!s} added to the pool.")
            return wrapper

    def _release(self, wrapper: TimeTrackerWrapper):
        """
        Put back a tracker wrapper in the pool, making it available again.
        """
        with self._lock:
            assert wrapper._tracker.employee_id in self._pool
            self._pool[wrapper._tracker.employee_id] = wrapper
            logger.debug(f"{wrapper._tracker!s} released in pool.")

            # Discard immediately if the garbage collector isn't running
            if not self._gc_run.is_set():
                self._discard(wrapper)

    def _discard(self, wrapper: TimeTrackerWrapper):
        """
        Close definitely a time tracker.
        """
        with self._lock:
            desc = f"{wrapper._tracker!s}"
            try:
                wrapper._tracker.close()
            finally:
                self._pool.pop(wrapper._tracker.employee_id, None)
                logger.debug(f"{desc} discarded from pool and closed.")

    def __discard_expired(self, force: bool = False):
        """
        Iterate over available wrappers and discard expired ones.
        Set `force` to discard all available wrappers.
        """
        now = time.time()
        expired = []
        with self._lock:
            for w in list(self._pool.values()):
                if w and (w._expires_at < now or force):
                    expired.append(w)

        for w in expired:
            self._discard(w)

    def __gc_task(self):
        """
        Garbage collector task. Discard all time trackers that have
        expired.
        """
        logger.debug("Pool garbage collector started.")

        while self._gc_run.is_set():
            time.sleep(GARBAGE_COLLECTOR_DELAY / 10.0)
            self.__discard_expired()

        self.__discard_expired(force=True)
        logger.debug("Pool garbage collector terminated.")

    def close(self, wait: bool = True):
        """
        Close the pool. Optionally wait for completion.
        """
        self._gc_run.clear()
        self._gc_thread.join(10.0 if wait else 0.0)
