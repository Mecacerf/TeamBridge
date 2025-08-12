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
import datetime as dt
from typing import Optional

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
            NotADirectoryError: If the provided path is not a directory.
        """
        self._repo_root = Path(repository_path)
        if not self._repo_root.is_dir():
            raise NotADirectoryError(f"{repository_path} is not a directory.")

        # Default root accessor
        self._root_accessor = self.__create_accessor(self._repo_root)

        # Repository scan lock and flag
        self._scan_lock = threading.Lock()
        self._scan_ready = threading.Event()
        self._scan_ready.set()

        # Placeholder for the sorted accessors: year -> accessor
        self._year_accessors: dict[int, SheetsRepoAccessor] = {}
        self.__scan_once()

    def __create_accessor(self, folder: Path):
        return SheetsRepoAccessor(remote_repository=str(folder.resolve()))

    def __scan_once(self):
        """
        Ensure proper synchronization if multiple threads are trying to
        scan the repository simultaneously.
        """
        if self._scan_ready.is_set():
            # Try to be the one who scans
            if self._scan_lock.acquire(blocking=False):
                try:
                    logger.info(
                        "Starting repository "
                        f"'{self._root_accessor.remote_repository}' scan "
                        f"on thread '{threading.current_thread().name}'."
                    )

                    self._scan_ready.clear()
                    try:
                        self.__scan_repo()
                    finally:
                        self._scan_ready.set()
                finally:
                    self._scan_lock.release()

                return

        # Another thread is scanning, just wait for it to complete
        logger.debug(
            f"Thread {threading.current_thread().name} is waiting "
            "for repository scan to be complete."
        )
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

    def __select_accessor(self, year: Optional[int]) -> Optional[SheetsRepoAccessor]:
        """
        Select the accessor for the specified year or the root accessor
        if year is `None`.

        If no accessor exists for the specified year, a repository scan
        is performed to check if the folders structure has changed. A new
        accessor may therefore be registered dynamically.

        When an accessor is found for the specified year, its availability
        is checked before it is returned. This mechanism ensures the
        accessor can be safely used. When the availability check fails,
        a repository scan is also performed to update the folders
        structure, which allows to dynamically remove an accessor for a
        deleted folder.

        Args:
            year (Optional[int]): Target year or `None` to select the root.

        Returns:
            Optional[SheetsRepoAccessor]: Selected accessor or `None` if
                not found / unavailable.
        """
        accessor: Optional[SheetsRepoAccessor] = None

        if year is None:
            accessor = self._root_accessor
        elif year in self._year_accessors:
            accessor = self._year_accessors[year]
        else:
            logger.debug(f"No accessor registered for year {year}.")
            self.__scan_once()
            accessor = self._year_accessors.get(year, None)

        if accessor is None:
            return None

        if accessor.check_repo_available():
            return accessor

        logger.debug(
            f"The remote repository '{accessor.remote_repository}' seems unavailable."
        )
        self.__scan_once()

        # The rescan does not change anything to accessor's availability. It
        # only allows to remove it from the cache if the folder no longer exists.
        return None

    def __create_tracker(
        self,
        accessor: SheetsRepoAccessor,
        employee_id: str,
        year: int,
        readonly: bool,
        strict: bool = True,
    ) -> Optional[SheetTimeTracker]:
        """
        Create a `SheetTimeTracker` safely.

        The `tracked_year` of the tracker is checked to ensure it matches
        the expected year. This mechanism prevents user errors, where
        a file has been placed in a wrong folder (thus attributed to the
        wrong accessor).

        When `strict` is `True`, a year mismatch raises an exception.
        When not set, `None` is returned without exception.

        Args:
            accessor (SheetsRepoAccessor): Accessor to use to open the file.
            employee_id (str): Employee's tracker id.
            year (int): Expected accessor's year.
            readonly (bool): Whether the tracker must be opened in read-only
                mode.
            strict (bool): Whether to raise an exception on year mismatch.

        Returns:
            Optional[SheetTimeTracker]: Created tracker or `None` if year
                mismatches and `strict` is `True`.

        Raises:
            TimeTrackerOpenException: Raised on year mismatch when
                `strict` is `True`.
        """
        logger.debug(
            f"Creating a {SheetTimeTracker.__name__} for employee "
            f"ID '{employee_id}' (readonly={readonly}). "
            f"Accessor path is '{accessor.remote_repository}'."
        )
        
        tracker = SheetTimeTracker(employee_id, accessor=accessor, readonly=readonly)

        # Sanity check tracked year
        tracked_year = tracker.tracked_year
        if tracked_year == year:
            return tracker

        cause = None
        try:
            tracker.close()
        except TimeTrackerCloseException as e:
            cause = e

        if not strict and cause is None:
            return None

        raise TimeTrackerOpenException(
            f"Year mismatch: a tracker for employee '{employee_id}' "
            f"in year {tracked_year} "
            f"was found in the folder targeting year {year}."
        ) from cause  # The cause shows if the closing failed

    def _create(
        self, employee_id: str, year: int, readonly: bool, root_search: bool = False
    ) -> TimeTrackerAnalyzer:
        """
        Create and return a time tracker instance for a given employee
        and year.

        The repository indexing is updated dynamically if year folders
        are added or removed during runtime. The function starts by
        searching in the year folders and fallbacks to the root repository
        if no tracker is found. The `tracked_year` property of the tracker
        is always compared to the given year to ensure no user error
        exists.

        Args:
            employee_id (str): Unique identifier for the employee.
            year (int): Year to look up the employee's data.
            readonly (bool): Whether to open the tracker in readonly mode.
            root_search (bool): Whether to search in the year folders or
                in the root repository.

        Returns:
            TimeTrackerAnalyzer: A tracker object for the given employee
                and year.

        Raises:
            TimeTrackerOpenException: If no valid tracker can be found for
                the given inputs or the opening failed.
            See chained exceptions for details.
        """
        accessor = self.__select_accessor(None if root_search else year)

        # Attempt to create a time tracker only if ID is listed
        if accessor is not None and employee_id in accessor.list_employee_ids():
            # If searching in the root repo, strict is False to allow years
            # mixing
            tracker = self.__create_tracker(
                accessor, employee_id, year, readonly, strict=not root_search
            )
            if tracker is not None:
                return tracker

        # Recursive call in root folder if nothing found in year folders
        if not root_search:
            logger.debug(
                f"Search employee '{employee_id}' at year {year} "
                "in root repository..."
            )
            return self._create(employee_id, year, readonly, root_search=True)

        raise TimeTrackerOpenException(
            f"Cannot find a file for employee '{employee_id}' at year {year}."
        )

    def list_employee_ids(
        self, filter_year: int | dt.date | dt.datetime | None = None
    ) -> list[str]:
        """
        List registered employee ids for the given year. If `filter_year`
        is `None`, all employee ids are listed. Employee ids from the
        root folder are always listed.

        This call may trigger a repository scan if `filter_year` is not
        indexed.
        """
        if isinstance(filter_year, (dt.date, dt.datetime)):
            filter_year = filter_year.year

        selected_years: list[int | None] = [None]
        if filter_year is None:
            # No year filter, select all years
            selected_years += list(self._year_accessors.keys())
        elif isinstance(filter_year, int):
            # Select targeted accessor
            selected_years += [filter_year]
        else:
            assert False, f"filter_year is {type(filter_year)}: {filter_year}."

        ids: set[str] = set()
        for year in selected_years:
            accessor = self.__select_accessor(year)
            if accessor is not None:
                ids.update(accessor.list_employee_ids())

        return sorted(ids)  # Return ids in a predictable order
