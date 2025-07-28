#!/usr/bin/env python3
"""
File: attendance_validator.py
Author: Bastian Cerf
Date: 09/06/2025
Description:
    Provides classes to check for attendance errors on a time tracker's
    data.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import logging
from dataclasses import dataclass, field
from abc import ABC
from enum import Enum
import datetime as dt
import time
from typing import Sequence, Iterable

# Internal libraries
from ..time_tracker import *

logger = logging.getLogger(__name__)

########################################################################
#                  Attendance error class declaration                  #
########################################################################


class AttendanceErrorStatus(Enum):
    """
    Error statuses enumeration.
    """

    NONE = auto()
    WARNING = auto()
    ERROR = auto()

    @classmethod
    def from_error_id(cls, error_id: int) -> "AttendanceErrorStatus":
        """
        Get the error status according to the given error identifier.

        Args:
            error_id (int): Error identifier.

        Returns:
            AttendanceErrorStatus: Related error status.
        """
        if error_id == 0:
            return cls.NONE
        elif error_id < 100:
            return cls.WARNING
        else:
            return cls.ERROR


@dataclass
class AttendanceError:
    """
    Attendance error data class.

    Attributes:
        error_id (int): Error identifier.
        status (AttendanceErrorStatus): Error status.
        description (str): Error description.
    """

    error_id: int
    status: AttendanceErrorStatus = field(init=False)
    description: str

    def __post_init__(self):
        self.status = AttendanceErrorStatus.from_error_id(self.error_id)

    def __str__(self) -> str:
        return f"{self.description} ({self.error_id})"


########################################################################
#                    Attendance checker base class                     #
########################################################################


class AttendanceChecker(ABC):
    """
    Responsible of checking a rule on the given data. The subclasses
    implement the rule algorithm and define the related error ID.
    """

    def __init__(self, error_id: int):
        """
        Set the error ID related to the checker.

        Args:
            error_id (int): The error ID.
        """
        self._error_id = error_id

    @property
    def error_id(self) -> int:
        """
        Returns:
            int: Related error identifier.
        """
        return self._error_id

    @abstractmethod
    def check_date(
        self,
        tracker: TimeTracker,
        date: dt.date,
        date_evts: Sequence[Optional[ClockEvent]],
    ) -> bool:
        """
        Check if the the tracker's data for the given date is valid
        according to the checker's rule.

        Args:
            tracker (TimeTracker): Time tracker to check.
            date (dt.date): Date to check.
            date_evts (Sequence[Optional[ClockEvent]]): Immutable list
                of events for the date. Same as `tracker.get_clocks(date)`.

        Returns:
            bool: `True` if the error is present, `False` if not.
        """
        pass

    def reset(self):
        """
        Reset the checker internal state. Should be called before running
        checks on a new time tracker.
        """
        pass


########################################################################
#                    Attendance validator base class                   #
########################################################################


class ErrorsReadMode(Enum):
    """
    Enumeration of the different options to retrieve time tracker's
    existing errors.
    """

    # Do not read errors, the dictionary stays empty
    NO_READ = auto()
    # Read errors in the validation range only
    VALIDATION_RANGE_ONLY = auto()
    # Read errors in the current month
    MONTH_ONLY = auto()
    # Read all errors of the year
    WHOLE_YEAR = auto()


class AttendanceValidator(ABC):
    """
    Utility class used to validate the state of a time tracker. It takes
    a list of `AttendanceChecker` that defines the rules to check when
    calling the `validate()` method. The validator stores a dictionary of
    identified errors by date for the last validated time tracker.

    See the `AttendanceValidator` implementations for pre-defined rules
    check.
    """

    def __init__(self, checkers: list[AttendanceChecker]):
        """
        Setup a validator with the provided checkers.

        Args:
            checkers (list[AttendanceValidator]): A list of checkers to
                use for validation.
        """
        self._checkers = checkers

    def validate(
        self,
        tracker: TimeTracker,
        until: dt.datetime,
        mode: ErrorsReadMode = ErrorsReadMode.MONTH_ONLY,
    ) -> AttendanceErrorStatus:
        """
        Perform a data validation of the provided time tracker until the
        given date.

        The function starts by reading existing errors in the dates range
        specified by the mode (defaults to month only). It only performs
        a new rules check if no existing critical error is found. A rules
        check always starts at the validation anchor date of the tracker
        until the given `until` date. The validation anchor date is moved
        to the first date containing a warning/error. This mechanism
        allows to rescan only a specified dates range and gives flexibility
        for HR, who can decide to manually set the anchor date after a
        manual intervention on a time tracker.

        The `dominant_error` and `date_errors` properties are available
        after the tracker validation.

        Args:
            tracker (TimeTracker): The tracker to validate. If a
                `TimeTrackerAnalyzer` is provided, its internal errors
                checks are considered and available in the output errors
                dictionary. The tracker is analyzed at `until` date but
                may be returned unanalyzed if errors have been registered.
            until (dt.datetime): The date until the data validation is
                performed. The time is only used when analyzing a
                `TimeTrackerAnalyzer`.

        Returns:
            AttendanceErrorStatus: The status of the dominant error.

        Raises:
            TimeTrackerDateException: `until` date or validation anchor
                date outside tracker's tracked year.
            TimeTrackerException: Problem with the tracker, see specific
                error and chained errors for details.
        """
        start = time.time()
        date_errors: dict[dt.date, int] = {}

        # Retrieve and check the validation anchor date
        anchor_date = tracker.get_last_validation_anchor()
        if anchor_date.year != tracker.tracked_year:
            raise TimeTrackerDateException(
                f"Wrong validation anchor date {anchor_date}, "
                f"expected year {tracker.tracked_year}."
            )

        if until.year != tracker.tracked_year:
            raise TimeTrackerDateException(
                f"Wrong `until` date {until}, expected year {tracker.tracked_year}."
            )

        # If the time tracker has analyzing capabilities, prepare the results
        # to `until` date and time.
        if isinstance(tracker, TimeTrackerAnalyzer):
            tracker.analyze(until)

        # Select the read range based on given mode
        # Don't forget that end_rng is exclusive
        if mode is not ErrorsReadMode.NO_READ:
            if mode is ErrorsReadMode.VALIDATION_RANGE_ONLY:
                start_rng = tracker.get_last_validation_anchor()
                end_rng = until
            elif mode is ErrorsReadMode.MONTH_ONLY:
                start_rng = dt.date(tracker.tracked_year, until.month, 1)
                end_rng = dt.date(tracker.tracked_year, until.month + 1, 1)
            elif mode is ErrorsReadMode.WHOLE_YEAR:
                start_rng = dt.date(tracker.tracked_year, 1, 1)
                end_rng = dt.date(tracker.tracked_year + 1, 1, 1)
            else:
                assert False, f"Unhandled mode {mode.name}."

            logger.info(
                f"{tracker!s} "
                "Selected errors reading range "
                f"[{start_rng} to {end_rng}[ (mode is {mode.name})."
            )
            dates_rng = self.__date_rng(start_rng, end_rng)

            # This read analyses a TimeTrackerAnalyzer
            self._read_existing_errors(tracker, date_errors, dates_rng)
        else:
            logger.info(f"{tracker!s} No errors read performed in {mode.name} mode.")

        # Select dominant error
        if isinstance(tracker, TimeTrackerAnalyzer):
            # The TimeTrackerAnalyzer provides the dominant error from its
            # internal analysis
            dominant_id = tracker.read_year_attendance_error()
        else:
            # The only way to determine the dominant error is to take the
            # highest error id in the read range
            dominant_id = max(date_errors.values(), default=0)

        dominant = self.__to_error(tracker, dominant_id)

        logger.info(
            f"{tracker!s} Read existing errors "
            f"returned {len(date_errors)} "
            f"error(s) and status {dominant.status.name}."
        )

        # Second step: scan for new errors
        if dominant.status is not AttendanceErrorStatus.ERROR:
            # The application can scan for new errors
            new_anchor = self._scan_range(
                tracker, date_errors, anchor_date, until.date()
            )
            if new_anchor:
                # Update the new validation anchor date and save the
                # modifications (new errors + anchor date)
                tracker.set_last_validation_anchor(new_anchor)
                tracker.save()

                # Update the dominant error that may have increased after a scan
                dominant_id = max(date_errors.values(), default=0)
                dominant_id = max(dominant_id, dominant.error_id)
                dominant = self.__to_error(tracker, dominant_id)

                until_incl = until.date() - dt.timedelta(days=1)
                scanned_days = (until.date() - anchor_date).days
                if scanned_days == 1:
                    logger.info(
                        f"{tracker!s} Scanned the {anchor_date} for errors. "
                        f"Validation anchor date set the {new_anchor}."
                    )
                else:
                    logger.info(
                        f"{tracker!s} Scanned from the {anchor_date} to "
                        f"the {until_incl} ({scanned_days} days) for errors. "
                        f"Validation anchor date set the {new_anchor}."
                    )
        else:
            logger.info(
                f"{tracker!s} Cannot scan for errors, already in "
                f"{dominant.status.name} state."
            )

        # Save validation results
        self._dominant_error = dominant
        self._date_errors = {
            edt: self.__to_error(tracker, eid) for edt, eid in date_errors.items()
        }

        elapsed = (time.time() - start) * 1000

        logger.info(
            f"{tracker!s} Finished attendance validation "
            f"with {len(self._date_errors)} error(s) and status "
            f"{dominant.status.name} in {elapsed:.0f} ms."
        )

        if dominant.error_id > 0:
            logger.info(f"{tracker!s} Most critical error is '{dominant}'.")

        if len(date_errors) > 0:
            logger.info(
                f"{tracker!s} Found errors [{", ".join([
                    f"{edt}: {eid!s}" for edt, eid in self._date_errors.items()
                ])}]."
            )

        return dominant.status

    def __date_rng(
        self, start: dt.date, end: dt.date | dt.datetime
    ) -> Iterable[dt.date]:
        """
        Iterate over the dates range [start, end[. Iteration stops the
        date before `end` (`end` exclusive).
        """
        one_day = dt.timedelta(days=1)

        if isinstance(end, dt.datetime):
            end = end.date()

        return [start + i * one_day for i in range((end - start).days)]

    def __to_error(self, tracker: TimeTracker, error_id: int) -> AttendanceError:
        """
        Returns:
            AttendanceError: An attendance error object based on the
                given error identifier.
        """
        desc = "unknown error"
        try:
            desc = tracker.get_attendance_error_desc(error_id)
        except TimeTrackerValueException:
            pass

        return AttendanceError(error_id, desc)

    def _read_existing_errors(
        self,
        tracker: TimeTracker,
        date_errors: dict[dt.date, int],
        dates_rng: Iterable[dt.date],
    ):
        """
        Read the errors that already exist in the time tracker for the
        given dates range. If a `TimeTracker` is provided, only application
        errors are read. If a `TimeTrackerAnalyzer` is provided, it is
        expected to be analyzed to the end date of `dates_rng` and internal
        errors are also read.

        The function fills the provided `date_errors` dictionary with all
        errors greater than 0.
        """
        start = time.time()

        # Read existing errors from the tracker, if it has analyzing capabilities
        if isinstance(tracker, TimeTrackerAnalyzer):
            assert tracker.analyzed
            # Check the global error id, if 0 there is no tracker errors
            # neither application errors to read. The iteration can be
            # stopped.
            if tracker.read_year_attendance_error() == 0:
                logger.debug(
                    f"{tracker!s} Errors iteration stopped early because the "
                    f"{tracker.__class__.__name__} reported no dominant error."
                )
                return

            for date in dates_rng:
                if (error := tracker.read_day_attendance_error(date)) > 0:
                    date_errors[date] = max(date_errors.get(date, 0), error)

        # Read existing errors from the application
        for date in dates_rng:
            if (error := tracker.get_attendance_error(date)) > 0:
                # Merge with existing errors
                date_errors[date] = max(date_errors.get(date, 0), error)

        elapsed = (time.time() - start) * 1000
        logger.debug(
            f"{tracker!s} Read existing error(s) in {elapsed:.0f} ms. "
            "Results: "
            f"[{", ".join(str(err) for err in date_errors.values())}] "
        )

    def _scan_range(
        self,
        tracker: TimeTracker,
        date_errors: dict[dt.date, int],
        start_rng: dt.date,
        end_rng: dt.date,
    ) -> Optional[dt.date]:
        """
        Scan day-by-day to find errors from the `start_rng` date to
        `end_rng` (exclusive). Each `AttendanceChecker` is tested on each
        day of the range and the highest error is sorted. This error is
        added to the `date_errors` dictionary and written in the tracker's
        application errors. The first day in error found in the range is
        returned, or `end_rng` is returned if no error is found. The
        returned value is `None` if the range is empty (start_rng >= end_rng).
        """
        start = time.time()

        # Reset the checkers to their initial state
        for checker in self._checkers:
            checker.reset()

        new_anchor_date = None
        errors: list[int] = []
        for date in self.__date_rng(start_rng, end_rng):
            # Apply each checker on the date and get the highest error
            # returned
            date_evts = tracker.get_clocks(date)  # Called once before checks
            error = max(
                [
                    checker.error_id
                    for checker in self._checkers
                    if checker.check_date(tracker, date, date_evts)
                ],
                default=0,
            )

            if error > 0:
                # The validation anchor is moved to the first date in error
                if new_anchor_date is None:
                    new_anchor_date = date

                # Write in the tracker and merge with existing errors
                tracker.set_attendance_error(date, error)
                date_errors[date] = max(date_errors.get(date, 0), error)
                errors.append(error)

        if "date" not in locals():
            # Iterable was empty -> nothing scanned and anchor didn't move
            logger.debug(f"{tracker!s} Validation range is empty. No scan performed.")
            return None

        # Move the validation anchor to the new anchor date if set, or to the
        # next day to scan if no error found
        new_anchor_date = new_anchor_date or end_rng

        elapsed = (time.time() - start) * 1000
        logger.debug(
            f"{tracker!s} Scanned for errors in {elapsed:.0f} ms. "
            f"Results: [{", ".join(str(err) for err in errors)}]."
        )

        return new_anchor_date

    @property
    def dominant_error(self) -> AttendanceError:
        """
        Returns:
            Optional[AttendanceError]: The dominant error (most critical).

        Raises:
            RuntimeError: No validation result available.
        """
        if not hasattr(self, "_dominant_error"):
            raise RuntimeError("No validation result available.")

        return self._dominant_error

    @property
    def date_errors(self) -> dict[dt.date, AttendanceError]:
        """
        Returns:
            Optional[dict[dt.date, AttendanceError]]: A dictionary of all
                errors detected by date. Depends on the selected range
                mode.

        Raises:
            RuntimeError: No validation result available.
        """
        if not hasattr(self, "_date_errors"):
            raise RuntimeError("No validation result available.")

        return self._date_errors
