#!/usr/bin/env python3
"""
File: time_tracker_viewmodel.py
Author: Bastian Cerf
Date: 02/03/2025
Description: 
    The view model translates and prepare the model events for the view. 
    This file is designed to be view-agnostic (according to MVVM pattern).
    It doesn't depend on any graphic library.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""
    
from enum import Enum
from live_data import LiveData
from time_tracker_model import TimeTrackerModel, EmployeeEvent, EmployeeData
from time_tracker_interface import ClockAction
import datetime as dt

class ScannerViewModelState(Enum):
    """
    Enumeration of the view model states.
    """
    # Waiting for a QR scan
    SCANNING = 0,
    # Loading an employee's data
    LOADING = 1,
    # Successfully done the action
    SUCCESS = 2,
    # Failed to do the action
    ERROR = 3

class TimeTrackerViewModel:
    """
    Contains the business logic behind the view.
    """

    def __init__(self, model: TimeTrackerModel):
        """
        Create the view model.

        Parameters:
            model: reference on the model in use
        """
        # Save the reference to the model
        self._model = model
        # Set initial state
        self._state = LiveData[ScannerViewModelState](ScannerViewModelState.SCANNING)
        self._text_state = LiveData[str]("")
        self._employee_text = LiveData[str]("")
        # Observe the employee events bus
        self._model.get_employee_events_bus().observe(self.__on_employee_event)
        # Observe the errors bus
        self._model.get_errors_bus().observe(self.__on_error)
        # Observe the loading state
        self._model.is_loading().observe(self.__is_loading)
        # Observe employee data text
        self._model.get_employee_info_bus().observe(self.__employee_data)
        # Reset state when starting scanning
        self._model.is_scanning().observe(lambda scanning: self.reset_state() if scanning else None)

    def __on_employee_event(self, event: EmployeeEvent):
        """
        Called when an employee event occurs in the model.
        """
        # Prepare a custom message based on action
        msg = ""
        if event.clock_evt.action == ClockAction.CLOCK_IN:
            msg = f"Bonjour {event.firstname} !\nEntrée "
        else:
            msg = f"Au revoir {event.firstname} !\nSortie "
        # Append clock time
        time = event.clock_evt.time
        msg += f"enregistrée à {time.hour}h{time.minute}."
        # Notify message
        self._text_state.set_value(msg)
        # Employee action successfully terminated
        self._state.set_value(ScannerViewModelState.SUCCESS)
        # Set loading employee's data
        self._employee_text.set_value("Chargement des informations ...")

    def __employee_data(self, info: EmployeeData):
        """
        Called when employee's data are available.
        """
        # Formatter function
        def format(td: dt.timedelta):
            tot_minutes = td.total_seconds() // 60
            hours, minutes = divmod(int(tot_minutes), 60)
            return f"{hours:02}h{minutes:02}"

        self._employee_text.set_value(
        f"Solde journalier: {format(info.worked_time)} / {format(info.scheduled_time)}\nSolde mensuel: {format(info.monthly_balance)}")

    def __on_error(self, error: str):
        """
        Called when an error occurs in the model.
        """
        # Notify error message
        self._text_state.set_value(f"Une erreur est survenue:\n{error}")
        # Go in error state
        self._state.set_value(ScannerViewModelState.ERROR)

    def __is_loading(self, loading: bool):
        """
        Called when the loading state changes.
        """
        # Go in loading state is currently in scanning state
        if loading and self._state.get_value() == ScannerViewModelState.SCANNING:
            self._text_state.set_value("Chargement des données ...")
            self._state.set_value(ScannerViewModelState.LOADING)

    def get_scanning_state(self) -> LiveData[bool]:
        """
        Returns:
            LiveData[bool]: current scanning state as an observable
        """
        return self._model.is_scanning()

    def get_info_text(self) -> LiveData[str]:
        """
        Returns:
            LiveData[str]: information text as an observable
        """
        return self._text_state
    
    def get_employee_info_text(self) -> LiveData[str]:
        """
        Returns:
            LiveData[str]: employee data text as an observable
        """
        return self._employee_text

    def get_current_state(self) -> LiveData[ScannerViewModelState]:
        """
        Returns:
            LiveData[ScannerViewModelState]: current view model state as an observable
        """
        return self._state
    
    def reset_state(self):
        """
        Reset the view model to the scanning state.
        """
        # Reset text and state
        self._text_state.set_value("En attente de badge ...")
        self._state.set_value(ScannerViewModelState.SCANNING)
        self._employee_text.set_value("")
        # Resume model operation
        self._model.resume()

    def close(self):
        """
        Close the view model and model and release resources.
        """
        # Close the view model
        self._model.close()
