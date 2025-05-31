#!/usr/bin/env python3
"""
File: sheet_time_tracker_factory.py
Author: Bastian Cerf
Date: 17/05/2025
Description:
    Concrete implementation of the abstract factory defined in
    `time_tracker_factory.py`. This implementation builds
    `SheetTimeTracker` instances.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import datetime as dt
from typing import Optional

# Internal libraries
from core.time_tracker import BaseTimeTracker
from core.time_tracker_factory import TimeTrackerFactory
from .sheet_time_tracker import SheetTimeTracker
from .sheets_repository import SheetsRepoAccessor


class SheetTimeTrackerFactory(TimeTrackerFactory):
    """
    Concrete implementation of the abstract factory defined in
    `time_tracker_factory.py`. This implementation builds
    `SheetTimeTracker` instances.
    """

    def __init__(self, repository_path: str):
        """
        Initialize the factory.

        Args:
            repository_path (str): Path to the spreadsheets repository.
        """
        # Create the internal repository accessor
        self._repo_accessor = SheetsRepoAccessor(
            remote_repository=repository_path
        )

    def create(
        self, employee_id: str, datetime: Optional[dt.datetime] = None
    ) -> BaseTimeTracker:
        # Inject the common repository accessor 
        return SheetTimeTracker(employee_id, datetime, self._repo_accessor)

    def list_employee_ids(self) -> list[str]:
        return self._repo_accessor.list_employee_ids()
