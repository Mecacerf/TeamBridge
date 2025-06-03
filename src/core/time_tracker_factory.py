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
        Create a time tracker for the given employee ID. The time tracker
        is opened for the given year. A `TimeTrackerDateException` is
        raised if no time tracker can be opened for that year.

        Args:
            employee_id (str): Unique identifier for the employee.
            year (int | dt.date | dt.datetime): Tracked year of the time
                tracker.

        Returns:
            TimeTrackerAnalyzer: An instance of a time tracker for the
                specified employee.

        Raises:
            TimeTrackerOpenException: Raised if the time tracker cannot
                be opened.
            TimeTrackerDateException: Raised if no time tracker can be
                opened for the specified year.
        """
        if isinstance(year, dt.date) or isinstance(year, dt.datetime):
            year = year.year

        try:
            return self._create(employee_id, year)
        except Exception as e:
            if isinstance(e, TimeTrackerOpenException) or isinstance(
                e, TimeTrackerDateException
            ):
                raise e
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
