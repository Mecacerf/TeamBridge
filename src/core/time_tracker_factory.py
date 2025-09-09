#!/usr/bin/env python3
"""
Abstract factory for creating time tracker instances. The concrete
type of the time tracker is defined by the subclass implementation.

---
TeamBridge - An open-source timestamping application

Author: Bastian Cerf
Copyright (C) 2025 Mecacerf SA
License: AGPL-3.0 <https://www.gnu.org/licenses/>
"""

# Standard libraries
from abc import ABC, abstractmethod
import datetime as dt

# Internal libraries
from .time_tracker import (
    TimeTrackerAnalyzer,
    TimeTrackerOpenException,
    TimeTrackerDateException,
)
from common.singleton_register import SingletonRegister


class TimeTrackerFactory(SingletonRegister, ABC):
    """
    Abstract factory for creating time tracker instances. The concrete
    type of the time tracker is defined by the subclass implementation.

    Each subclass of this factory are singletons.
    """

    def create(
        self,
        employee_id: str,
        year: int | dt.date | dt.datetime,
        readonly: bool = False,
    ) -> TimeTrackerAnalyzer:
        """
        Create a time tracker for the given employee ID and year.

        If a `date` or `datetime` object is passed, only the year component
        is considered. A `TimeTrackerDateException` is raised if no tracker
        exists for that year.

        The `readonly` argument can optionally be specified. Depending on
        the implementation in use, it may return a time tracker with only
        reading capabilities.

        Args:
            employee_id (str): Unique identifier for the employee.
            year (int | date | datetime): Year to open the time tracker for.
            readonly (bool): Optionally specify a read-only flag.

        Returns:
            TimeTrackerAnalyzer: The time tracker instance for the employee.

        Raises:
            TimeTrackerOpenException: If the time tracker fails to open.
            TimeTrackerDateException: If no time tracker is found for the year.
            See chained exceptions for specific failure reasons.
        """
        if isinstance(year, (dt.date, dt.datetime)):
            year = year.year

        try:
            return self._create(employee_id, year, readonly)
        except (TimeTrackerOpenException, TimeTrackerDateException):
            raise
        except Exception as e:
            raise TimeTrackerOpenException() from e

    @abstractmethod
    def _create(
        self, employee_id: str, year: int, readonly: bool
    ) -> TimeTrackerAnalyzer:
        """
        Must be implemented by subclasses to create the time tracker.
        """
        pass

    @abstractmethod
    def list_employee_ids(
        self, filter_year: int | dt.date | dt.datetime | None = None
    ) -> list[str]:
        """
        List all employee IDs registered in the system.

        Returns:
            list[str]: A list of employee identifiers.
        """
        pass
