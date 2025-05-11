#!/usr/bin/env python3
"""
File: teambridge_viewmodel.py
Author: Bastian Cerf
Date: 02/03/2025
Description: 
    The ViewModel serves as the intermediary between the view and the model, 
    encapsulating the business logic of the application. It manages a state 
    machine to handle user interactions from the view and coordinates with 
    the model to schedule and execute the necessary tasks.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""
    
# Import logging and get the module logger
import logging
LOGGER = logging.getLogger(__name__)

# Import the state machine base interfaces
from ..common.state_machine import *
# Observable live data are used to communicate with the view
from ..common.live_data import LiveData
# Model is used to schedule tasks
from ..model.teambridge_model import *
# The barcode scanner allows to identify employee's ids
from ..io.barcode_scanner import BarcodeScanner
# Needed to interpret data containers from the model
from ..core.time_tracker_interface import ClockAction

# Other imports
from enum import Enum
import datetime as dt
from abc import ABC
import time

# Reduce visibility to public classes only
__all__ = ["TeamBridgeViewModel", "ViewModelAction"]

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
    All actions are auto-clearing, meaning they are automatically reset
    once the action is done. The default action is always the clock action.
    """
    # Move to clock in/out waiting state
    CLOCK_ACTION = 0
    # Move to consultation waiting state
    CONSULTATION = 1
    # Leave the current state, move to waiting for clock action state
    RESET_TO_CLOCK_ACTION = 2
    # Leave the current state, move to waiting for consultation action state
    RESET_TO_CONSULTATION = 3
    # Default action
    DEFAULT_ACTION = CLOCK_ACTION

class TeamBridgeViewModel(IStateMachine):
    """
    Application state machine.
    """

    def __init__(self, model: TeamBridgeModel, 
                 scanner: BarcodeScanner,
                 cam_idx: int, 
                 scan_rate: float, 
                 debug_mode: bool=False):
        """
        Create the viewmodel state machine.

        Args:
            model: `TeamBridgeModel` reference on the model to use to perform tasks
            scanner: `BarcodeScanner` reference on the barcode scanner to use to identify ids
            cam_idx: `int` barcode scanner camera id
            scan_rate: `float` barcode scanner rate in Hz
            debug_mode: `bool` True to show a live window of the scanner view
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
        # Set default view model next action
        self._next_action = ViewModelAction.DEFAULT_ACTION
        # Create viewmodel live data
        self._current_state = LiveData[str](str(self._state))
        self._main_title_text = LiveData[str]("")
        self._main_subtitle_text = LiveData[str]("")
        self._panel_title_text = LiveData[str]("")
        self._panel_subtitle_text = LiveData[str]("")
        self._panel_content_text = LiveData[str]("")

    def run(self):
        """
        Run the state machine. Must be called at fixed interval.
        """
        # Run the state machine
        super().run()

    def on_state_changed(self, old_state):
        """
        Called by the state machine on state change.
        """
        LOGGER.info(f"State changed from {old_state} to {self._state}.")
        # The state machine must work with known state types
        assert isinstance(self._state, _IViewModelState)
        # Update the state machine data
        self._current_state.value = str(self._state)
        # The texts for the view are updated on state change, as it is for a Moore
        # state machine. This can be limiting in some cases where extra states must
        # be added. This design might be re-evaluated in the future.
        self._main_title_text.value     = self._state.main_title_text
        self._main_subtitle_text.value  = self._state.main_subtitle_text
        self._panel_title_text.value    = self._state.panel_title_text    
        self._panel_subtitle_text.value = self._state.panel_subtitle_text
        self._panel_content_text.value  = self._state.panel_content_text

    @property
    def next_action(self) -> ViewModelAction:
        """
        Returns:
            ViewModelAction: the next action the viewmodel is going to perform
        """
        return self._next_action

    @next_action.setter
    def next_action(self, action: ViewModelAction):
        """
        Program the next viewmodel action.

        Args:
            action: `ViewModelAction` next action
        """
        self._next_action = action

    @property
    def current_state(self) -> LiveData[str]:
        """
        Machine states are expressed as strings. 

        Returns:
            LiveData[str]: observable on the current machine state as a string
        """
        return self._current_state

    def close(self):
        """
        Close the viewmodel. It will automatically close the barcode scanner and the
        model in use.
        """
        self._scanner.close(join=True) # Close synchronously
        self._model.close()

    ### Get UI information as observables ###

    @property
    def main_title_text(self) -> LiveData[str]:
        """
        The main title is used to give an instruction to the user or inform of
        an important information.

        Returns:
            LiveData[str]: text as an observable
        """
        return self._main_title_text

    @property
    def main_subtitle_text(self) -> LiveData[str]:
        """
        The subtitle is used as an additional piece of information to the main title.

        Returns:
            LiveData[str]: text as an observable
        """
        return self._main_subtitle_text

    @property
    def panel_title_text(self) -> LiveData[str]:
        """
        The title of the information panel. Typically always visible.

        Returns:
            LiveData[str]: text as an observable
        """
        return self._panel_title_text

    @property
    def panel_subtitle_text(self) -> LiveData[str]:
        """
        The subtitle of the information panel.

        Returns:
            LiveData[str]: text as an observable
        """
        return self._panel_subtitle_text

    @property
    def panel_content_text(self) -> LiveData[str]:
        """
        The content of the information panel. The panel is typically hidden in
        most states and shows up for states that must display more information.

        Returns:
            LiveData[str]: text as an observable
        """
        return self._panel_content_text

class _IViewModelState(IStateBehavior[TeamBridgeViewModel], ABC):
    """
    Define the base interface for a state of the viewmodel. Provide
    getters for the different UI information in the state.
    """

    def __repr__(self):
        # Return the class name and remove leading underscore
        return self.__class__.__name__[1:]

    @property
    def main_title_text(self) -> str:
        return "" # Erase last text

    @property
    def main_subtitle_text(self) -> str:
        return "" # Erase last text

    @property
    def panel_title_text(self) -> str:
        return "" # Erase last text

    @property
    def panel_subtitle_text(self) -> str:
        return "" # Erase last text

    @property
    def panel_content_text(self) -> str:
        return "" # Erase last text

class _InitialState(_IViewModelState):
    """
    Role:
        Initialize and open the barcode scanner.
    Entry:
        - At machine state initialization
    Exit:
        - Once the barcode scanner is opened and scanning
    """

    # Delay in seconds between scanner opening retries
    RETRY_DELAY = 10.0

    def entry(self):
        # Configure the barcode scanner
        self._fsm._scanner.configure(regex=EMPLOYEE_REGEX, 
                                     extract_group=EMPLOYEE_REGEX_GROUP,
                                     timeout=SCAN_ID_TIMEOUT,
                                     debug_mode=self._fsm._debug_mode)
        # Try to open on entry
        self.__open_scanner()
        
    def __open_scanner(self):
        # Open the scanner
        try:
            self._fsm._scanner.open(cam_idx=self._fsm._cam_idx, scan_rate=self._fsm._scan_rate)
        except RuntimeError as e:
            LOGGER.warning(f"Failed to open the barcode scanner. It appears to be running but is not actively scanning.")
        # Set next retry time
        self._next_retry = time.time() + self.RETRY_DELAY

    def do(self) -> IStateBehavior:
        # Check if the scanner is open
        if self._fsm._scanner.is_scanning():
            # Go to scanning state
            return _WaitClockActionState()
        # Check if a retry should be done
        if time.time() > self._next_retry:
            self.__open_scanner()
        # Stay in this state as long as the scanner is closed
        return None
    
    @property
    def main_title_text(self):
        return "Hors service"
    
    @property
    def panel_title_text(self):
        return "Ouverture du scanner..."

class _WaitClockActionState(_IViewModelState):
    """
    Role:
        Poll the barcode scanner until an employee's ID is found and start 
        a clock action.
    Entry:
        - Once the barcode scanner is initialized
        - After a consultation success
        - When changing the next action
    Exit:
        - Once an id has been scanned
    """

    def entry(self):
        # Set the next action accordingly
        self._fsm.next_action = ViewModelAction.CLOCK_ACTION
        # Make sure the barcode scanner is scanning on entry.
        self._fsm._scanner.clear() # Clear for safety
        self._fsm._scanner.resume()

    def do(self) -> IStateBehavior:
        # Check that the scanner is still scanning
        if not self._fsm._scanner.is_scanning():
            # Return to initial state, an error may have occurred
            return _InitialState()
            
        # Manage state change
        if self._fsm.next_action == ViewModelAction.CONSULTATION:
            # Move to waiting for consultation action
            return _WaitConsultationActionState()

        # Check if an employee ID is available
        if self._fsm._scanner.available():
            # Read scanned ID
            id = self._fsm._scanner.read_next()
            # Move to clock action state
            return _ClockActionState(id)

        return None
    
    def exit(self):
        # Pause the scanner to prevent scanning multiple IDs while processing one
        self._fsm._scanner.pause()
    
    @property
    def main_title_text(self):
        return "Veuillez présenter votre badge"

    @property
    def main_subtitle_text(self):
        return "Mode de timbrage"

class _WaitConsultationActionState(_IViewModelState):
    """
    Role:
        Poll the scanner until an employee's ID is found and start a
        consultation action.
    Entry:
        - When changing the next action
    Exit:
        - Once an id has been scanned
    """

    def entry(self):
        # Set the next action accordingly
        self._fsm.next_action = ViewModelAction.CONSULTATION
        # Make sure the barcode scanner is scanning on entry.
        self._fsm._scanner.clear() # Clear for safety
        self._fsm._scanner.resume()

    def do(self) -> IStateBehavior:
        # Check that the scanner is still scanning
        if not self._fsm._scanner.is_scanning():
            # Return to initial state, an error may have occurred
            return _InitialState()
            
        # Manage state change
        if self._fsm.next_action == ViewModelAction.CLOCK_ACTION:
            # Move to waiting for consultation action
            return _WaitClockActionState()

        # Check if an employee ID is available
        if self._fsm._scanner.available():
            # Read scanned ID
            id = self._fsm._scanner.read_next()
            # Move to clock action state
            return _ConsultationActionState(id)

        return None
    
    def exit(self):
        # Pause the scanner to prevent scanning multiple IDs while processing one
        self._fsm._scanner.pause()
    
    @property
    def main_title_text(self):
        return "Veuillez présenter votre badge"
    
    @property
    def main_subtitle_text(self):
        return "Mode de consultation"

class _ClockActionState(_IViewModelState):
    """
    Role:
        Clock in an employee who's clocked out and out an employee who's clocked in.
    Entry:
        - Once an id has been scanned 
    Exit:
        - Once the clock in/out task is performed
    """

    def __init__(self, id: str):
        super().__init__()
        # Save employee ID
        self._id = id

    def entry(self):
        # Reset next action
        self._fsm.next_action = ViewModelAction.DEFAULT_ACTION
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

class _ClockSuccessState(_IViewModelState):
    """
    Role:
        After the clock in/out task succeeded, display the welcome message and choose the
        next action. Currently it performs an automatic consultation.
    Entry:
        - After the clock in/out task succeeded
    Exit:
        - When consultation data are available
    """

    def __init__(self, event: EmployeeEvent):
        super().__init__()
        # Save employee's event
        self._evt = event

    def entry(self):
        # Start a consultation task
        self._handle = self._fsm._model.start_consultation_task(self._evt.id, dt.datetime.now())

    def do(self) -> IStateBehavior:
        # If a new ID is available, return to scanning state
        if self._fsm._scanner.available():
            return _WaitClockActionState()
        # If the consultation is done, move in presentation state
        msg = self._fsm._model.get_result(self._handle)
        if msg:
            if isinstance(msg, EmployeeData):
                return _ConsultationSuccessState(msg, timeout=20.0)
            elif isinstance(msg, ModelError):
                return _ErrorState(msg)
            else:
                raise RuntimeError(f"Unexpected message received {msg}")

        return None

    def exit(self):
        # Drop the task handle, it has no effect if the task is finished
        self._fsm._model.drop(self._handle)

    @property
    def main_title_text(self):
        # Format text according to event
        text = ""
        # Greetings
        if self._evt.clock_evt.action == ClockAction.CLOCK_IN:
            text = "Entrée "
        else:
            text = "Sortie "
        # Clock action
        text += "enregistrée"
        # Return formatted text
        return text
    
    @property
    def main_subtitle_text(self):
        # Format text according to event
        text = ""
        # Greetings
        if self._evt.clock_evt.action == ClockAction.CLOCK_IN:
            if self._evt.clock_evt.time.hour < 16:
                text += "Bonjour"
            else:
                text += "Bonsoir"
        else:
            text += "Au revoir"
        # Employee's firstname
        text += f" {self._evt.firstname}"
        # Return formatted text
        return text

class _ConsultationActionState(_IViewModelState):
    """
    Role:
        Make a consultation of employee's information.
    Entry:
        - Once an id has been scanned
    Exit:
        - When the consultation task is done
    """

    def __init__(self, id: str):
        super().__init__()
        # Save employee's ID
        self._id = id

    def entry(self):
        # Reset next action
        self._fsm.next_action = ViewModelAction.DEFAULT_ACTION
        # Start a consultation task
        self._handle = self._fsm._model.start_consultation_task(id=self._id, datetime=dt.datetime.now())

    def do(self) -> IStateBehavior:
        # Get the task result if available
        msg = self._fsm._model.get_result(self._handle)
        if msg:
            # The consultation task has completed
            if isinstance(msg, EmployeeData):
                return _ConsultationSuccessState(msg, timeout=60.0)
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
    Role:
        Show the result of the consultation.
    Entry:
        - When the consultation task is done
    Exit:
        - When the exit signal is received
        - When the timeout is elapsed
    """

    def __init__(self, data: EmployeeData, timeout=15.0):
        super().__init__()
        # Save data and quit option
        self._data = data
        self._timeout = timeout

    def entry(self):
        # Set leave time
        self._leave = time.time() + self._timeout

    def do(self) -> IStateBehavior:
        # Leave the state if an employee ID is available
        if self._fsm._scanner.available():
            return _WaitClockActionState()
        # Leave the state on reset signal
        if self._fsm.next_action == ViewModelAction.RESET_TO_CLOCK_ACTION:
            return _WaitClockActionState()
        elif self._fsm.next_action == ViewModelAction.RESET_TO_CONSULTATION:
            return _WaitConsultationActionState()
        # Leave the state when the timeout is elapsed
        if time.time() > self._leave:
            # Set default state
            self._fsm.next_action = ViewModelAction.DEFAULT_ACTION
            return _WaitClockActionState()
        
        return None

    @property
    def panel_title_text(self):
        return f"{self._data.firstname} {self._data.name}"

    @property
    def panel_content_text(self):
        return (f"Solde journalier : {self.format_dt(self._data.daily_worked_time)}"
                f" / {self.format_dt(self._data.daily_scheduled_time)}\n"
                f"Balance : {self.format_dt(self._data.daily_balance)}\n"
                f"Solde mensuel : {self.format_dt(self._data.monthly_balance)}\n")

    def format_dt(self, td: dt.timedelta):
        # Ensure the information is available
        if not isinstance(td, dt.timedelta):
            return "indisponible"
        # Available, format time
        total_minutes = int(td.total_seconds() // 60)
        sign = "-" if total_minutes < 0 else ""
        abs_minutes = abs(total_minutes)
        hours, minutes = divmod(abs_minutes, 60)
        return f"{sign}{hours:02}:{minutes:02}"

class _ErrorState(_IViewModelState):
    """
    Role:
        Block the state machine and show an error until acknowledgment.
    Entry:
        - Form anywhere, on error
    Exit:
        - Upon acknowledgment by sengind the reset to clock action signal
    """

    def __init__(self, error: ModelError=None):
        super().__init__()
        # Save error
        self._error = error

    def entry(self):
        # Reset next action to prevent wrong acknowledgment 
        self._fsm.next_action = ViewModelAction.DEFAULT_ACTION

    def do(self) -> IStateBehavior:
        # Check if acknowledged
        if self._fsm.next_action == ViewModelAction.RESET_TO_CLOCK_ACTION:
            return _WaitClockActionState()

    @property
    def main_title_text(self):
        return "Une erreur est survenue"
    
    @property
    def main_subtitle_text(self):
        return "Veuillez vous addresser à la direction"
    
    @property
    def panel_subtitle_text(self):
        return self._error.message
