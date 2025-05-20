#!/usr/bin/env python3
"""
File: spreadsheet_time_tracker.py
Author: Bastian Cerf
Date: 21/02/2025
Description: 
    Implementation of the time tracker abstract class using spreadsheet files for 
    data storage. This implementation works with the `sheets_repository` module
    to access and manipulate files on a remote repository.

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

LOGGER = logging.getLogger(__name__)

################################################
#      Spreadsheet constants declaration       #
################################################

# Expected spreadsheets major version
# Opening a spreadsheet that doesn't use this major version will fail to prevent 
# compatibity issues
# This version may be preceded by a minor version in the form '.xx', that is discarded
EXPECTED_MAJOR_VERSION = "v190525"

# Init sheet index
SHEET_INIT = 0

## Init sheet cells
# Employee's name and firstname
CELL_NAME = 'A10'
CELL_FIRSTNAME = 'A11'

# Date and time information
# These cells contains formulas that must be evaluated
CELL_DATE = 'A21'
CELL_HOUR = 'A22'

# Year the employee's data in the file belong to
# This is a raw cell (no formula) used for verification of dates
CELL_YEAR = 'A4'

# Spreadsheet major version
# This time tracker is designed to work with a defined major version and opening
# a newer / older spreadsheet version will fail. The minor version is discarded. 
CELL_VERSION = 'A3'

## Next cells of the init sheet are pointers to the actual information in the 
## month sheets. This is used to allow changes in the files without having to 
## modify the code.
# January sheet index
LOCATION_JANUARY_SHEET = 'A23'

# Row number for the first date of the month (01.xx.xxxx)
LOCATION_FIRST_MONTH_DATE_ROW = 'A24'

# Day information: scheduled work, worked time and balance columns
LOCATION_DAY_SCHEDULE_COL = 'A25'
LOCATION_DAY_WORKED_TIME_COL = 'A26'
LOCATION_DAY_BALANCE_COL = 'A27'

# Month and year balance cells
LOCATION_MONTH_BALANCE = 'A28'
LOCATION_YEAR_BALANCE = 'A29'

# Vacation information: remaining days, planned for the month and for the day
LOCATION_REMAINING_VACATION = 'A30'
LOCATION_MONTH_VACATION = 'A31'
LOCATION_DAY_VACATION_COL = 'A32'

# Clock in/out times columns (left and right array delimeters)
LOCATION_FIRST_CLOCK_IN_COL = 'A33'
LOCATION_LAST_CLOCK_OUT_COL = 'A34'

################################################
#   Spreadsheets time tracker custom errors    #
################################################

class SheetTimeTrackerError(Exception):
    """
    Custom exception for general spreadsheet exceptions.
    """
    def __init__(self, message="An error occurred while manipulating the spreadsheet"):
        super().__init__(message)

################################################
#   Spreadsheets time tracker implementation   #
################################################

class SheetTimeTracker(BaseTimeTracker):
    """
    Implementation of the time tracker abstract class using spreadsheet files for 
    data storage. This implementation works with the `sheets_repository` module
    to access and manipulate files on a remote repository.
    """

    def _setup(self):
        """
        Acquire and load the spreadsheet file. Time tracker properties are available
        after this call. Note that even though the spreadsheet file may have evaluated
        formula values, the evaluated workbook is intentionally invalidated to prevent
        access to potentially outdated data and ensure the time tracker is always 
        created in the same state; i.e. the `read_` methods are unavalaible.
        """
        self._file_path = acquire_spreadsheet_file(self._employee_id)

        self.__load_workbook()
        self.__invalidate_eval_wb() # Prevent access to outdated data

        init_sheet = self._workbook_raw.worksheets[SHEET_INIT]
        
        # Check that the spreadsheet uses the expected major version
        version = init_sheet[CELL_VERSION].value
        if version is None or not str(version).lower().startswith(EXPECTED_MAJOR_VERSION.lower()):
            raise SheetTimeTrackerError((f"Cannot load workbook '{self._file_path}' that uses "
                f"version '{version}'. The expected major version is '{EXPECTED_MAJOR_VERSION}'."))

        # Get locations of the actual values from the init sheet 
        self._sheet_january         = int(init_sheet[LOCATION_JANUARY_SHEET].value)
        self._row_first_month_date  = int(init_sheet[LOCATION_FIRST_MONTH_DATE_ROW].value)
        self._col_day_schedule      = col_idx(init_sheet[LOCATION_DAY_SCHEDULE_COL].value)
        self._col_day_worked_time   = col_idx(init_sheet[LOCATION_DAY_WORKED_TIME_COL].value)
        self._col_day_balance       = col_idx(init_sheet[LOCATION_DAY_BALANCE_COL].value)
        self._cell_month_balance    = str(init_sheet[LOCATION_MONTH_BALANCE].value)
        self._cell_year_balance     = str(init_sheet[LOCATION_YEAR_BALANCE].value)
        self._cell_remaining_vac    = str(init_sheet[LOCATION_REMAINING_VACATION].value)
        self._cell_month_vac        = str(init_sheet[LOCATION_MONTH_VACATION].value)
        self._col_day_vac           = col_idx(init_sheet[LOCATION_DAY_VACATION_COL].value)
        self._col_first_clock_in    = col_idx(init_sheet[LOCATION_FIRST_CLOCK_IN_COL].value)
        self._col_last_clock_out    = col_idx(init_sheet[LOCATION_LAST_CLOCK_OUT_COL].value)

        LOGGER.debug(f"[Employee '{self._employee_id}'] Finished spreadsheet time tracker setup.")

    def __get_init_sheet_val(self, cell: str):
        """
        Retrieve a property from the init sheet.

        Args:
            cell (str): Cell coordinates (ex. 'A1', 'B36', etc.)

        Returns:
            Any: Value stored in the given cell of the init sheet
        """
        return self._workbook_raw.worksheets[SHEET_INIT][cell].value

    @property
    def firstname(self) -> str:
        return str(self.__get_init_sheet_val(CELL_FIRSTNAME))

    @property
    def name(self) -> str:
        return str(self.__get_init_sheet_val(CELL_NAME)) 

    @property
    def data_year(self) -> int:
        return int(self.__get_init_sheet_val(CELL_YEAR))

    @property
    def clock_events(self) -> list[ClockEvent]:
        """
        Implementation of `time_tracker.clock_events`. 

        Retrieve the clock events for the `current_date` by iterating the current date 
        row of the month's sheet.

        Raises:
            TimeTrackerDateException: If the opened file doesn't contain the month (i.e. wrong year)
            SheetTimeTrackerError: The spreadsheet file might be corrupted
        """
        date_row = self.__get_date_row() 
        month_sheet = self._workbook_raw.worksheets[self.__get_month_sheet_idx()]

        clock_events = []
        
        # Iterate columns along the date row from the first clock-in column to the last clock-out column
        # The column therefore always contains a single cell
        for column in month_sheet.iter_cols(min_row=date_row, max_row=date_row, 
                                            min_col=self._col_first_clock_in, 
                                            max_col=self._col_last_clock_out):
            if len(column) != 1:
                raise SheetTimeTrackerError(f"Expected one date in the column, got {len(column)}.")

            cell = column[0]
            event = None

            # Create and append a ClockEvent if a time is available in the cell, otherwise just append 
            # None in the clock events list
            if cell and cell.value and isinstance(cell.value, dt.time):
                event = ClockEvent(time=cell.value, 
                                   action=self.__get_clock_action_for_cell(cell))
            clock_events.append(event)

        # Return the events list without the trailing None values
        for i in reversed(range(len(clock_events))):
            if clock_events[i] is not None:
                return clock_events[:i+1]
        return [] # All values are None

    @property
    def readable(self) -> bool:
        return (self._workbook_eval is not None)

    def __read_month_static_cell(self, cell: str):
        """
        Read the value of a specific evaluated cell from the current month's sheet.

        The cell is identified by its coordinate string (e.g., 'A1', 'B26').

        Args:
            cell (str): Cell coordinate

        Returns:
            Any: The value of the evaluated cell

        Raises:
            TimeTrackerReadException: If the spreadsheet is not readable
            TimeTrackerDateException: If the opened file doesn't contain the month (i.e. wrong year)
        """
        if not self.readable:
            raise TimeTrackerReadException()

        sheet = self._workbook_eval.worksheets[self.__get_month_sheet_idx()]
        return sheet[cell].value

    def __read_month_day_cell(self, col: int):
        """
        Read the value of a cell from the current month's sheet based on the current date.

        The row is computed from the date (e.g., 1st = base row, 2nd = base row + 1, etc.),
        and the column is provided as an index.

        Args:
            col (int): Column index to read from (1-based, like Excel columns)

        Returns:
            Any: The value of the evaluated cell at the given column and date row

        Raises:
            TimeTrackerReadException: If the spreadsheet is not readable
            TimeTrackerDateException: If the opened file doesn't contain the month (i.e. wrong year)
        """
        if not self.readable:
            raise TimeTrackerReadException()

        day_row = self._row_first_month_date + self._date.day - 1
        sheet = self._workbook_eval.worksheets[self.__get_month_sheet_idx()]
        return sheet.cell(row=day_row, column=col).value

    def __to_timedelta(self, value) -> dt.timedelta:
        """
        Make sure the given value is a `datetime.timedelta` type. Convert if necessary.

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
            return dt.timedelta(hours=value.hour, minutes=value.minute, seconds=value.second)
        
        raise ValueError("The given value cannot be converted to a timedelta.")

    def read_day_schedule(self) -> dt.timedelta:
        value = self.__read_month_day_cell(self._col_day_schedule)
        return self.__to_timedelta(value)

    def read_day_balance(self) -> dt.timedelta:
        value = self.__read_month_day_cell(self._col_day_balance)
        return self.__to_timedelta(value)

    def read_day_worked_time(self) -> dt.timedelta:
        value = self.__read_month_day_cell(self._col_day_worked_time)
        return self.__to_timedelta(value)

    def read_month_balance(self) -> dt.timedelta:
        value = self.__read_month_static_cell(self._cell_month_balance)
        return self.__to_timedelta(value)

    def read_year_balance(self) -> dt.timedelta:
        value = self.__read_month_static_cell(self._cell_year_balance)
        return self.__to_timedelta(value)

    def read_remaining_vacation(self) -> float:
        value = self.__read_month_static_cell(self._cell_remaining_vac)
        return float(value)

    def read_month_vacation(self) -> float:
        value = self.__read_month_static_cell(self._cell_month_vac)
        return float(value)

    def read_day_vacation(self) -> float:
        value = self.__read_month_day_cell(self._col_day_vac)
        return float(value)

    def register_clock(self, event: ClockEvent) -> None:
        """
        Implementation of `time_tracker.register_clock()`.

        Searches for the next available time slot in the current date's row on the monthly sheet,
        and writes the event time. If no slot is available, raises a TimeTrackerWriteException.

        Raises:
            TimeTrackerDateException: If the opened file doesn't contain the month (i.e. wrong year)
            TimeTrackerWriteException: If no available slot is found for the clock event
        """
        date_row = self.__get_date_row()
        month_sheet = self._workbook_raw.worksheets[self.__get_month_sheet_idx()]

        # Determine starting column index based on clock action
        start_idx = self._col_first_clock_in + (1 if event.action == ClockAction.CLOCK_OUT else 0)

        for col_idx in range(start_idx, self._col_last_clock_out + 1, 2):
            cell = month_sheet.cell(row=date_row, column=col_idx)

            if cell.value is None:
                # The slot is available, write the clock time in HH:MM format
                cell.number_format = 'HH:MM'
                cell.value = dt.time(hour=event.time.hour, minute=event.time.minute, second=0)
                
                # The workbook is saved upon modification, and the reading methods become inaccessible 
                # to prevent access to values that may have changed
                self._workbook_raw.save(self._file_path)
                self.__invalidate_eval_wb()

                LOGGER.debug((f"[Employee '{self._employee_id}'] Registered clock event '{event}' "
                              f"in cell '{cell.coordinate}'."))
                return

        raise TimeTrackerWriteException(f"No available time slot to write the clock event '{event}'.")

    def evaluate(self) -> None:
        """
        Implementation of `time_tracker.evaluate()`.

        Try to evaluate the spreadsheet file using the LibreOffice module. 
        The workbooks are reloaded on success in order to update the `readable` property.
        """
        try:
            evaluate_calc(self._file_path)
            self.__load_workbook()
        except Exception as e:
            raise TimeTrackerEvaluationException() from e 

    def save(self) -> None:
        """
        Implementation of `time_tracker.save()`.

        Try to save the file on the spreadsheets repository.  
        """
        try:
            save_spreadsheet_file(self._file_path)
            LOGGER.debug(f"[Employee '{self._employee_id}'] Spreadsheet file saved.")
        except Exception as e:
            raise TimeTrackerSaveException() from e

    def close(self) -> None:
        """
        Implementation of `time_tracker.close()`.

        Release the file lock from the spreadsheets repository, allowing other
        processes to access the employee's file.
        """
        try:
            release_spreadsheet_file(self._file_path)
            self._workbook_eval = None
            self._workbook_raw = None
            LOGGER.debug(f"[Employee '{self._employee_id}'] Spreadsheet time tracker closed.")
        except Exception as e:
            raise TimeTrackerCloseException() from e
    
    def __get_date_row(self) -> int:
        """
        Returns:
            int: The row index corresponding to the day of the month in the month's sheets
        """
        return (self._date.day - 1 + self._row_first_month_date)

    def __get_month_sheet_idx(self) -> int:
        """
        Returns:
            int: The sheet index corresponding to the current date's month
        
        Raises:
            TimeTrackerDateException: If the opened file doesn't contain the month (i.e. wrong year)
        """
        if self.data_year != self._date.year:
            raise TimeTrackerDateException((f"Cannot access date '{self._date}' while the file "
                                            f"targets the year {self.data_year}."))

        return (self._date.month - 1 + self._sheet_january)

    def __get_clock_action_for_cell(self, cell: openpyxl.cell.Cell) -> ClockAction:
        """
        Get the clock action (clock-in / clock-out) that the cell is supposed to hold. 
        The function assumes the sequence `self._col_first_clock_in` is a clock-in,
        `self._col_first_clock_in + 1` is a clock-out and so on until 
        `self._col_last_clock_out`

        Args:
            cell (openpyxl.cell.Cell): Openpyxl `Cell`
        
        Returns:
            ClockAction: Clock action for the cell
        """
        if (cell.column < self._col_first_clock_in) or (cell.column > self._col_last_clock_out):
            raise ValueError((f"Cell column {cell.column} is out of the range "
                              f"[{self._col_first_clock_in}; {self._col_last_clock_out}]."))

        # Follow the sequence 0: clock-in, 1: cock-out, 2: clock-in, etc.
        even = ((cell.column - self._col_first_clock_in) % 2) == 0
        return ClockAction.CLOCK_IN if even else ClockAction.CLOCK_OUT

    def __load_workbook(self):
        """
        Load the employee's spreadsheet file (workbook) in two modes:

        - `self._workbook_raw` is loaded with `data_only=False`, allowing access to raw cell values.
        In this mode, formula cells contain the actual formula text rather than the evaluated result.
        This workbook is always available and can be safely saved.

        - `self._workbook_eval` is loaded with `data_only=True`, enabling access to evaluated formula values.
        This workbook is available only after the spreadsheet has been opened, evaluated, and saved by
        a spreadsheet application such as LibreOffice Calc. It must **not** be saved, as doing so would 
        overwrite the formula cells with their last evaluated values.

        After loading both workbooks, a check is performed on the evaluated one to determine whether
        formula cells have actually been evaluated. If not, `self._workbook_eval` is set to `None` 
        to prevent accidental use.
        """
        self._workbook_raw = openpyxl.load_workbook(self._file_path, data_only=False)
        self._workbook_eval = openpyxl.load_workbook(self._file_path, data_only=True)

        # The eval workbook has not been evaluated if the date cell from the init sheet is None, since
        # this cell contains the TODAY() formula.
        if self._workbook_eval.worksheets[SHEET_INIT][CELL_DATE].value is None:
            self._workbook_eval = None

        LOGGER.debug((f"[Employee '{self._employee_id}'] (Re)loaded spreadsheet '{self._file_path.name}', "
                     f"readable={self.readable}."))

    def __invalidate_eval_wb(self):
        """
        Invalidate the evaluated workbook. This is typically done after a modification that may change the 
        result of a formula has been made.
        """
        self._workbook_eval = None
