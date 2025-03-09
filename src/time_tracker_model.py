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

# Timeout in seconds during which an already scanned code will be ignored
TIMEOUT = 15

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
        self._employee_events_bus = LiveData[EmployeeEvent](None)
        # Create the scanning signal
        self._scanning_sig = LiveData[bool](False)
        # Create the loading signal
        self._loading_sig = LiveData[bool](False)
        # Create the errors bus
        self._error_bus = LiveData[str](None)

    def run(self):
        """
        Model loop. Read the scanner and perform associated actions.
        """
        # Report the scanning state
        self._scanning_sig.set_value(self._scanner.is_scanning())
        
        # Read pending codes
        while self._scanner.available():
            # Get the code as a string
            code = self._scanner.get_next()
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
            self.__process_code(code)

    def __process_code(self, code: str):
        """
        Process the code that has been scanned.

        Parameters:
            code: scanned code
        """
        # Put the code in the waiting list to prevent it to be processed multiple times
        self._waiting_codes[code] = time.time()

        # Set the loading state
        self._loading_sig.set_value(True)

        # Get today date and time from system info
        today = dt.datetime.now().date()
        now = dt.datetime.now().time()
        
        # Next operations might fail, surround with a try except block to capture errors
        try:
            # Open the employee time tracker 
            employee = self._time_tracker_provider(today, code)
            # Refresh it
            employee.refresh()

            # Get employee name and firstname
            name = employee.get_name()
            firstname = employee.get_firstname()

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

            # Everything went fine
            # Create the employee event
            event = EmployeeEvent(name=name, firstname=firstname, id=code, clock_evt=clock_evt)
            # Notify of the new event on the bus
            self._employee_events_bus.set_value(event)

        except Exception as e:
            # Notify that an exception occurred on the errors bus
            self._error_bus.set_value(str(e))
        
        finally:
            # Reset the loading signal
            self._loading_sig.set_value(False)

    def get_employee_events_bus(self) -> LiveData[EmployeeEvent]:
        """
        Returns:
            LiveData[EmployeeEvent]: observable bus on which employees events are published
        """
        return self._employee_events_bus

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
