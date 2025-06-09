#!/usr/bin/env python3
"""
File: spreadsheet_time_tracker.py
Author: Bastian Cerf
Date: 21/02/2025
Description:
    Implementation of the time tracker analyzer abstract class using
    spreadsheet files for data storage and data analysis. This
    implementation works with the `sheets_repository` module to access
    and manipulate files on a remote repository.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import logging
import datetime as dt

# Third-party libraries
import openpyxl
from openpyxl.utils import column_index_from_string as col_idx

# Internal imports
from core.time_tracker import *
from .sheets_repository import *
from .libreoffice import *

logger = logging.getLogger(__name__)

########################################################################
#                   Spreadsheet constants declaration                  #
########################################################################

# Expected spreadsheets major version
# Opening a spreadsheet that doesn't use this major version will fail to
# prevent compatibity issues
# This version may be preceded by a minor version in the form '.xx'
EXPECTED_MAJOR_VERSION = "v220525"

# Init sheet index
SHEET_INIT = 0

# Spreadsheet version
CELL_VERSION = "A3"

CELL_NAME = "A10"
CELL_FIRSTNAME = "A11"

CELL_OPENING_DAY_SCHEDULE = "A12"
CELL_OPENING_VACATION = "A13"
CELL_OPENING_BALANCE = "A14"

# These are the date and time data analysis is based on
CELL_DATE = "A21"
CELL_TIME = "A22"

# The year is a constant
CELL_YEAR = "A4"

# Formula evaluation test cell
CELL_EVALUATED = "A23"

## Next cells give the locations of different information in the other
## sheets. It allows to support dynamic per sheet locations and improve
## flexibility in production.

# January sheet index
LOCATION_JANUARY_SHEET = "A24"

# Row number for the first date of the month (01.xx.xxxx)
LOCATION_FIRST_MONTH_DATE_ROW = "A25"

# Day information: scheduled work, worked time and balance columns
LOCATION_DAY_SCHEDULE_COL = "A26"
LOCATION_DAY_WORKED_TIME_COL = "A27"
LOCATION_DAY_BALANCE_COL = "A28"

# Month and year balance cells
LOCATION_MONTH_BALANCE = "A29"
LOCATION_YEAR_BALANCE = "A30"

# Vacation information: remaining days, planned for the month and for the day
LOCATION_REMAINING_VACATION = "A31"
LOCATION_MONTH_VACATION = "A32"
LOCATION_DAY_VACATION_COL = "A33"

# Clock in/out times columns (left and right array delimeters)
LOCATION_FIRST_CLOCK_IN_COL = "A34"
LOCATION_LAST_CLOCK_OUT_COL = "A35"

########################################################################
#         Spreadsheet time tracker custom error definition             #
########################################################################


class SheetTimeTrackerError(Exception):
    """
    Custom exception for general spreadsheet exceptions.
    """

    def __init__(
        self, message: str = "Error occurred while manipulating the spreadsheet"
    ):
        super().__init__(message)


################################################
#   Spreadsheets time tracker implementation   #
################################################


class SheetTimeTracker(TimeTrackerAnalyzer):
    """
    Implementation of the time tracker abstract class using spreadsheet
    files for data storage.
    """

    def _setup(self, accessor: SheetsRepoAccessor):
        """
        Acquire and load the spreadsheet file. Time tracker properties
        are available after this call. The analysis is intentionally
        invalidated to prevent access to potentially outdated data and
        ensure the time tracker is always created in the same state; i.e.
        the `read_` methods are unavalaible.
        """
        self._accessor = accessor
        self._file_path = accessor.acquire_spreadsheet_file(self._employee_id)

        self.__load_workbook()
        self.__invalidate_analysis()  # Prevent access to outdated data

        init_sheet = self._workbook_raw.worksheets[SHEET_INIT]

        # Check that the spreadsheet uses the expected major version
        version = init_sheet[CELL_VERSION].value
        if version is None or not str(version).lower().startswith(
            EXPECTED_MAJOR_VERSION.lower()
        ):
            raise SheetTimeTrackerError(
                f"Cannot load workbook '{self._file_path}' that uses version "
                f"'{version}'. The expected major version is "
                f"'{EXPECTED_MAJOR_VERSION}'."
            )

        # Load locations of cells in the month sheets from the init sheet
        self._sheet_january = int(init_sheet[LOCATION_JANUARY_SHEET].value)
        self._row_first_month_date = int(
            init_sheet[LOCATION_FIRST_MONTH_DATE_ROW].value
        )
        self._col_day_schedule = col_idx(init_sheet[LOCATION_DAY_SCHEDULE_COL].value)
        self._col_day_worked_time = col_idx(
            init_sheet[LOCATION_DAY_WORKED_TIME_COL].value
        )
        self._col_day_balance = col_idx(init_sheet[LOCATION_DAY_BALANCE_COL].value)
        self._cell_month_balance = str(init_sheet[LOCATION_MONTH_BALANCE].value)
        self._cell_year_balance = str(init_sheet[LOCATION_YEAR_BALANCE].value)
        self._cell_remaining_vac = str(init_sheet[LOCATION_REMAINING_VACATION].value)
        self._cell_month_vac = str(init_sheet[LOCATION_MONTH_VACATION].value)
        self._col_day_vac = col_idx(init_sheet[LOCATION_DAY_VACATION_COL].value)
        self._col_first_clock_in = col_idx(
            init_sheet[LOCATION_FIRST_CLOCK_IN_COL].value
        )
        self._col_last_clock_out = col_idx(
            init_sheet[LOCATION_LAST_CLOCK_OUT_COL].value
        )

        logger.debug(
            f"[Employee '{self._employee_id}'] Finished spreadsheet time "
            "tracker setup."
        )

    def __load_workbook(self):
        """
        Load the employee's spreadsheet file (workbook) in two modes:

        - `self._workbook_raw` is loaded with `data_only=False`, allowing
        access to raw cell values. In this mode, formula cells contain
        the actual formula text rather than the evaluated result.
        This workbook is always available and can be safely saved.

        - `self._workbook_eval` is loaded with `data_only=True`, enabling
        access to evaluated formula values. This workbook is available
        only after the spreadsheet has been opened, evaluated, and saved
        by a spreadsheet application such as LibreOffice Calc. It must
        **not** be saved, as doing so would overwrite the formula cells
        with their last evaluated values.

        After loading both workbooks, a check is performed on the evaluated
        one to determine whether formula cells have actually been evaluated.
        If not, `self._workbook_eval` is reset to `None` to prevent
        accidental use. See `__invalidate_analysis()`.
        """
        if self._file_path is None:
            raise RuntimeError("Attempted to re(load) a closed SheetTimeTracker.")

        self._workbook_raw: openpyxl.Workbook = openpyxl.load_workbook(
            self._file_path, data_only=False
        )
        self._workbook_eval: Optional[openpyxl.Workbook] = openpyxl.load_workbook(
            self._file_path, data_only=True
        )

        # Check the "evaluated" cell from the init sheet to know if the formula
        # values are available. If unavailable, invalidate the analysis.
        if self._workbook_eval.worksheets[SHEET_INIT][CELL_EVALUATED].value is None:
            self.__invalidate_analysis()

        logger.debug(
            f"[Employee '{self._employee_id}'] (Re)loaded spreadsheet "
            f"'{self._file_path.name}' "
            + (
                f"(analyzed for '{self._target_dt}')."
                if self.analyzed
                else "(not analyzed)."
            )
        )

    ## General internal utility methods ##

    def __invalidate_analysis(self):
        """
        Invalidate the analysis. It resets the eval workbook and the
        target datetime to `None`, which set the `analyzed` property
        to `False`.
        """
        self._workbook_eval = None
        self._target_dt = None

    def __get_init_sheet_val(self, cell: str) -> Any:
        """
        Retrieve a property from the init sheet.

        Args:
            cell (str): Cell coordinates (ex. 'A1', 'B36', etc.)

        Returns:
            Any: Value stored in the given cell of the init sheet
        """
        return self._workbook_raw.worksheets[SHEET_INIT][cell].value

    def __to_timedelta(self, value: Any) -> dt.timedelta:
        """
        Make sure the given value is a `datetime.timedelta` type. Convert
        if necessary.

        Args:
            value (Any): Input value

        Returns:
            datetime.timedelta: Value converted to a `datetime.timedelta`

        Raises:
            ValueError: If the value cannot be converted
        """
        if isinstance(value, dt.timedelta):
            # Passthrough
            return value
        if isinstance(value, dt.time):
            return dt.timedelta(
                hours=value.hour, minutes=value.minute, seconds=value.second
            )

        raise ValueError("The given value cannot be converted to a timedelta.")

    def __get_date_row(self, date: dt.date | dt.datetime) -> int:
        """
        Args:
            date (datetime.date | datetime.datetime): Input date.

        Returns:
            int: The row index for the given day in the month sheet.

        Raises:
            TimeTrackerDateException: Given date doesn't relate to
                `tracked_year`.
        """
        if date.year != self.tracked_year:
            raise TimeTrackerDateException(
                f"Attempted operation on year {date.year} while tracked year "
                f"is {self.tracked_year}."
            )
        return date.day - 1 + self._row_first_month_date

    def __get_month_sheet_idx(self, month: int | dt.date | dt.datetime) -> int:
        """
        Args:
            month (int | dt.date | dt.datetime): Input month.

        Returns:
            int: The sheet index corresponding to the given month.

        Raises:
            TimeTrackerDateException: Given date doesn't relate to
                `tracked_year`.
        """
        if isinstance(month, (dt.date, dt.datetime)):
            if month.year != self.tracked_year:
                raise TimeTrackerDateException(
                    f"Attempted operation on year {month.year} while tracked "
                    f"year is {self.tracked_year}."
                )
            month = month.month

        # Convert month number to sheet index
        return month - 1 + self._sheet_january

    def __get_clock_action_for_cell(self, cell: Any) -> ClockAction:
        """
        Get the clock action (clock-in / clock-out) that the cell is
        supposed to hold. The function assumes the sequence
        `self._col_first_clock_in` is a clock-in;
        `self._col_first_clock_in + 1` is a clock-out;
        `self._col_first_clock_in + 2` is a clock-in; etc until
        `self._col_last_clock_out`

        Args:
            cell (Any): Must be of type openpyxl.cell.Cell

        Returns:
            ClockAction: Clock action for the cell
        """
        if (
            cell.column < self._col_first_clock_in
            or cell.column > self._col_last_clock_out
        ):
            raise ValueError(
                f"Cell column {cell.column} is out of the range "
                f"[{self._col_first_clock_in}; {self._col_last_clock_out}]."
            )

        # Follow the sequence 0: clock-in, 1: cock-out, 2: clock-in, etc.
        even = ((cell.column - self._col_first_clock_in) % 2) == 0
        return ClockAction.CLOCK_IN if even else ClockAction.CLOCK_OUT

    def __read_month_cell(self, month: int | dt.date | dt.datetime, cell: str) -> Any:
        """
        Read the value of the cell from the given month.

        The cell is identified by its coordinate string (e.g., 'A1', 'B26').

        Args:
            month (int | datetime.date | datetime.datetime): Input month.
            cell (str): Cell coordinate.

        Returns:
            Any: The value of the evaluated cell.

        Raises:
            TimeTrackerReadException: If the spreadsheet is not analyzed
            TimeTrackerDateException: Given date doesn't relate to
                `tracked_year`.
        """
        if self._workbook_eval is None:
            raise TimeTrackerReadException()

        sheet = self._workbook_eval.worksheets[self.__get_month_sheet_idx(month)]
        return sheet[cell].value

    def __read_month_day_cell(self, date: dt.date | dt.datetime, col: int):
        """
        Read the value of the cell from the given month. The cell row is
        found depending on the given date.

        The row is computed from the date (e.g., 1st = base row, 2nd = base row + 1, etc.),
        and the column is provided as an index.

        Args:
            date (datetime.date | datetime.datetime): Input date.
            col (int): Column index to read from (1-based, like Excel columns)

        Returns:
            Any: The value of the evaluated cell

        Raises:
            TimeTrackerReadException: If the spreadsheet is not analyzed
            TimeTrackerDateException: Given date doesn't relate to
                `tracked_year`.
        """
        if self._workbook_eval is None:
            raise TimeTrackerReadException()

        day_row = self.__get_date_row(date)
        sheet = self._workbook_eval.worksheets[self.__get_month_sheet_idx(date)]
        return sheet.cell(row=day_row, column=col).value

    ## General employee's properties access ##

    @property
    def firstname(self) -> str:
        return str(self.__get_init_sheet_val(CELL_FIRSTNAME))

    @property
    def name(self) -> str:
        return str(self.__get_init_sheet_val(CELL_NAME))

    ## General time tracker's properties access ##

    @property
    def tracked_year(self) -> int:
        return int(self.__get_init_sheet_val(CELL_YEAR))

    @property
    def opening_day_schedule(self) -> dt.timedelta:
        return self.__to_timedelta(self.__get_init_sheet_val(CELL_OPENING_DAY_SCHEDULE))

    @property
    def opening_balance(self) -> dt.timedelta:
        return self.__to_timedelta(self.__get_init_sheet_val(CELL_OPENING_BALANCE))

    @property
    def opening_vacation_days(self) -> float:
        return float(self.__get_init_sheet_val(CELL_OPENING_VACATION))

    @property
    def max_clock_events_per_day(self) -> int:
        return int(self._col_last_clock_out - self._col_first_clock_in + 1)

    ## Time Tracker read / write methods ##

    def get_clocks(self, date: dt.date | dt.datetime) -> list[Optional[ClockEvent]]:
        """
        Implementation of `TimeTracker.get_clocks()`.

        Retrieve the clock events on the given date by iterating the
        corresponding row of the month's sheet.

        Raises:
            TimeTrackerDateException: If the opened file doesn't contain
                the month (i.e. wrong year)
            SheetTimeTrackerError: The spreadsheet file might be corrupted
        """
        date_row = self.__get_date_row(date)
        sheet_idx = self.__get_month_sheet_idx(date)
        month_sheet = self._workbook_raw.worksheets[sheet_idx]

        clock_events: list[Optional[ClockEvent]] = []

        # Iterate columns along the date row from the first clock-in column to
        # the last clock-out column
        for column in month_sheet.iter_cols(
            min_row=date_row,
            max_row=date_row,
            min_col=self._col_first_clock_in,
            max_col=self._col_last_clock_out,
        ):
            # The column contains a single row (min_row = max_row)
            if len(column) != 1:
                raise SheetTimeTrackerError(
                    f"Expected one date in the column, got {len(column)}."
                )

            cell = column[0]
            event: Optional[ClockEvent] = None

            # Create and append a ClockEvent if a time is available in the cell,
            # otherwise just append None in the clock events list
            if cell and cell.value and isinstance(cell.value, dt.time):
                event = ClockEvent(
                    time=cell.value, action=self.__get_clock_action_for_cell(cell)
                )
            clock_events.append(event)

        # Return the events list without the trailing None values
        for i in reversed(range(len(clock_events))):
            if clock_events[i] is not None:
                return clock_events[: i + 1]
        return []  # All values are None

    def register_clock(self, date: dt.date | dt.datetime, event: ClockEvent):
        """
        Implementation of `TimeTracker.register_clock()`.

        Searches for the next available time slot in the current date's
        row on the month sheet and writes the event time. If no slot is
        available, raises a TimeTrackerWriteException.

        Raises:
            TimeTrackerDateException: If the opened file doesn't contain
                the month (i.e. wrong year)
            TimeTrackerWriteException: If no available slot is found for
                the clock event
        """
        if self._file_path is None:
            raise RuntimeError("Attempted to use a closed SheetTimeTracker.")

        date_row = self.__get_date_row(date)
        sheet_idx = self.__get_month_sheet_idx(date)
        month_sheet = self._workbook_raw.worksheets[sheet_idx]

        # Determine starting column index based on clock action
        start_idx = self._col_first_clock_in + (
            1 if event.action == ClockAction.CLOCK_OUT else 0
        )

        for col_idx in range(start_idx, self._col_last_clock_out + 1, 2):
            cell = month_sheet.cell(row=date_row, column=col_idx)

            if cell.value is None:
                # The slot is available, write the clock time in HH:MM format
                cell.number_format = "HH:MM"
                cell.value = dt.time(
                    hour=event.time.hour, minute=event.time.minute, second=0
                )  # type: ignore

                # The workbook is saved upon modification, and the reading
                # methods become inaccessible to prevent access to values that
                # may have changed
                self._workbook_raw.save(self._file_path)
                self.__invalidate_analysis()

                logger.debug(
                    f"[Employee '{self._employee_id}'] Registered clock event "
                    f"'{event}' in cell '{cell.coordinate}'."
                )
                return

        raise TimeTrackerWriteException(
            f"No available time slot to write the clock event '{event}'."
        )

    def write_clocks(
        self, date: dt.date | dt.datetime, events: list[Optional[ClockEvent]]
    ):
        pass

    def set_vacation(self, date: dt.date | dt.datetime, day_ratio: float):
        pass

    def get_vacation(self, date: dt.date | dt.datetime) -> float:
        return 0

    def set_attendance_error(
        self, date: dt.date | dt.datetime, error_id: Optional[int]
    ):
        pass

    def get_attendance_error(self, date: dt.date | dt.datetime) -> Optional[int]:
        pass

    ## Time Tracker Analyzer methods ##

    def _analyze_internal(self):
        """
        Implementation of `TimeTrackerAnalyzer.analyze()`.

        Evaluate the spreadsheet file at the defined target date and time
        using the LibreOffice module.
        On failure, invalidates analysis and may prevent future saves by
        nullifying _file_path.
        """
        assert self._target_dt is not None

        if self._file_path is None:
            raise RuntimeError("Attempted to use a closed SheetTimeTracker.")

        init_sheet = self._workbook_raw.worksheets[SHEET_INIT]
        tmp_date_formula = init_sheet[CELL_DATE].value
        tmp_time_formula = init_sheet[CELL_TIME].value

        try:
            # Update the date and time cells of the init sheet with the
            # target values
            init_sheet[CELL_DATE].value = self._target_dt.date()
            init_sheet[CELL_TIME].value = self._target_dt.time()
            self._workbook_raw.save(self._file_path)

            # Evaluate the file and reload it
            evaluate_calc(self._file_path)
            self.__load_workbook()

        except Exception:
            # Analysis result cannot be trust on exception
            self.__invalidate_analysis()
            raise

        finally:
            try:
                # Always restore the formulas in the init sheet
                init_sheet[CELL_DATE].value = tmp_date_formula
                init_sheet[CELL_TIME].value = tmp_time_formula
                self._workbook_raw.save(self._file_path)
            except Exception:
                # Failed to restore the date and time formula: this is
                # a critical error. Prevent the file from being saved to
                # the repository by nullifying it.
                self._file_path = None
                logger.error(
                    f"[Employee '{self._employee_id}'] Failed to "
                    f"restore formula cells after evaluation. File "
                    f"is corrupted and will stay in local cache."
                )
                # Do not close() the file. It must stay locked on the remote
                # until a manual intervention.
                raise

    def read_day_schedule(self, date: dt.date | dt.datetime) -> dt.timedelta:
        value = self.__read_month_day_cell(date, self._col_day_schedule)
        return self.__to_timedelta(value)

    def read_day_worked_time(self, date: dt.date | dt.datetime) -> dt.timedelta:
        value = self.__read_month_day_cell(date, self._col_day_worked_time)
        return self.__to_timedelta(value)

    def read_day_balance(self, date: dt.date | dt.datetime) -> dt.timedelta:
        value = self.__read_month_day_cell(date, self._col_day_balance)
        return self.__to_timedelta(value)

    def read_day_attendance_error(self, date: dt.date | dt.datetime) -> Optional[int]:
        pass

    def read_month_expected_daily_schedule(
        self, month: int | dt.date | dt.datetime
    ) -> dt.timedelta:
        pass

    def read_month_schedule(self, month: int | dt.date | dt.datetime) -> dt.timedelta:
        pass

    def read_month_worked_time(
        self, month: int | dt.date | dt.datetime
    ) -> dt.timedelta:
        pass

    def read_month_balance(self, month: int | dt.date | dt.datetime) -> dt.timedelta:
        value = self.__read_month_cell(month, self._cell_month_balance)
        return self.__to_timedelta(value)

    def read_month_vacation(self, month: int | dt.date | dt.datetime) -> float:
        value = self.__read_month_cell(month, self._cell_month_vac)
        return float(value)

    def read_year_vacation(self) -> float:
        pass

    def read_remaining_vacation(self) -> float:
        pass

    def read_year_to_date_balance(self) -> dt.timedelta:
        if self._target_dt is None:
            raise TimeTrackerReadException()
        value = self.__read_month_cell(self._target_dt, self._cell_year_balance)
        return self.__to_timedelta(value)

    def save(self):
        """
        Implementation of `TimeTracker.save()`.

        Try to save the file on the spreadsheets repository.
        """
        if self._file_path is None:
            raise RuntimeError("Attempted to save a closed SheetTimeTracker.")

        try:
            self._accessor.save_spreadsheet_file(self._file_path)
            logger.debug(f"[Employee '{self._employee_id}'] Spreadsheet file saved.")
        except Exception as e:
            raise TimeTrackerSaveException() from e

    def close(self):
        """
        Implementation of `TimeTracker.close()`.

        Release the file lock from the spreadsheets repository, allowing
        other processes to access the employee's file.
        """
        if self._file_path is None:
            raise RuntimeError("Cannot close a SheetTimeTracker twice.")

        try:
            self._accessor.release_spreadsheet_file(self._file_path)
            self._file_path = None
        except Exception as e:
            raise TimeTrackerCloseException() from e

        logger.debug(
            f"[Employee '{self._employee_id}'] Spreadsheet time tracker closed."
        )
