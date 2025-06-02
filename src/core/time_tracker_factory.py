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
import datetime as dt
from typing import Optional
from abc import ABC, abstractmethod

# Internal libraries
from .time_tracker import BaseTimeTracker
from common.singleton_register import SingletonRegister


class TimeTrackerFactory(SingletonRegister, ABC):
    """
    Abstract factory for creating time tracker instances. The concrete
    type of the time tracker is defined by the subclass implementation.

    Each subclass of this factory are singletons.
    """

    @abstractmethod
    def create(
        self, employee_id: str, datetime: Optional[dt.datetime] = None
    ) -> BaseTimeTracker:
        """
        Create a time tracker for the given employee ID. An optional date
        and time can be provided; if omitted, the tracker may fall back
        to the last evaluated datetime or the reading functions may remain
        unavailable.

        Args:
            employee_id (str): Unique identifier for the employee.
            atetime (Optional[datetime]): The reference date and time
                for evaluating the tracker's data.

        Returns:
            BaseTimeTracker: An instance of a time tracker for the
                specified employee.

        Raises:
            TimeTrackerOpenException: Raised if the time tracker cannot
                be opened. See the underlying exception for details.
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
