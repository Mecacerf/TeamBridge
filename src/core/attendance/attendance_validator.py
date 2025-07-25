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
        date_errors: dict[dt.date, int] = {}

        # Read existing errors and select the worse
        self._read_existing_errors(tracker, date_errors, until)
        worse = self.__to_error(tracker, max(date_errors.values(), default=0))

        logger.info(
            f"Read existing errors of {tracker!s} returned {len(date_errors)} "
            f"error(s) and status {worse.status.name}."
        )

        if worse.status is not AttendanceErrorStatus.ERROR:
            # The application can scan for new errors
            self._scan_until(tracker, date_errors, until)
            worse = self.__to_error(tracker, max(date_errors.values(), default=0))
        else:
            logger.info(
                f"Cannot scan for {tracker!s} errors, already in "
                f"{worse.status.name} state."
            )

        # Save validation results
        self._worse_error = worse
        self._date_errors = {
            edt: self.__to_error(tracker, eid) for edt, eid in date_errors.items()
        }

        logger.info(
            f"Finished attendance validation of {tracker!s} "
            f"with {len(self._date_errors)} error(s) and status "
            f"{worse.status.name}."
        )

        if worse.error_id > 0:
            logger.info(f"{tracker!s} most cirtical error is '{worse}'.")

        if len(date_errors) > 0:
            logger.info(
                f"{tracker!s} has errors [{", ".join([
                    f"{edt}: {eid!s}" for edt, eid in self._date_errors.items()
                ])}]."
            )

        return worse.status

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
        desc = "unknown error"
        try:
            desc = tracker.get_attendance_error_desc(error_id)
        except TimeTrackerValueException:
            pass

        return AttendanceError(error_id, desc)

    def _read_existing_errors(
        self, tracker: TimeTracker, date_errors: dict[dt.date, int], until: dt.datetime
    ):
        """
        Read the errors that already exist in the time tracker. If a
        `TimeTracker` is provided, only application errors are read.
        If a `TimeTrackerAnalyzer` is provided, it is analyzed to `until`
        datetime and internal errors are read as well. The function fills
        the provided `date_errors` dictionary.
        """
        first_year_date = dt.date(year=tracker.tracked_year, month=1, day=1)

        # Read existing errors from the application
        for date in self.__date_rng(first_year_date, until):
            if (error := tracker.get_attendance_error(date)) > 0:
                # Merge with existing errors, if not empty
                date_errors[date] = max(date_errors.get(date, 0), error)

        # Read existing errors from the tracker, if it has analyzing capabilities
        if isinstance(tracker, TimeTrackerAnalyzer):
            tracker.analyze(until)

            for date in self.__date_rng(first_year_date, until):
                if (error := tracker.read_day_attendance_error(date)) > 0:
                    # Merge with application errors
                    date_errors[date] = max(date_errors.get(date, 0), error)

        logger.debug(
            f"{tracker!s} existing error(s) "
            f"[{", ".join(str(err) for err in date_errors.values())}]."
        )

    def _scan_until(
        self, tracker: TimeTracker, date_errors: dict[dt.date, int], until: dt.date
    ):
        """
        Scan the dates to find errors from the last validation anchor to
        `until` (exclusive). Each `AttendanceChecker` is tested on each
        date of the range and the highest error is sorted. This error is
        added to the `date_errors` dictionary and written in the tracker's
        application errors. The tracker's validation anchor date is moved
        to the first date with an error or to `until` if no error is found.
        """
        assert until.year == tracker.tracked_year  # Must be managed cleanly earlier

        anchor_date = tracker.get_last_validation_anchor()

        if anchor_date.year != tracker.tracked_year:
            raise TimeTrackerDateException(
                f"Wrong validation anchor date {anchor_date}, "
                f"expected year {tracker.tracked_year}."
            )

        if isinstance(until, dt.datetime):
            until = until.date()

        if anchor_date == until:
            logger.info(
                f"{tracker!s} validation anchor date is already the {anchor_date}. "
                "Nothing to scan."
            )
            return

        new_anchor_date = None
        for date in self.__date_rng(anchor_date, until):
            # Apply each checker on the date and get the highest error
            # returned
            error = max(
                [
                    checker.error_id
                    for checker in self._checkers
                    if checker.check_date(tracker, date)
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

        # Move the validation anchor to the new date if set, or to until
        # if no error has been found
        tracker.set_last_validation_anchor(new_anchor_date or until)
        tracker.save()

        if anchor_date == new_anchor_date:
            anchor_msg = f"stays the {anchor_date} -> error {date_errors[anchor_date]}"
        elif new_anchor_date:
            anchor_msg = f"moved to the {new_anchor_date} -> error {date_errors[new_anchor_date]}"
        else:
            anchor_msg = f"moved at today {until} -> no error"

        logger.info(
            f"Scanned dates {anchor_date} to {until - dt.timedelta(days=1)} of "
            f"{tracker!s}. Validation anchor {anchor_msg}."
        )

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
