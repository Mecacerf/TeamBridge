#!/usr/bin/env python3
"""
File: time_tracker_factory.py
Author: Bastian Cerf
Date: 17/05/2025
Description: 
    Abstract factory for creating time tracker instances. The concrete type
    of the time tracker is defined by the subclass implementation.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import datetime as dt
from typing import Optional
from abc import ABC, abstractmethod

# Internal libraries
from .time_tracker import BaseTimeTracker

class TimeTrackerFactory(ABC):
    """
    Abstract factory for creating time tracker instances. The concrete type
    of the time tracker is defined by the subclass implementation.
    """

    @abstractmethod
    def create(self, employee_id: str, 
               date: Optional[dt.date] = None) -> BaseTimeTracker:
        """
        Create a time tracker for the given employee ID. An optional date can
        be provided; if omitted, a default such as January 1st may be used,
        depending on the implementation.

        Args:
            employee_id (str): Unique identifier for the employee.
            date (Optional[datetime.date]): Optional current date pointer. Defaults
                to first of January.

        Returns:
            BaseTimeTracker: An instance of a time tracker for the specified employee.

        Raises:
            TimeTrackerOpenException: Raised if the time tracker cannot be opened.
                See the underlying exception for details.
        """
        pass

    @abstractmethod
    def list_employee_ids(self) -> list[str]:
        """
        List all registered employee IDs.

        Returns:
            list[str]: A list of employee identifiers.
        """
        pass
