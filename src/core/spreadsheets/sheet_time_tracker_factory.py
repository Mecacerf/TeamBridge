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
from pathlib import Path

# Internal libraries
from core.time_tracker import TimeTrackerAnalyzer, TimeTrackerDateException
from core.time_tracker_factory import TimeTrackerFactory
from .sheet_time_tracker import SheetTimeTracker
from .sheets_repository import SheetsRepoAccessor


class SheetTimeTrackerFactory(TimeTrackerFactory):
    """
    Concrete implementation of the abstract factory defined in
    `time_tracker_factory.py`. This implementation builds
    `SheetTimeTracker` instances.

    The repository folder path is the root folder in which spreadsheet
    files are searched. This folder can be organized in many subfolders
    each corresponding to a specific year. The factory will dynamically
    search in the subfolders and determine the year they relate to.
    """

    def _setup(self, repository_path: str):
        """
        Initialize the factory at the given repository root folder.

        Args:
            repository_path (str): Path to the root folder of the
                spreadsheets repository.

        Raises:
            RuntimeError: If the provided path is not a directory.
        """
        root = Path(repository_path)
        if not root.is_dir():
            raise RuntimeError(f"{repository_path} is not a folder.")

        # Discover all folders at the first level (root and its subfolders)
        look_folders: list[Path] = [root] + [
            sub for sub in root.iterdir() if sub.is_dir()
        ]

        # Create the unsorted list of repository accessors
        self._unsorted_accessors = [
            SheetsRepoAccessor(str(path.resolve())) for path in look_folders
        ]

        # Placeholder for the sorted accessors: year -> accessor
        self._sorted_accessors: dict[int, SheetsRepoAccessor] = {}

    def _create(
        self, employee_id: str, year: int, readonly: bool
    ) -> TimeTrackerAnalyzer:
        """
        Search, create, and return the time tracker for the specified
        employee and year.

        This first attempts to use a sorted accessor if available.
        Otherwise, it searches through the unsorted accessors, validates
        the year, and caches the accessor if matched.

        Raises:
            TimeTrackerDateException: If the employee's file is missing
                or if the tracked year doesn't match the expected year.
        """
        # Case 1: accessor for the year already known
        if year in self._sorted_accessors:
            accessor = self._sorted_accessors[year]
            try:
                tracker = SheetTimeTracker(
                    employee_id, accessor=accessor, readonly=readonly
                )
            except FileNotFoundError:
                raise TimeTrackerDateException(
                    f"No file found for employee '{employee_id}'"
                    f"in year folder {year} ({accessor.remote_repository})."
                )
            if tracker.tracked_year != year:
                raise TimeTrackerDateException(
                    f"Tracked year mismatch: opened {tracker.tracked_year} "
                    f"while expecting {year}. Is employee '{employee_id}' file "
                    f"in the wrong folder ? ({accessor.remote_repository})"
                )
            return tracker

        # Case 2: search among unsorted accessors
        for accessor in self._unsorted_accessors:
            if employee_id in accessor.list_employee_ids():
                try:
                    tracker = SheetTimeTracker(
                        employee_id, accessor=accessor, readonly=readonly
                    )
                except FileNotFoundError:
                    continue  # Maybe listed but file is missing; keep trying others
                if tracker.tracked_year == year:
                    # Cache the accessor for faster future access
                    self._sorted_accessors[year] = accessor
                    return tracker

        raise TimeTrackerDateException(
            f"Cannot find a file for employee '{employee_id}' in year {year}."
        )

    def list_employee_ids(self) -> list[str]:
        """
        Return a deduplicated list of all employee IDs found across
        all unsorted repository accessors.
        """
        ids: set[str] = set()
        for accessor in self._unsorted_accessors:
            ids.update(accessor.list_employee_ids())
        return sorted(ids)  # Return ids in a predictable order
