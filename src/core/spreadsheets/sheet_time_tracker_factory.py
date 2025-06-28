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
import logging
from pathlib import Path
import re
import threading

# Internal libraries
from core.time_tracker import (
    TimeTrackerAnalyzer,
    TimeTrackerOpenException,
    TimeTrackerCloseException,
)
from core.time_tracker_factory import TimeTrackerFactory
from .sheet_time_tracker import SheetTimeTracker
from .sheets_repository import SheetsRepoAccessor

logger = logging.getLogger(__name__)

# Extract the year from a folder name by matching a sequence of four digits
SUBDIR_NAME_REGEX = r"(?<!\d)(\d{4})(?!\d)"


class SheetTimeTrackerFactory(TimeTrackerFactory):
    """
    Concrete implementation of the abstract factory defined in
    `time_tracker_factory.py`. This implementation builds
    `SheetTimeTracker` instances.

    The repository folder path is the root folder in which spreadsheet
    files are searched. This folder can be organized in many subfolders
    each corresponding to a specific year. The year is identified by
    four digits at any place in the directory name. Subfolders that
    doesn't match the regex (no year or more than one year) are not
    considered.
    If a time tracker for a given employee ID is not found in the year
    folder, the factory defaults by searching it in the repositoy root
    before raising an error if not found.
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
        self._repo_root = Path(repository_path)
        if not self._repo_root.is_dir():
            raise RuntimeError(f"{repository_path} is not a folder.")

        # Default root accessor
        self._root_accessor = self.__create_accessor(self._repo_root)

        self._scan_lock = threading.Lock()
        self._scan_ready = threading.Event()
        self._scan_ready.set()

        # Placeholder for the sorted accessors: year -> accessor
        self._year_accessors: dict[int, SheetsRepoAccessor] = {}
        self.__scan_once()

    def __scan_once(self):
        """
        Ensure proper synchronization if multiple threads are trying to
        scan the repository simultaneously.
        """
        # If scan ready is set, no thread is currently scanning
        if self._scan_ready.is_set():
            with self._scan_lock:
                if self._scan_ready.is_set():  # Double check in lock
                    # This is the very first thread that needs to perform a
                    # scan
                    self._scan_ready.clear()
                    try:
                        self.__scan_repo()
                    finally:
                        self._scan_ready.set()
                    return

        # Another thread is scanning, just wait for it to finish
        self._scan_ready.wait()

    def __scan_repo(self):
        """
        Scan the repository subfolders (only first level) and search for
        year folders. Update the accessors list by creating new accessors
        for new entries and remove old accessors for missing entries.
        """
        # Discover all folders at the first level
        subfolders: list[Path] = [
            sub
            for sub in self._repo_root.iterdir()
            if sub.is_dir() and not sub.name.startswith((".", ".."))
        ]

        # Match subfolders by year regex
        year_folders: dict[int, Path] = {}
        for folder in subfolders:
            matches = re.findall(SUBDIR_NAME_REGEX, folder.name)

            if len(matches) == 1:
                # Name contains a valid year
                year = int(matches[0])
                if year in year_folders:
                    logger.error(f"More than one folder exists for year {year}.")
                else:
                    year_folders[int(matches[0])] = folder

            elif len(matches) > 1:
                logger.warning(
                    f"Ignored subfolder '{folder.name}': cannot identify the "
                    "year (multiple matches)."
                )
            else:
                logger.debug(f"Ignored subfolder '{folder.name}': no year match.")

        old_years = set(self._year_accessors.keys())
        new_years = set(year_folders.keys())

        # Update the dictionary with the accessors for the discovered year folders
        self._year_accessors = {
            year: (
                self._year_accessors[year]
                if year in self._year_accessors
                else self.__create_accessor(path)
            )
            for year, path in year_folders.items()
        }

        # Warning about removed accessors
        for rem_year in old_years - new_years:
            logger.warning(f"Removed year {rem_year}: folder no longer found.")

        years = list(self._year_accessors.keys())
        logger.info(
            f"Repository scan returned {len(years)} entries: {
                ", ".join([str(year) for year in years])
            }."
        )

    def __create_accessor(self, folder: Path):
        return SheetsRepoAccessor(remote_repository=str(folder.resolve()))

    def _create(
        self, employee_id: str, year: int, readonly: bool, may_rescan: bool = True
    ) -> TimeTrackerAnalyzer:
        """
        Create and return a time tracker instance for a given employee and year.

        Logic:
        1. If the year is already known (cached in self._year_accessors),
        try to access the corresponding folder and check if the employee
        ID is listed. If so, return a SheetTimeTracker for that employee
        and year.
        2. If the year is not yet cached or the employee ID is not found,
        and if `may_rescan` is True, perform a repository rescan to refresh
        year mappings and retry step 1 (without rescanning again).
        3. If the employee ID is still not found, check the fallback "root"
        accessor. If found, return a SheetTimeTracker using the root accessor.
        4. If the employee ID is not found in any valid location, raise
        an exception.

        Args:
            employee_id (str): Unique identifier for the employee.
            year (int): Year to look up the employee's data.
            readonly (bool): Whether to open the tracker in readonly mode.
            may_rescan (bool): Whether to perform a repository rescan if
                data is missing (internal use).

        Returns:
            TimeTrackerAnalyzer: A tracker object for the given employee
                and year.

        Raises:
            TimeTrackerOpenException: If no valid tracker can be found for
                the given inputs or the opening failed.
            See chained exceptions for details.
        """
        # Step 1: year is registered in accessors cache
        if year in self._year_accessors:
            accessor = self._year_accessors[year]  #  Read is atomic

            # Attempt to create a time tracker only if ID is listed
            if employee_id in accessor.list_employee_ids():
                tracker = SheetTimeTracker(
                    employee_id, accessor=accessor, readonly=readonly
                )

                # Sanity check tracked year
                tracked_year = tracker.tracked_year
                if tracked_year != year:

                    cause = None
                    try:
                        tracker.close()
                    except TimeTrackerCloseException as e:
                        cause = e

                    raise TimeTrackerOpenException(
                        f"Year mismatch: a tracker for employee '{employee_id}' "
                        f"in year {tracked_year} "
                        f"was found in the folder targeting year {year}."
                    ) from cause  # The cause shows if the closing failed

                return tracker

        # Step 2: year not registered or missing entry for given ID
        # Try to perform a repository scan if allowed
        if may_rescan:
            logger.debug(
                f"Accessor for employee '{employee_id}' at year {year} not found. "
                "Try to update the cache..."
            )

            self.__scan_once()
            # Retry the case 1
            return self._create(employee_id, year, readonly, may_rescan=False)

        # Step 3: try to search in the root accessor
        logger.debug(
            f"Last attempt to find employee '{employee_id}' at year {year} "
            "in root repository..."
        )

        if employee_id in self._root_accessor.list_employee_ids():
            return SheetTimeTracker(
                employee_id, accessor=self._root_accessor, readonly=readonly
            )

        raise TimeTrackerOpenException(
            f"Cannot find a file for employee '{employee_id}' at year {year}."
        )

    def list_employee_ids(self) -> list[str]:
        """
        Return a deduplicated list of all employee IDs found across
        all unsorted repository accessors.
        """
        accessors: list[SheetsRepoAccessor] = [self._root_accessor] + list(
            self._year_accessors.values()
        )

        ids: set[str] = set()
        for accessor in accessors:
            ids.update(accessor.list_employee_ids())
        return sorted(ids)  # Return ids in a predictable order
