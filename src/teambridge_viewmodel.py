#!/usr/bin/env python3
"""
File: teambridge_viewmodel.py
Author: Bastian Cerf
Date: 02/03/2025
Description: 


Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""
    
from enum import Enum
from state_machine import IStateMachine, IStateBehavior
from live_data import LiveData
from teambridge_model import *
from time_tracker_interface import ClockAction
from barcode_scanner import BarcodeScanner
import datetime as dt
import logging
from abc import ABC
import time

# Reduce visibility to public classes
__all__ = ["TeamBridgeViewModel", "ViewModelAction"]

LOGGER = logging.getLogger(__name__)

# Regular expression to use to identify an employee's ID
EMPLOYEE_REGEX = r"teambridge@(\w+)"
# Regex group to extract ID
EMPLOYEE_REGEX_GROUP = 1
# Timeout [s] to prevent scanning the same ID multiple times
SCAN_ID_TIMEOUT = 10.0

class ViewModelAction(Enum):
    """
    Possible actions the viewmodel can perform.
    This enum is used to interact with the viewmodel.
    """
    # No action planned
    NO_ACTION = -1,
    # Clock in/out action
    CLOCK_ACTION = 0,
    # Consultation action
    CONSULTATION = 1,
    # Move to scanning action, self-clearing
    SCANNING = 2

class TeamBridgeViewModel(IStateMachine):
    """
    """

    def __init__(self, model: TeamBridgeModel, 
                 scanner: BarcodeScanner,
                 cam_idx: int, 
                 scan_rate: float, 
                 debug_mode: bool=False):
        """
        """
        # Enter the initial state
        # The entry() method is called at first run
        super().__init__(_InitialState())
        # Save parameters
        self._model = model
        self._scanner = scanner
        self._cam_idx = cam_idx
        self._scan_rate = scan_rate
        self._debug_mode = debug_mode
        # Create viewmodel live data
        self._next_action = LiveData[ViewModelAction](ViewModelAction.CLOCK_ACTION)
        self._instruction_txt = LiveData[str]("")
        self._information_txt = LiveData[str]("")
        self._attendance_txt = LiveData[str]("")

    def run(self):
        """
        """
        # Run the state machine
        super().run()

    def on_state_changed(self, old_state):
        """
        """
        LOGGER.info(f"State changed from {old_state} to {self._state}.")
        # The state machine must work with known state types
        assert isinstance(self._state, _IViewModelState)
        # Update texts
        self._instruction_txt.value = self._state.instruction_text
        self._information_txt.value = self._state.information_text
        self._attendance_txt.value = self._state.attendance_text

    @property
    def next_action(self) -> LiveData[ViewModelAction]:
        """
        Returns:
            LiveData[ViewModelAction]: an observable on the next action the viewmodel is going to perform
        """
        return self._next_action

    @next_action.setter
    def next_action(self, action: ViewModelAction):
        """
        Set the next action the viewmodel will have to perform when an employee's ID will be available.

        Args:
            action: `ViewModelAction` next action
        """
        self._next_action.value = action

    @property
    def current_state(self) -> str:
        """
        """
        return str(self._state)

    @property
    def instruction_text(self) -> LiveData[str]:
        """
        """
        return self._instruction_txt

    @property
    def information_text(self) -> LiveData[str]:
        """
        """
        return self._information_txt

    @property
    def attendance_text(self) -> LiveData[str]:
        """
        """
        return self._attendance_txt
    
    def close(self):
        """
        """
        self._model.close()

class _IViewModelState(IStateBehavior[TeamBridgeViewModel], ABC):
    """
    Define the base interface for a state of the viewmodel. Provide
    getters for the different UI information in the state.
    """

    @property
    def instruction_text(self):
        return None
    
    @property
    def information_text(self):
        return None
    
    @property
    def attendance_text(self):
        return None

    def __repr__(self):
        # Return the class name and remove leading underscore
        return self.__class__.__name__[1:]

class _InitialState(_IViewModelState):
    """
    Initialize the barcode scanner.
    """

    def entry(self):
        # Configure the barcode scanner
        self._fsm._scanner.configure(regex=EMPLOYEE_REGEX, 
                                     extract_group=EMPLOYEE_REGEX_GROUP,
                                     timeout=SCAN_ID_TIMEOUT,
                                     debug_mode=self._fsm._debug_mode)
        # Open the scanner
        self._fsm._scanner.open(cam_idx=self._fsm._cam_idx, scan_rate=self._fsm._scan_rate)

    def do(self) -> IStateBehavior:
        # Check if the scanner is open
        if self._fsm._scanner.is_scanning():
            # Go to scanning state
            return _ScanningState()
        # Stay in this state as long as the scanner is closed
        return None
    
    @property
    def instruction_text(self):
        return "Ouverture du scanner..."

class _ScanningState(_IViewModelState):
    """
    Poll the scanner until an employee's ID is found.
    """

    TRANSITION_STATES = [ViewModelAction.CLOCK_ACTION, ViewModelAction.CONSULTATION]

    def entry(self):
        # Make sure the barcode scanner is scanning
        self._fsm._scanner.resume()

    def do(self) -> IStateBehavior:
        # Check that the scanner is still scanning
        if not self._fsm._scanner.is_scanning():
            # Return to initial state, an error may have occurred
            return _InitialState()
            
        # Check if an employee ID is available and the next action is available for a state transition
        action = self._fsm._next_action.value
        if self._fsm._scanner.available() and action in self.TRANSITION_STATES:
            # Read scanned ID
            id = self._fsm._scanner.read_next()
            # Choose the next action
            action = self._fsm._next_action.value
            if action == ViewModelAction.CLOCK_ACTION:
                # Go to clock action state
                return _ClockActionState(id)
            elif action == ViewModelAction.CONSULTATION:
                # Go to consultation state
                return _ConsultationActionState(id)
        
        return None
    
    def exit(self):
        # Pause the scanner to prevent scanning multiple IDs while processing one
        self._fsm._scanner.pause()
    
    @property
    def instruction_text(self):
        return "En attente de badge."
    
    @property
    def information_text(self):
        return ""

class _ClockActionState(_IViewModelState):
    """
    Clock in/out an employee.
    """

    def __init__(self, id: str):
        super().__init__()
        # Save employee ID
        self._id = id

    def entry(self):
        # Start a clock action task and save the task handle
        self._handle = self._fsm._model.start_clock_action_task(id=self._id, datetime=dt.datetime.now())

    def do(self) -> IStateBehavior:
        # Get the task result if available
        msg = self._fsm._model.get_result(self._handle)
        if msg:
            # The clock action task has completed
            if isinstance(msg, EmployeeEvent):
                return _ClockSuccessState(msg)
            elif isinstance(msg, ModelError):
                return _ErrorState(msg)
            else:
                raise RuntimeError(f"Unexpected message received {msg}")
        return None

    def exit(self):
        # Drop the task handle, it has no effect if the task is finished
        self._fsm._model.drop(self._handle)
    
    @property
    def instruction_text(self):
        return "Chargement..."

class _ClockSuccessState(_IViewModelState):
    """
    The clock action succeeded. Perform a consultation.
    """

    def __init__(self, event: EmployeeEvent):
        super().__init__()
        # Save employee's event
        self._evt = event

    def entry(self):
        # Resume scanner operation
        self._fsm._scanner.clear()
        self._fsm._scanner.resume()
        # Start a consultation task
        self._handle = self._fsm._model.start_consultation_task(self._evt.id, dt.datetime.now())

    def do(self) -> IStateBehavior:
        # If a new ID is available, return to scanning state
        if self._fsm._scanner.available():
            return _ScanningState()
        # If the consultation is done, move in presentation state
        msg = self._fsm._model.get_result(self._handle)
        if msg:
            if isinstance(msg, EmployeeData):
                return _ConsultationSuccessState(msg, timeout=True)
            elif isinstance(msg, ModelError):
                return _ErrorState(msg)
            else:
                raise RuntimeError(f"Unexpected message received {msg}")

        return None

    def exit(self):
        # Drop the task handle, it has no effect if the task is finished
        self._fsm._model.drop(self._handle)
        # Reset the next action (self-clearing)
        self._fsm._next_action.value = ViewModelAction.NO_ACTION

    @property
    def instruction_text(self):
        # Format text according to event
        text = ""
        action = ""
        # Greetings
        if self._evt.clock_evt.action == ClockAction.CLOCK_IN:
            action = "Entrée "
            if self._evt.clock_evt.time.hour < 16:
                text += "Bonjour"
            else:
                text += "Bonsoir"
        else:
            action = "Sortie "
            text += "Au revoir"
        # Employee's firstname
        text += f" {self._evt.firstname}.\n"
        # Clock action
        time_h = self._evt.clock_evt.time.hour
        time_m = self._evt.clock_evt.time.minute
        text += f"{action} enregistrée à {time_h}h{time_m}."
        # Return formatted text
        return text
    
    @property
    def information_text(self):
        return "Chargement des informations..."

class _ConsultationActionState(_IViewModelState):
    """
    Make a consultation of employee's information.
    """

    def __init__(self, id: str):
        super().__init__()
        # Save employee's ID
        self._id = id

    def entry(self):
        # Start a consultation task
        self._handle = self._fsm._model.start_consultation_task(id=self._id, datetime=dt.datetime.now())

    def do(self) -> IStateBehavior:
        # Get the task result if available
        msg = self._fsm._model.get_result(self._handle)
        if msg:
            # The consultation task has completed
            if isinstance(msg, EmployeeData):
                return _ConsultationSuccessState(msg, timeout=False)
            elif isinstance(msg, ModelError):
                return _ErrorState(msg)
            else:
                raise RuntimeError(f"Unexpected message received {msg}")
        return None

    def exit(self):
        # Drop the task handle, it has no effect if the task is finished
        self._fsm._model.drop(self._handle)

class _ConsultationSuccessState(_IViewModelState):
    """
    Show the result of the consultation.
    This state can be configured to automatically end after a timeout is finished or on the scanning signal.
    It will always end when a new employee's ID is available.
    """

    # State duration in seconds
    DURATION = 10.0

    def __init__(self, data: EmployeeData, timeout: bool=True):
        super().__init__()
        # Save data and quit option
        self._data = data
        self._timeout = timeout

    def entry(self):
        # Set leave time
        self._leave = time.time() + self.DURATION
        # Resume scanner operation
        self._fsm._scanner.clear()
        self._fsm._scanner.resume()

    def do(self) -> IStateBehavior:
        # Leave the state if an employee ID is available
        if self._fsm._scanner.available():
            return _ScanningState()
        # Leave the state on scanning signal
        if self._fsm._next_action.value == ViewModelAction.SCANNING:
            return _ScanningState()
        # Leave the state when the timeout is elapsed
        if self._timeout and time.time() > self._leave:
            return _ScanningState()
        
        return None

    def exit(self):
        # Reset the next action (self-clearing)
        self._fsm._next_action.value = ViewModelAction.NO_ACTION

    @property
    def information_text(self):
        return str(self._data)

class _ErrorState(_IViewModelState):
    """
    An error has occurred. It must be acknowledged by setting the next action to the
    scanning state.
    """

    def __init__(self, error: ModelError=None):
        super().__init__()
        # Save error
        self._error = error

    def entry(self):
        # Reset next action to prevent wrong acknowledgment 
        self._fsm._next_action.value = ViewModelAction.NO_ACTION

    def do(self) -> IStateBehavior:
        # Check if acknowledged
        if self._fsm._next_action.value == ViewModelAction.SCANNING:
            return _ScanningState()
        
    def exit(self):
        # Reset next action 
        self._fsm._next_action.value = ViewModelAction.NO_ACTION

    @property
    def instruction_text(self):
        return "Une erreur est survenue"
    
    @property
    def information_text(self):
        return str(self._error) if self._error else "Aucune information disponible."
    