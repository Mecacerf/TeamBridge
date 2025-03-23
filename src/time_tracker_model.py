#!/usr/bin/env python3
"""
File: time_tracker_model.py
Author: Bastian Cerf
Date: 02/03/2025
Description: 
    The model orchestrates how the application works by processing QR scanner inputs and
    reading / writing in employees database.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

from qr_scanner import QRScanner
from time_tracker_interface import ITodayTimeTracker, ClockEvent, ClockAction
from typing import Callable
import time
import datetime as dt
from live_data import LiveData
import logging
import threading
import queue

# Get module logger
LOGGER = logging.getLogger(__name__)

# Timeout in seconds during which an already scanned code will be ignored
TIMEOUT = 10
# Token a code must start with in order to be valid. Example: teambridge@000, id='000'
CODE_TOKEN = "teambridge@"

class EmployeeEvent:
    """
    Describes an event related to an employee.
    """

    def __init__(self, name: str, firstname: str, id: str, clock_evt: ClockEvent):
        """
        Create an employee event.

        Parameters:
            name: employee's name
            firstname: employee's firstname
            id: employee's id
            clock_evt: related ClockEvent
        """
        # Save event parameters
        self.name = name
        self.firstname = firstname
        self.id = id
        self.clock_evt = clock_evt

class EmployeeData:
    """
    Container of different information about an employee.
    """

    def __init__(self, name: str, 
                 firstname: str, 
                 id: str, 
                 worked_time: dt.timedelta, 
                 scheduled_time: dt.timedelta, 
                 monthly_balance: dt.timedelta):
        """
        Create an employee's data container.
        """
        # Save parameters
        self.name = name
        self.firstname = firstname
        self.id = id
        self.worked_time = worked_time
        self.scheduled_time = scheduled_time
        self.monthly_balance = monthly_balance

class TimeTrackerModel:
    """
    This class is intended to hold the application backend logic: 
    - Create and poll the QR scanner
    - Acquire and use the time tracker interface to read/write the employees data
    """

    def __init__(self, time_tracker_provider: Callable[[dt.date, str], ITodayTimeTracker], device_id=0, scan_rate=5, debug=False):
        """
        Build the application model.

        Parameters:
            time_tracker: generic access to employees data
            device_id: webcam id used by the scanner, typically 0 if only one webcam is available
            scan_rate: rate in [Hz] at which the scanner will analyze frames
        """
        # Save the time tracker provider
        self._time_tracker_provider = time_tracker_provider
        # Create the QR scanner and open it
        self._scanner = QRScanner()
        self._scanner.open(cam_idx=device_id, scan_rate=scan_rate, debug_window=debug)
        # Create the waiting dictionary 
        self._waiting_codes = {}
        # Create the employees events bus
        self._employee_events_bus = LiveData[EmployeeEvent](None, bus_mode=True)
        # Create the employees info bus
        self._employee_info_bus = LiveData[EmployeeData](None, bus_mode=True)
        # Create the scanning signal
        self._scanning_sig = LiveData[bool](False)
        # Create the loading signal
        self._loading_sig = LiveData[bool](False)
        # Create the errors bus
        self._error_bus = LiveData[str](None, bus_mode=True)
        # Create the processing flag
        self._processing = threading.Event()
        # Create the working flag, initially true
        self._working = threading.Event()
        self._working.set()
        # Create the employee events queue
        self._event_queue = queue.Queue()
        # Create the employee info queue
        self._info_queue = queue.Queue()
        # Create the errors queue
        self._error_queue = queue.Queue()

    def run(self):
        """
        Model loop. Read the scanner and perform associated actions.
        """
        # Report the scanning state
        self._scanning_sig.set_value(self._scanner.is_scanning())
        
        # Read pending codes if not already processing
        while self._working.is_set() and self._scanner.available():
            # Get the code as a string
            code = self._scanner.get_next()
            # Ensure that the code starts with the token
            if not code.startswith(CODE_TOKEN):
                # Ignore wrong code
                LOGGER.debug(f"Ignored wrong scanned code '{code}'")
                continue
            # Check if the code is present in the waiting codes
            if code in self._waiting_codes:
                # Calculate delta time between first scan and now
                delta = time.time() - self._waiting_codes[code]
                # Check if the timeout is still pending
                if delta < TIMEOUT:
                    # Ignore the code
                    continue
                # Otherwise remove the code from the waiting list and process it
                self._waiting_codes.pop(code)
            # Process the code
            self.__start_code_processing(code)

        # Clear loading state when processing finishes
        if not self._processing.is_set() and self._loading_sig.get_value():
            self._loading_sig.set_value(False)

        # Publish pending employee's events 
        if not self._event_queue.empty():
            try:
                # Notify of the new event on the bus
                self._employee_events_bus.set_value(self._event_queue.get_nowait())
            except queue.Empty:
                pass

        # Publish pending employee's info 
        if not self._info_queue.empty():
            try:
                # Notify of the new event on the bus
                self._employee_info_bus.set_value(self._info_queue.get_nowait())
            except queue.Empty:
                pass

        # Publish pending error events
        if not self._error_queue.empty():
            try:
                # Notify of the error on the bus
                self._error_bus.set_value(self._error_queue.get_nowait())
            except queue.Empty:
                pass

    def __start_code_processing(self, code: str):
        """
        Prepare and start the processing thread.

        Parameters:
            code: scanned code
        """
        # Put the code in the waiting list to prevent it to be processed multiple times
        self._waiting_codes[code] = time.time()
        # Get the employee's id from scanned code
        id = code.removeprefix(CODE_TOKEN)
        # Log processing will start
        LOGGER.info(f"Start processing code '{code}', employee's id is '{id}'.")

        # Set processing status and disable working status
        self._working.clear()
        self._processing.set()
        self._loading_sig.set_value(True)

        # Start the processing thread
        executor = threading.Thread(target=self.__process_id, args=(id,), name=f"ID{id}-Executor")
        executor.start()
    
    def __process_id(self, id: str):
        """
        Process the employee's action.

        Parameters:
            id: employee's id
        """
        # Get today date and time from system info
        today = dt.datetime.now().date()
        now = dt.datetime.now().time()
        
        # Next operations might fail, surround with a try except block to capture errors
        employee = None
        try:
            # Open the employee time tracker 
            employee = self._time_tracker_provider(today, id)

            # Get employee name and firstname
            name = employee.get_name()
            firstname = employee.get_firstname()

            # Log that time tracker is open
            LOGGER.info(f"Opened time tracker for employee '{firstname} {name}' with id '{id}'. Initially readable: {employee.is_readable()}.")

            # Check if the employee is clocked in to define next action
            if employee.is_clocked_in_today():
                # The employee is clocking out
                action = ClockAction.CLOCK_OUT
            else:
                # The employee is clocking in
                action = ClockAction.CLOCK_IN
            # Create and register the clock event
            clock_evt = ClockEvent(time=now, action=action)
            employee.register_clock(clock_evt)
            # Commit changes
            employee.commit()
            # Close the time tracker
            # If this operation fails the data might not be correctly saved
            employee.close()
            # Nullify to prevent closing it again
            employee = None

            LOGGER.info(f"Clock action saved for employee ['{firstname} {name}' with id '{id}'].")

            # Everything went fine
            # Create the employee event
            event = EmployeeEvent(name=name, firstname=firstname, id=id, clock_evt=clock_evt)
            # Put the event in the queue
            self._event_queue.put(event)

            # Start the inquiry process
            # Open again for read
            employee = self._time_tracker_provider(today, id)
            # Evaluate to allow reading
            if not employee.is_readable():
                employee.evaluate()
            # Read and fill an employee info container
            worked_time = employee.get_worked_time_today()
            scheduled = employee.get_daily_schedule()
            balance = employee.get_monthly_balance()
            event = EmployeeData(name=name, firstname=firstname, id=id, 
                                 worked_time=worked_time, scheduled_time=scheduled, monthly_balance=balance)
            # Publish
            self._info_queue.put(event)
            # Close again and nullify
            employee.close()
            employee = None

            LOGGER.info(f"Operation finished for employee ['{firstname} {name}' with id '{id}'].")

        # Catch the exceptions that may occur during the process
        except Exception as e:
            # Notify that an exception occurred on the errors bus
            self._error_queue.put(str(e))
            # Log error
            LOGGER.error(f"Error occurred operating time tracker of employee '{id}'.", exc_info=True)
        finally:
            # Always close the time tracker once operations are finished
            try:
                if employee:
                    employee.close()
            except:
                LOGGER.error(f"Error occurred closing time tracker of employee '{id}'.", exc_info=True)
            
            # Processing finished
            self._processing.clear()

    def resume(self):
        """
        Resume scanning operation. Must be called after an employee has been processed to continue
        scanning next ids.
        """
        # Cannot resume while processing
        if self._processing.is_set():
            return
        # Flush pending QR values that may have been scanned during the processing time and set the working status
        self._scanner.flush()
        self._working.set()

    def get_employee_events_bus(self) -> LiveData[EmployeeEvent]:
        """
        Returns:
            LiveData[EmployeeEvent]: observable bus on which employees events are published
        """
        return self._employee_events_bus
    
    def get_employee_info_bus(self) -> LiveData[EmployeeEvent]:
        """
        Returns:
            LiveData[EmployeeInfo]: observable bus on which employees info are published
        """
        return self._employee_info_bus

    def get_errors_bus(self) -> LiveData[str]:
        """
        Returns:
            LiveData[str]: observable bus on which errors are published
        """
        return self._error_bus

    def is_loading(self) -> LiveData[bool]:
        """
        Returns:
            LiveData[bool]: loading state as an observable
        """
        return self._loading_sig

    def is_scanning(self) -> LiveData[bool]:
        """
        Returns:
            LiveData[bool]: scanning state as an observable
        """
        return self._scanning_sig

    def close(self):
        """
        Terminate the model, release resources.
        """
        # Release the scanner
        self._scanner.close()
