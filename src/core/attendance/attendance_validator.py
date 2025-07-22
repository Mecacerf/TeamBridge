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
    def check_date(self, tracker: TimeTracker, date: dt.date) -> bool:
        """
        Check if the the tracker's data for the given date is valid
        according to the checker's rule.

        Args:
            tracker (TimeTracker): Time tracker to check.
            date (dt.date): Date to check.

        Returns:
            bool: `True` if the error is present, `False` if not.
        """
        pass


########################################################################
#                    Attendance validator base class                   #
########################################################################


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

        self._worse_error = None
        self._date_errors = None

    def __date_rng(self, start: dt.date, end: dt.date | dt.datetime):
        """
        Iterate over the dates range [start, end[. Iteration stops the
        date before `end` (`end` exclusive).
        """
        one_day = dt.timedelta(days=1)

        if isinstance(end, dt.datetime):
            end = end.date()

        date = start
        while date < end:
            yield date
            date += one_day

    def __to_error(self, tracker: TimeTracker, error_id: int) -> AttendanceError:
        """
        Returns:
            AttendanceError: An attendance error object based on the
                given error identifier.
        """
        return AttendanceError(error_id, tracker.get_attendance_error_desc(error_id))

    def validate(
        self, tracker: TimeTracker, until: dt.datetime
    ) -> AttendanceErrorStatus:
        """
        Perform a data validation of the provided time tracker until the
        given date.

        The function starts by reading existing errors. It only performs
        a new rules check if no existing critical error is found. A rules
        check always starts at the validation anchor date of the tracker
        until the given `until` date. The validation anchor date is moved
        to the first date containing a warning/error. This mechanism
        allows to rescan only a specified dates range and gives flexibility
        for HR, who can decide to manually set the anchor date after a
        manual intervention on a time tracker.

        The `worse_error` and `errors_by_date` properties are available
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
            AttendanceErrorStatus: The status of the worse error found.

        Raises:
            TimeTrackerDateException: `until` date or or validation anchor
                date outside tracker's tracked year.
            TimeTrackerException: Problem with the tracker, see specific
                error and chained errors for details.
        """
        first_year_date = dt.date(tracker.tracked_year, 1, 1)
        validation_anchor_date = tracker.get_last_validation_anchor()

        if validation_anchor_date.year != tracker.tracked_year:
            raise TimeTrackerDateException(
                f"Wrong validation anchor date {validation_anchor_date}, "
                f"expected year {tracker.tracked_year}."
            )

        logger.debug(f"Reading existing attendance errors of {tracker!s}.")

        date_errors: dict[dt.date, int] = {}

        # 1. Read existing errors from the application
        for date in self.__date_rng(first_year_date, until):
            if (error := tracker.get_attendance_error(date)) > 0:
                date_errors[date] = error

        # 2. Read existing errors from the tracker, if it has analyzing
        # capabilities
        if isinstance(tracker, TimeTrackerAnalyzer):
            tracker.analyze(until)

            # Merge with application errors
            for date in self.__date_rng(first_year_date, until):
                if (error := tracker.read_day_attendance_error(date)) > 0:
                    date_errors[date] = max(date_errors.get(date, 0), error)

        # 3. Find the dominant error and its status
        worse_error = max(date_errors.values(), default=0)
        error_status = AttendanceErrorStatus.from_error_id(worse_error)

        # The worse error should be the same as returned by the analyzer
        if isinstance(tracker, TimeTrackerAnalyzer):
            assert tracker.read_year_attendance_error() == worse_error

        logger.debug(
            f"{tracker!s} has initially {len(date_errors)} error(s) in the "
            f"range [{first_year_date}, {until.date()}[. Status "
            f"{error_status.name}. "
            f"Error IDs by date: [{", ".join([
                f"{edt}: {eid!s}" for edt, eid in date_errors.items()
            ])}]."
        )

        # 4. If not in critical error state, the application can scan for
        # errors using the provided checkers. No scan is done if an error
        # already exists because the data may be corrupted.
        no_scan = error_status is AttendanceErrorStatus.ERROR
        if no_scan:
            logger.debug(
                f"Skipped attendance errors scan for {tracker!s} that is in "
                f"{error_status.name} state."
            )
        else:
            logger.debug(
                "Proceeding to application errors scan in range "
                f"[{validation_anchor_date}, {until.date()}[."
            )

            new_anchor_date = None
            for date in self.__date_rng(validation_anchor_date, until):
                # Get the highest error returned by the checkers
                error = max(
                    [
                        checker.error_id
                        for checker in self._checkers
                        if checker.check_date(tracker, date)
                    ],
                    default=0,
                )

                # Write checker error in the tracker and move the validation
                # anchor
                if error > 0:
                    tracker.set_attendance_error(date, error)
                    # The validation anchor is moved to the first date in error
                    if new_anchor_date is None:
                        new_anchor_date = date

                    # Merge with existing error
                    date_errors[date] = max(date_errors.get(date, 0), error)

            if new_anchor_date is None:
                # No error, move the anchor to the last validated day
                new_anchor_date = until.date()

            tracker.set_last_validation_anchor(new_anchor_date)
            logger.debug(f"{tracker!s} validation anchor moved to {new_anchor_date}.")
            tracker.save()

            # Update the worse error that may have increased
            worse_error = max(date_errors.values(), default=0)
            error_status = AttendanceErrorStatus.from_error_id(worse_error)

        # 5. Save results in the validator
        self._worse_error = self.__to_error(tracker, worse_error)
        self._date_errors = {
            edt: self.__to_error(tracker, eid) for edt, eid in date_errors.items()
        }

        logger.info(
            f"Finished attendance validation of {tracker!s} "
            f"with {len(self._date_errors)} error(s). "
            f"Status {error_status.name}. "
            f"Errors by date: [{", ".join([
                f"{edt}: {eid!s}" for edt, eid in self._date_errors.items()
            ])}]. {
                "No rescan performed due to already existing error(s)."
                if no_scan
                else "Scanned range " f"[{validation_anchor_date}, {until.date()}[."
            }"
        )

        return error_status

    @property
    def worse_error(self) -> Optional[AttendanceError]:
        """
        Returns:
            Optional[AttendanceError]: The worse error found or `None` if
                no validation was performed.
        """
        return self._worse_error

    @property
    def errors_by_date(self) -> Optional[dict[dt.date, AttendanceError]]:
        """
        Returns:
            Optional[dict[dt.date, AttendanceError]]: A dictionary of all
                errors by date, or `None` if no validation was performed.
        """
        return self._date_errors
