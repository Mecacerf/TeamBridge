#!/usr/bin/env python3
"""
File: spreadsheet_time_tracker.py
Author: Bastian Cerf
Date: 21/02/2025
Description: 
    Implementation of the time tracker interface using spreadsheet files for data storage.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Import openpyxl for spreadsheet manipulation
import openpyxl
import openpyxl.cell
import openpyxl.utils
import openpyxl.worksheet
# Import subprocess, pathlib and shutil that will be required to execute processes and manipulate files 
import subprocess
import pathlib
import shutil
# Import the time tracker interface
from time_tracker_interface import ITodayTimeTracker, ClockEvent, ClockAction
# Import datetime
import datetime as dt

################################################
#           Spreadsheet constants              #
################################################

# Init sheet index
SHEET_INIT = 0
# January sheet index, next months are incremented
SHEET_JANUARY = 1
# Cell containing the name information
CELL_NAME = 'A6'
# Cell containing the firstname information
CELL_FIRSTNAME = 'A7'
# Cell containing the first day of the month
CELL_START_DATE = 'B9'
# Cell containing the last day of a 31 days month
CELL_END_DATE = 'B39'
# Top left cell containing the first clock in hour of the month
CELL_TOP_LEFT_CLOCK_IN = 'F9'
# Bottom right cell containing the last clock out hour of the month
CELL_BOT_RIGHT_CLOCK_OUT = 'M39'
# Cell containing the employee monthly balance, days balance are in the same column
CELL_MONTHLY_BALANCE = 'D8'

class SpreadsheetTimeTracker(ITodayTimeTracker):
    """
    Implementation of the time tracker that uses spreadsheet files as database.
    """

    def __init__(self, path: str, employee_id: str, today: dt.date):
        """
        Open the employee's data for given date.

        Parameters:
            path: file system path to employees folder
            id: employee unique ID
            index: date index
        Raise:
            ValueError: employee not found
            ValueError: wrong / unavailable date time
        """
        # Save current date
        self._date = today
        # Save employees database path
        self._database_path = pathlib.Path(path)
        # Search employee's file
        self._file_path = self.__get_employee_file(employee_id)
        # Throw a file not found error if necessary
        if self._file_path is None:
            raise FileNotFoundError(f"File not found for employee's ID '{employee_id}'.")
        
        # Reload employee's workbook so all formulas values are up to date
        self.__reload_workbook()

    def __get_employee_file(self, employee_id: str) -> pathlib.Path | None:
        """
        Search the employee's file in given folder.

        Returns:
            pathlib.Path: employee's file or None if not found
        """
        # Get path to employees data files
        folder = pathlib.Path(self._database_path)
        # Search the employee's file based on given id by iterating on all spreadsheet files
        for file in folder.glob("*.xlsx"):
            # Check that this is a file and its name starts with correct id
            if file.is_file() and file.name.startswith(employee_id):
                # Employee's file is found
                return file
        # Employee's file not found
        return None

    def get_firstname(self) -> str:
        """
        Get employee's firstname.

        Returns:
            str: employee's firstname
        """
        # Get firstname information in cell
        return str(self._workbook_rd.worksheets[SHEET_INIT][CELL_FIRSTNAME].value)

    def get_name(self) -> str:
        """
        Get employee's name.

        Returns:
            str: employee's name
        """
        # Get name information in cell
        return str(self._workbook_rd.worksheets[SHEET_INIT][CELL_NAME].value)
    
    def __get_current_date_cell(self) -> openpyxl.cell.Cell:
        """
        Get the cell containing the current date.
        """
        # Get current month's sheet in read mode
        sheet_rd = self._workbook_rd.worksheets[self._date.month - 1 + SHEET_JANUARY]
        # Get dates boundaries in sheet, by definition min_col == max_col since dates are disposed along the same column
        column, min_row, _, max_row = openpyxl.utils.range_boundaries(f"{CELL_START_DATE}:{CELL_END_DATE}")
        # Search current date cell
        date_cell = None
        for row in sheet_rd.iter_rows(min_row=min_row, max_row=max_row, min_col=column, max_col=column):
            # Check date exists and is equal to current date
            if row[0] and row[0].value and row[0].value.date() == self._date:
                # Match is found
                date_cell = row[0]
                break
        
        # Make sure the cell has been found
        if not date_cell:
            raise ValueError(f"The date {self._date} doesn't exist in {self._file_path.name} spreadsheet.")
        # Return cell
        return date_cell

    def __get_clock_action_for_cell(self, cell: openpyxl.cell.Cell) -> ClockAction:
        """
        Check if the given cell contains a clock in or a clock out action, based on its column index.
        """
        # Get first clock in column
        _, clock_in_col = openpyxl.utils.coordinate_to_tuple(CELL_TOP_LEFT_CLOCK_IN)
        # Get difference between first clock in column and given cell column
        delta_actions = cell.column - clock_in_col
        # Sanity check
        if delta_actions < 0:
            raise ValueError(f"Cannot evaluate clock action for cell '{cell.coordinate}' that is beyond limits.")
        # Since a clock in is followed by a clock out and so on, 0=in, 1=out, 2=in, etc
        if (delta_actions % 2) == 0:
            # This is a clock in column
            return ClockAction.CLOCK_IN
        else:
            # This is a clock out action
            return ClockAction.CLOCK_OUT

    def get_clock_events_today(self) -> list[ClockEvent]:
        """
        Get all clock-in/out events for today.

        Returns:
            list[ClockEvent]: list of today's clock events (can be empty)
        """
        # Get current date cell to identify the row
        date_cell = self.__get_current_date_cell()
        # Get current month's sheet in read mode
        sheet_rd = self._workbook_rd.worksheets[self._date.month - 1 + SHEET_JANUARY]
        # Create current date events list
        clock_events = []
        # Get clock actions boundaries
        min_col, _, max_col, _ = openpyxl.utils.range_boundaries(f"{CELL_TOP_LEFT_CLOCK_IN}:{CELL_BOT_RIGHT_CLOCK_OUT}")
        # Iterate in clock actions row for current date
        for column in sheet_rd.iter_cols(min_row=date_cell.row, max_row=date_cell.row, min_col=min_col, max_col=max_col):
            # Get cell value
            cell = column[0]
            # Check if the cell exists and contains an entry
            if cell and cell.value:
                # Create and append the clock event to the list
                event = ClockEvent(time=cell.value, action=self.__get_clock_action_for_cell(cell))
                clock_events.append(event)
            else:
                # No clock event in the cell
                # For this implementation, consider that no other clock action can exist after a hole is found
                break

        # Return the events list
        return clock_events

    def get_worked_time_today(self, now: dt.time = None) -> dt.timedelta:
        """
        Get employee's worked time today.
        If the employee is clocked in the optional argument can be passed to calculate the worked time
        until the given hour (typically now). If None, the worked time is calculated based on previous
        clock events.
        
        Parameters:
            now: used when the employee is clocked in to calculate the worked time until the given hour
        Returns:
            timedelta: delta time object
        """
        # This function currently calculates itself the employee balance for the day instead of reading the
        # balance cell. This behavior might change in next spreadsheet versions.
        # Get today clock events
        clock_events = self.get_clock_events_today()
        # Total calculated delta time 
        delta = dt.timedelta(0)
        # Save previous clock in time
        clock_in_datetime = None
        # Iterate through clock events and sum the deltas
        for event in clock_events:
            # By definition, first event is a clock in action
            if event.action == ClockAction.CLOCK_IN:
                # Set clock in time
                # Since minus and plus operators are available only for dates, create a date object by combining the current
                # date with the clock action time 
                clock_in_datetime = dt.datetime.combine(self._date, event.time)
            elif event.action == ClockAction.CLOCK_OUT:
                # Calculate and add the delta time
                delta += (dt.datetime.combine(self._date, event.time) - clock_in_datetime)
                # Reset clock in time
                clock_in_datetime = None
        # Once all clock events have been iterated, if clock_in_datetime is not None that means the employee is still clocked in
        # If the now argument is available, add the difference between now and last clock in time
        if now and clock_in_datetime:
            # Add the difference
            delta += (dt.datetime.combine(self._date, now) - clock_in_datetime)
        # Return the delta time
        return delta

    def get_monthly_balance(self) -> dt.timedelta:
        """
        Get employee's balance for the current month.

        Returns:
            timedelta: delta time object
        """
        # Get current month's sheet in read mode
        sheet_rd = self._workbook_rd.worksheets[self._date.month - 1 + SHEET_JANUARY]
        # Get monthly balance value as a timedelta
        return sheet_rd[CELL_MONTHLY_BALANCE].value

    def register_clock(self, event: ClockEvent) -> None:
        """
        Register a clock in/out event.

        Parameters:
            event: clock event object
        Raise:
            ValueError: double clock in/out detected
        """
        # Get current date cell
        date_cell = self.__get_current_date_cell()
        # Get current month's sheet in write mode
        sheet_wr = self._workbook_wr.worksheets[self._date.month - 1 + SHEET_JANUARY]
        # Set written flag
        written = False
        # Get clock actions boundaries
        min_col, _, max_col, _ = openpyxl.utils.range_boundaries(f"{CELL_TOP_LEFT_CLOCK_IN}:{CELL_BOT_RIGHT_CLOCK_OUT}")
        # Previous clock action time
        prev_clock_time = None
        # Iterate in clock actions row for current date
        for column in sheet_wr.iter_cols(min_row=date_cell.row, max_row=date_cell.row, min_col=min_col, max_col=max_col):
            # Get cell in the column
            cell = column[0]
            # Iterate until a free cell is found
            if cell.value:
                # Save previous clock action time
                prev_clock_time = cell.value
            else:
                # Cell value is None, free to write a clock action
                # For this implementation, check that the cell is intended to contain the given clock action and raise an error if not
                expected_action = self.__get_clock_action_for_cell(cell)
                if event.action != expected_action:
                    raise ValueError(f"Got a '{event.action}' while expecting a '{expected_action}'.")
                # Check that the clock action times are in ascending order
                if prev_clock_time and prev_clock_time > event.time:
                    raise ValueError(f"Cannot clock at {event.time} while last clock was at {prev_clock_time}.")
                # Write the clock action
                # Save as HH:MM, do not take seconds into account for final user simplicity
                cell.number_format = 'HH:MM'
                cell.value = dt.time(hour=event.time.hour, minute=event.time.minute, second=0)
                print(f"Written {cell.value} in cell {cell.coordinate}")
                written = True
                break
            
        # Check if event has been correctly registered
        if not written:
            raise ValueError(f"Event ({event.action} at {event.time}) has not been correctly registered.")
        
        # Save and reload the workbook after write
        self.__save_workbook_and_reload()

    def __save_workbook_and_reload(self):
        """
        Save the workbook.
        """
        # Log action
        print(f"Starting (re)evaluation of '{self._file_path.name}'...")
        # Save/overwrite the spreadsheet
        self._workbook_wr.save(self._file_path)
        # Reload
        self.__reload_workbook()

    def __reload_workbook(self, tmp=".tmp_calc/"):
        """
        After cell values are modified, use libreoffice in headless mode to update the values of formula cells. 
        This requires 'soffice' to be in the system path.
        """
        # Get temporary file path based on real file path and temporary folder path
        tmp_file = pathlib.Path(tmp) / self._file_path.name
        # Ensure the temporary folder doesn't contain a file with the same name
        if tmp_file.exists():
            raise FileExistsError(f"The temporary file '{tmp_file}' already exists and may contain unsaved data. Manual check required.")
        # Create libreoffice command to evaluate and save a spreadsheet
        command = [
            "C:\Program Files\LibreOffice\program\soffice", # libreoffice invokation
            "--headless",       # Headless means no GUI
            "--calc",           # Spreadsheets mode
            "--convert-to", "xlsx", # Go to xlsx format
            "--outdir", tmp,    # Output in temporary folder
            str(self._file_path.absolute()) # Input employee file
        ]
        # Run command with subprocess
        # Use check=True to ensure raising an exception if the process fails
        # By definition, run() waits for the process to finish
        result = subprocess.run(command, check=True, capture_output=True)
        # It seems like the soffice process can fail and still return 0. Double check for error:
        if result.returncode != 0 or len(result.stderr) > 0:
            raise subprocess.CalledProcessError(returncode=result.returncode, cmd=command, output=result.stderr)
        # Check that the evaluated workbook exists in the temporary folder with the same file name
        if not tmp_file.exists():
            raise FileNotFoundError(f"Subprocess failed to create temporary file under '{tmp_file}'.")
        # Delete old spreadsheet
        self._file_path.unlink(missing_ok=False)
        # Copy temporary spreadsheet to deleted spreadsheet location
        shutil.copy(src=tmp_file, dst=self._file_path)
        # Delete temporary file
        tmp_file.unlink(missing_ok=True)
        # Load workbook
        self.__load_workbook()

    def __load_workbook(self):
        """
        Load the employee's workbook.
        """
        # Open employee spreadsheet in data only and read only modes
        # This is used to read evaluated cell values
        # This workbook must not be saved since all formulas are evaluated, it would overwrite them with current values
        self._workbook_rd = openpyxl.load_workbook(self._file_path, data_only=True)
        # Open employee spreadsheet in write mode
        self._workbook_wr = openpyxl.load_workbook(self._file_path, data_only=False)
        # Log action
        print(f"Successfully (re)loaded '{self._file_path.name}'.")
        