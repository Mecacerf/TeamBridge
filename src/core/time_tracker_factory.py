#!/usr/bin/env python3
"""
File: time_tracker_factory.py
Author: Bastian Cerf
Date: 17/05/2025
Description:
    Abstract factory for creating time tracker instances. The concrete
    type of the time tracker is defined by the subclass implementation.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
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
        self, employee_id: str, year: int | dt.date | dt.datetime
    ) -> TimeTrackerAnalyzer:
        """
        Create a time tracker for the given employee ID and year.

        If a `date` or `datetime` object is passed, only the year component
        is considered. A `TimeTrackerDateException` is raised if no tracker 
        exists for that year.

        Args:
            employee_id (str): Unique identifier for the employee.
            year (int | date | datetime): Year to open the time tracker for.

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
            return self._create(employee_id, year)
        except (TimeTrackerOpenException, TimeTrackerDateException):
            raise
        except Exception as e:
            raise TimeTrackerOpenException() from e

    @abstractmethod
    def _create(self, employee_id: str, year: int) -> TimeTrackerAnalyzer:
        """
        Must be implemented by subclasses to create the time tracker.
        """
        pass

    @abstractmethod
    def list_employee_ids(self) -> list[str]:
        """
        List all employee IDs registered in the system.

        Returns:
            list[str]: A list of employee identifiers.
        """
        pass
