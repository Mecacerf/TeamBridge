#!/usr/bin/env python3
"""
File: teambridge_viewmodel.py
Author: Bastian Cerf
Date: 02/03/2025
Description:
    The ViewModel serves as the intermediary between the view and the
    model, encapsulating the business logic of the application. It
    manages a state machine to handle user interactions from the view
    and coordinates with the model to schedule and execute the necessary
    tasks.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import logging
import datetime as dt
import time
from enum import Enum, auto
from abc import ABC
from typing import cast
from os.path import join

# Third-party libraries
from PIL import ImageFont

# Import internal modules
from common.state_machine import *
from common.live_data import LiveData  # For view communication
from common.reporter import ReportingService, ReportSeverity, Report, EmployeeReport
from model import *  # Task scheduling
from platform_io.barcode_scanner import BarcodeScanner  # Employee ID detection
from core.time_tracker import ClockAction  # Domain model enums
from core.attendance.attendance_validator import AttendanceErrorStatus
from local_config import LocalConfig

__all__ = ["TeamBridgeViewModel", "ViewModelAction"]

logger = logging.getLogger(__name__)
config = LocalConfig()
_scanner_conf = config.section("scanner")

# Timeout for the attendance list task
ATTENDANCE_LIST_TIMEOUT = 90.0

# Timeout for error state (triggered once a report has been sent)
ERROR_STATE_TIMEOUT = 20.0

# Font used for attendance list displaying
ATTENDANCE_LIST_FONT = join("assets", "fonts", "Inter_28pt-Regular.ttf")


class ViewModelAction(Enum):
    """
    Possible actions the viewmodel can perform.
    This enum is used to interact with the viewmodel.
    All actions are auto-clearing, meaning they are automatically reset
    once the action is done. The default action is always the clock
    action.
    """

    # Move to clock in/out waiting state
    CLOCK_ACTION = auto()
    # Move to consultation waiting state
    CONSULTATION = auto()
    # Perform an attendance list fetch
    ATTENDANCE_LIST = auto()
    # Leave the current state, move to waiting for clock action state
    RESET_TO_CLOCK_ACTION = auto()
    # Leave the current state, move to waiting for consultation action state
    RESET_TO_CONSULTATION = auto()
    # Default action
    DEFAULT_ACTION = CLOCK_ACTION


class TeamBridgeViewModel(IStateMachine):
    """
    Application state machine.
    """

    def __init__(
        self,
        model: TeamBridgeScheduler,
        scanner: BarcodeScanner,
        reporter: Optional[ReportingService] = None,
    ):
        """
        Create the viewmodel state machine.

        Args:
            model (TeamBridgeScheduler): Reference on the scheduler to use
                to perform tasks.
            scanner (BarcodeScanner): Reference on the barcode scanner to
                use to identify employees ids.
            reporter (Optional[Reporter]): Optionally provide a reporter
                object for employee errors / warnings.
        """
        # Enter the initial state
        # The entry() method is called at first run() call
        super().__init__(_InitialState())

        self._model = model
        self._scanner = scanner
        self._reporter = reporter
        self._cam_idx = _scanner_conf["camera_id"]
        self._scan_rate = _scanner_conf["scan_rate"]
        self._debug_mode = config.section("debug")["debug"]

        self._next_action = ViewModelAction.DEFAULT_ACTION

        # Live data are observed by the view
        self._current_state = LiveData[str](str(self._state))
        self._main_title_text = LiveData[str]("")
        self._main_subtitle_text = LiveData[str]("")
        self._panel_title_text = LiveData[str]("")
        self._panel_subtitle_text = LiveData[str]("")
        self._panel_content_text = LiveData[str]("")
        self._reporting_service = LiveData[bool](False)

    @property
    def model(self) -> TeamBridgeScheduler:
        return self._model

    @property
    def scanner(self) -> BarcodeScanner:
        return self._scanner

    @property
    def reporter(self) -> Optional[ReportingService]:
        return self._reporter

    @property
    def camera_idx(self) -> int:
        return self._cam_idx

    @property
    def camera_scan_rate(self) -> float:
        return self._scan_rate

    @property
    def debug_mode(self) -> bool:
        return self._debug_mode

    def run(self):
        """
        Run the state machine. Must be called at fixed interval.
        """
        # Run the state machine
        super().run()

        # Update service status
        self._reporting_service.value = not self._reporter or self._reporter.available

    def on_state_changed(
        self, old_state: Optional[IStateBehavior], new_state: IStateBehavior
    ):
        """
        Called by the state machine on state change.
        """
        logger.info(f"State changed from {old_state!r} to {self._state!r}.")

        # The state machine must work with subclasses of _IViewModelState
        assert isinstance(self._state, _IViewModelState)

        self._current_state.value = repr(self._state)

        # The texts for the view are updated on state change, as it is for a Moore
        # state machine. This can be limiting in some cases where extra states must
        # be added. This design might be re-evaluated in the future.
        self._main_title_text.value = self._state.main_title_text
        self._main_subtitle_text.value = self._state.main_subtitle_text
        self._panel_title_text.value = self._state.panel_title_text
        self._panel_subtitle_text.value = self._state.panel_subtitle_text
        self._panel_content_text.value = self._state.panel_content_text

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
        Machine state are expressed as a string.

        Returns:
            LiveData[str]: observable on the current machine state as a string
        """
        return self._current_state

    def close(self):
        """
        Close the viewmodel. It will automatically close the barcode scanner and the
        model in use.
        """
        self._scanner.close(join=True)  # Close synchronously
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
        The content of the information panel. The panel is typically
        hidden in most states and shows up for states that must display
        more information.

        Returns:
            LiveData[str]: text as an observable
        """
        return self._panel_content_text

    @property
    def reporting_service_status(self) -> LiveData[bool]:
        """
        Get the reporting service status. If no reporting service is
        configured, this is always `True`.
        """
        return self._reporting_service


class _IViewModelState(IStateBehavior, ABC):
    """
    Define the base interface for a viewmodel state. Provide getters for
    the different UI information in the state.
    """

    @property
    def fsm(self) -> TeamBridgeViewModel:
        return cast(TeamBridgeViewModel, self._fsm)

    def __repr__(self):
        # Return the class name and remove leading underscore
        return self.__class__.__name__[1:]

    @property
    def main_title_text(self) -> str:
        return ""  # Erase last text

    @property
    def main_subtitle_text(self) -> str:
        return ""  # Erase last text

    @property
    def panel_title_text(self) -> str:
        return ""  # Erase last text

    @property
    def panel_subtitle_text(self) -> str:
        return ""  # Erase last text

    @property
    def panel_content_text(self) -> str:
        return ""  # Erase last text


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
        """
        Initial state entry: the barcode scanner is configured and
        opened.
        """
        self.fsm.scanner.configure(
            regex=_scanner_conf["regex"],
            extract_group=_scanner_conf["regex_group"],
            timeout=_scanner_conf["scanned_id_delay"],
            debug_mode=self.fsm.debug_mode,
        )

        self.__open_scanner()

    def __open_scanner(self):
        """
        Try to open the barcode scanner. Note that the process may take
        some time depending on OS, device, etc.
        """
        try:
            self.fsm.scanner.open(
                cam_idx=self.fsm.camera_idx, scan_rate=self.fsm.camera_scan_rate
            )

        except RuntimeError:
            logger.warning(
                "Failed to open the barcode scanner. It appears to be "
                "running but is not actively scanning.",
                exc_info=True,
            )
        finally:
            self._next_retry = time.time() + self.RETRY_DELAY

    def do(self) -> Optional[IStateBehavior]:
        """
        Recall the open method when the delay is elapsed and leave the
        state once opened.
        Stay in this state as long as the scanner is closed.
        """
        if self.fsm.scanner.is_scanning():
            return _WaitClockActionState()

        if time.time() > self._next_retry:
            self.__open_scanner()

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
        self.fsm.next_action = ViewModelAction.CLOCK_ACTION
        # Make sure the barcode scanner is scanning on entry.
        self.fsm.scanner.clear()  # Clear for safety
        self.fsm.scanner.resume()

    def do(self) -> Optional[IStateBehavior]:
        if not self.fsm.scanner.is_scanning():
            # Return to initial state, an error may have occurred
            return _InitialState()

        # Manage state change
        if self.fsm.next_action == ViewModelAction.CONSULTATION:
            # Move to waiting for consultation action
            return _WaitConsultationActionState()
        elif self.fsm.next_action == ViewModelAction.ATTENDANCE_LIST:
            return _LoadAttendanceList()

        # Check if an employee ID is available
        if self.fsm.scanner.available():
            # Read scanned ID
            scanned_id = self.fsm.scanner.read_next()
            # Move to clock action state
            return _ClockActionState(scanned_id)

    def exit(self):
        # Pause the scanner to prevent scanning multiple IDs while processing one
        self.fsm.scanner.pause()

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
        self.fsm.next_action = ViewModelAction.CONSULTATION
        # Make sure the barcode scanner is scanning on entry.
        self.fsm.scanner.clear()  # Clear for safety
        self.fsm.scanner.resume()

    def do(self) -> Optional[IStateBehavior]:
        if not self.fsm.scanner.is_scanning():
            # Return to initial state, an error may have occurred
            return _InitialState()

        # Manage state change
        if self.fsm.next_action == ViewModelAction.CLOCK_ACTION:
            # Move to waiting for consultation action
            return _WaitClockActionState()
        elif self.fsm.next_action == ViewModelAction.ATTENDANCE_LIST:
            return _LoadAttendanceList()

        # Check if an employee ID is available
        if self.fsm.scanner.available():
            # Read scanned ID
            scanned_id = self.fsm.scanner.read_next()
            # Move to clock action state
            return _ConsultationActionState(scanned_id)

    def exit(self):
        # Pause the scanner to prevent scanning multiple IDs while processing one
        self.fsm.scanner.pause()

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
        self.fsm.next_action = ViewModelAction.DEFAULT_ACTION
        # Start a clock action task and save the task handle
        self._handle = self.fsm.model.start_clock_action_task(
            self._id, dt.datetime.now()
        )

    def do(self) -> Optional[IStateBehavior]:
        # Get the task result if available
        msg = self.fsm.model.get_result(self._handle)
        if msg:
            # The clock action task has completed
            if isinstance(msg, EmployeeEvent):
                return _ClockSuccessState(msg)
            elif isinstance(msg, ModelError):
                return _ErrorState("Clock action task failed", msg)
            else:
                raise RuntimeError(f"Unexpected message received {msg}")

    def exit(self):
        # Drop the task handle, it has no effect if the task is finished
        self.fsm.model.drop(self._handle)


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
        self._handle = self.fsm.model.start_consultation_task(
            self._evt.id, dt.datetime.now()
        )

    def do(self) -> Optional[IStateBehavior]:
        # If a new ID is available, return to scanning state
        if self.fsm.scanner.available():
            return _WaitClockActionState()
        # If the consultation is done, move in presentation state
        msg = self.fsm.model.get_result(self._handle)
        if msg:
            if isinstance(msg, EmployeeData):
                # Always send an error report when coming from clocking mode
                return _ConsultationSuccessState(msg, timeout=20.0, should_report=True)
            elif isinstance(msg, ModelError):
                return _ErrorState("Consultation task failed", msg)
            else:
                raise RuntimeError(f"Unexpected message received {msg}")

    def exit(self):
        # Drop the task handle, it has no effect if the task is finished
        self.fsm.model.drop(self._handle)

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
        self.fsm.next_action = ViewModelAction.DEFAULT_ACTION
        # Start a consultation task
        self._handle = self.fsm.model.start_consultation_task(
            self._id, dt.datetime.now()
        )

    def do(self) -> Optional[IStateBehavior]:
        # Get the task result if available
        msg = self.fsm.model.get_result(self._handle)
        if msg:
            # The consultation task has completed
            if isinstance(msg, EmployeeData):
                return _ConsultationSuccessState(msg, timeout=60.0)
            elif isinstance(msg, ModelError):
                return _ErrorState("Consultation task failed", msg)
            else:
                raise RuntimeError(f"Unexpected message received {msg}")

    def exit(self):
        # Drop the task handle, it has no effect if the task is finished
        self.fsm.model.drop(self._handle)


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

    def __init__(
        self, data: EmployeeData, timeout: float = 15.0, should_report: bool = False
    ):
        super().__init__()
        # Save data and quit option
        self._data = data
        self._timeout = timeout
        self._should_report = should_report

    def entry(self):
        # Set leave time
        self._leave = time.time() + self._timeout

        # Send a warning / error report if configured
        if self._should_report and self.fsm.reporter:
            self.__send_report(self.fsm.reporter)

    def __send_report(self, reporter: ReportingService):
        # Translate error status to report severity
        dominant = self._data.dominant_error
        severity = ReportSeverity.INFO
        if dominant.status is AttendanceErrorStatus.WARNING:
            severity = ReportSeverity.WARNING
        elif dominant.status is AttendanceErrorStatus.ERROR:
            severity = ReportSeverity.ERROR

        body = f"Most critical error for employee: \n- {dominant}"
        if self._data.date_errors:
            body += "\n\nAll errors:\n"
            body += "\n".join(
                [f"- {date}: {err}" for date, err in self._data.date_errors.items()]
            )

        # Report employee error
        reporter.send_report(
            EmployeeReport(
                severity,
                f"{self._data.firstname} {self._data.name}",
                body,
                employee_id=self._data.id,
                name=self._data.name,
                firstname=self._data.firstname,
                error_id=dominant.error_id,
            )
        )

    def do(self) -> Optional[IStateBehavior]:
        # Leave the state if an employee ID is available
        if self.fsm.scanner.available():
            return _WaitClockActionState()

        # Leave the state on reset signal
        if self.fsm.next_action == ViewModelAction.RESET_TO_CLOCK_ACTION:
            return _WaitClockActionState()
        elif self.fsm.next_action == ViewModelAction.RESET_TO_CONSULTATION:
            return _WaitConsultationActionState()

        # Leave the state when the timeout is elapsed
        if time.time() > self._leave:
            # Set default state
            self.fsm.next_action = ViewModelAction.DEFAULT_ACTION
            return _WaitClockActionState()

    @property
    def panel_title_text(self):
        return f"{self._data.firstname} {self._data.name}"

    @property
    def panel_content_text(self):
        data = self._data

        if data.dominant_error.status == AttendanceErrorStatus.ERROR:
            # Show the error panel
            lines = [
                "Des erreurs empêchent l'affichage correct des informations. ",
                "Veuillez vous adresser au secrétariat.",
                "",
            ]

            # Keep only errors
            errors = {
                date: error
                for date, error in data.date_errors.items()
                if error.status is AttendanceErrorStatus.ERROR
            }

            lines.append(f"\u26a0 Erreur{"" if len(data.date_errors) == 1 else "s"}:")
            lines.extend(
                [
                    f"   \u2022 {self._fmt_date(date)}: {err.description}"
                    for date, err in self._data.date_errors.items()
                    if err.status is AttendanceErrorStatus.ERROR
                ]
            )

            # The dominant error may not be in the scanned range
            if len(errors) == 0:
                lines.append(
                    f"   \u2022 date inconnue: {data.dominant_error.description}"
                )
        else:
            # Extract and format
            yty_bal = self._fmt_dt(
                data.yty_balance, data.min_allowed_balance, data.max_allowed_balance
            )
            mty_bal = self._fmt_dt(data.month_to_yday_balance)
            day_bal = self._fmt_dt(data.day_balance)
            day_wtm = self._fmt_dt(data.day_worked_time)
            day_stm = self._fmt_dt(data.day_schedule_time)
            mth_vac = self._fmt_days(data.month_vacation)
            rem_vac = self._fmt_days(data.remaining_vacation)

            # Normal information panel
            lines = [
                f"\u2022 Présent: {'oui' if data.clocked_in else 'non'}",
                f"\u2022 Balance totale au jour précédent: {yty_bal}",
            ]

            # Add a warning line if balance is out of range
            if data.yty_balance:
                # Clamp if not existing
                min_bal = data.min_allowed_balance or data.yty_balance
                max_bal = data.max_allowed_balance or data.yty_balance
                if not min_bal <= data.yty_balance <= max_bal:
                    # Show allowed balance range only if both ends are configured
                    rng = ""
                    if data.min_allowed_balance and data.max_allowed_balance:
                        rng = (
                            f" ({self._fmt_dt(data.min_allowed_balance)} / "
                            f"{self._fmt_dt(data.max_allowed_balance)})"
                        )

                    lines.append(
                        f"   \u26a0 Hors de la plage autorisée{rng}, "
                        "veuillez régulariser rapidement \u26a0"
                    )

            lines.extend(
                [
                    f"\u2022 Balance du mois au jour précédent: {mty_bal}",
                    f"\u2022 Balance du jour: {day_bal} ({day_wtm} / {day_stm})",
                    f"\u2022 Vacances ce mois: {mth_vac}",
                    f"\u2022 Vacances à planifier: {rem_vac}",
                ]
            )

            # Add errors if any
            if data.date_errors:
                lines.append(
                    f"\u26a0 Problème{"" if len(data.date_errors) == 1 else "s"}:"
                )
                lines.extend(
                    [
                        f"   \u2022 {self._fmt_date(date)}: {err.description}"
                        for date, err in data.date_errors.items()
                    ]
                )

        return "\n".join(lines)

    def _fmt_dt(
        self,
        td: Optional[dt.timedelta],
        td_min: Optional[dt.timedelta] = None,
        td_max: Optional[dt.timedelta] = None,
    ):
        if td is None:
            return "indisponible"

        # Check if a warning must be shown
        warn = ""
        if td_min and td < td_min:
            warn = f" (\u26a0 min. {self._fmt_dt(td_min)} \u26a0)"
        if td_max and td > td_max:
            warn = f" (\u26a0 max. {self._fmt_dt(td_max)} \u26a0)"

        total_minutes = int(td.total_seconds() // 60)
        sign = "-" if total_minutes < 0 else ""
        abs_minutes = abs(total_minutes)
        hours, minutes = divmod(abs_minutes, 60)

        if hours == 0:
            return f"{sign}{minutes} minute{"s" if minutes > 1 else ""}{warn}"
        elif minutes == 0:
            return f"{sign}{hours}h{warn}"
        return f"{sign}{hours}h{minutes:02}{warn}"

    def _fmt_date(self, date: dt.date):
        return dt.date.strftime(date, "%d.%m.%Y")

    def _fmt_days(self, days: Optional[float]) -> str:
        """
        Format a floating number of days as a human-readable string
        with integer and Unicode fraction components.
        E.g., 1.26 → '1j ¼', 0.48 → '½j', 1.93 → '2j'
        """
        if days is None:
            return "indisponible"

        # Manual thresholds
        thresholds = [
            (0.875, "", 1),  # Round up
            (0.625, "\u00be", 0),  # ¾
            (0.375, "\u00bd", 0),  # ½
            (0.125, "\u00bc", 0),  # ¼
            (0.0, "", 0),  # No fraction
        ]

        integer = int(days)
        decimal = days - integer

        fraction_symbol = ""
        for threshold, symbol, increment in thresholds:
            if decimal >= threshold:
                fraction_symbol = symbol
                integer += increment
                break

        parts = []
        if integer > 0:
            parts.append(f"{integer}j")
            if fraction_symbol:
                parts.append(fraction_symbol)
        elif fraction_symbol:
            parts.append(f"{fraction_symbol}j")
        else:
            parts.append("0j")

        return " ".join(parts)


class _LoadAttendanceList(_IViewModelState):
    """
    Role:
        Load the attendance list.
    Entry:
        - When the next action is ATTENDANCE_LIST
    Exit:
        - When the attendance list task is finished
        - When the timeout is elapsed
    """

    def entry(self):
        # Schedule the attendance list task
        self._handle = self.fsm.model.start_attendance_list_task(dt.datetime.now())
        # Prepare a task watchdog
        self._timeout = time.time() + ATTENDANCE_LIST_TIMEOUT

    def do(self) -> Optional[IStateBehavior]:
        # Check task result
        if self.fsm.model.available(self._handle):
            result = self.fsm.model.get_result(self._handle)

            if result and isinstance(result, AttendanceList):
                return _ShowAttendanceList(result)
            return _ErrorState("No attendance list result received.")

        # Check watchdog
        if time.time() > self._timeout:
            return _ErrorState(
                f"Timed out while loading attendance list "
                f"(more than {ATTENDANCE_LIST_TIMEOUT} sec elapsed)."
            )

    def exit(self):
        self.fsm.model.drop(self._handle)


class _ShowAttendanceList(_IViewModelState):
    """
    Role:
        Show the attendance list.
    Entry:
        - After the attendance list has been loaded.
    Exit:
        - When the next action is reset
        - When the timeout is elapsed
    """

    def __init__(self, result: AttendanceList):
        super().__init__()
        self._result = result

        # Load attendance list font
        self._font = ImageFont.truetype(ATTENDANCE_LIST_FONT, size=32)

    def entry(self):
        # Prepare timeout
        self._timeout = time.time() + ATTENDANCE_LIST_TIMEOUT
        # Show results
        logger.info(f"Fetched attendance list in {self._result.fetch_time:.2f} sec.")
        logger.info(
            f"Present: {", ".join([f"{info.firstname} {info.name} ({info.id})" 
            for info in self._result.present])}."
        )
        logger.info(
            f"Absent: {", ".join([f"{info.firstname} {info.name} ({info.id})" 
            for info in self._result.absent])}."
        )
        logger.info(
            f"Unknown: {", ".join(f"{info.firstname} {info.name} ({info.id})" 
            for info in self._result.unknown)}."
        )

    def do(self) -> Optional[IStateBehavior]:
        # Leave the state on reset signal or timeout
        if self.fsm.next_action == ViewModelAction.RESET_TO_CLOCK_ACTION:
            return _WaitClockActionState()
        elif self.fsm.next_action == ViewModelAction.RESET_TO_CONSULTATION:
            return _WaitConsultationActionState()
        elif time.time() > self._timeout:
            return _WaitClockActionState()

    @property
    def panel_title_text(self):
        return "Liste des présences"

    @property
    def panel_content_text(self):
        """
        Format the attendance list to be shown in the panel.
        """
        from math import ceil

        MAX_COL_ENTRIES = 12
        MAX_COL_NUMBER = 3
        MAX_NAME_LENGTH = 45  # In terms of space units
        COL_SPACING = 10

        # Show the names of clocked-in employees as well as unknown ones, to
        # inform that an error occurred with this employee and the system doesn't
        # know if he's present or absent.
        names = [f"{info.firstname} {info.name}" for info in self._result.present] + [
            (f"??? {info.firstname} {info.name}" if info.name else f"??? ID {info.id}")
            for info in self._result.unknown
        ]

        # Truncate too long names
        names = [self.__truncate(name, MAX_NAME_LENGTH) for name in names]

        if len(names) == 0:
            names = ["Il n'y a personne."]

        max_names = MAX_COL_ENTRIES * MAX_COL_NUMBER
        if len(names) > max_names:
            # Replace the last name to show the list continues
            names[max_names - 1] = f"+ {len(names) - max_names + 1} cachés..."

        ncols = min(ceil(len(names) / MAX_COL_ENTRIES), MAX_COL_NUMBER)

        # Split names in columns of MAX_COL_SIZE
        columns = [
            names[col * MAX_COL_ENTRIES : (col + 1) * MAX_COL_ENTRIES]
            for col in range(ncols)
        ]

        # Pad last column with empty strings
        columns[-1] += [""] * (MAX_COL_ENTRIES - len(columns[-1]))

        # Use longest name as the column width reference
        col_width = max([self.__text_width(name) for name in names]) + COL_SPACING

        # Print the names left justified
        lines = []
        for row in zip(*columns):
            line = "".join([self.__ljust(name, col_width) for name in row])
            lines.append(line)

        return "\n".join(lines)

    def __text_width(self, text: str) -> float:
        """
        Returns the text width ratio related to the space character.
        """
        return self._font.getlength(text) / self._font.getlength(" ")

    def __truncate(self, text: str, width: float) -> str:
        """
        Truncate the text to specified width.
        """
        for chars in range(1, len(text) + 1):
            if self.__text_width(text[:chars]) > width:
                # The text must be truncated
                return text[: chars - 1] + "."
        return text

    def __ljust(self, text: str, width: float) -> str:
        """
        Left justify with spaces to reach given width.
        """
        return text + (" " * max(0, round(width - self.__text_width(text))))


class _ErrorState(_IViewModelState):
    """
    Role:
        Block the state machine and show an error until acknowledgment.
    Entry:
        - Form anywhere, on error
    Exit:
        - Upon acknowledgment by sending the reset to clock action signal
    """

    def __init__(self, msg: str, error: Optional[ModelError] = None):
        super().__init__()
        self._message = msg
        self._error = error
        self._report = None
        self._timeout = None

    def entry(self):
        # Reset next action to prevent wrong acknowledgment
        self.fsm.next_action = ViewModelAction.DEFAULT_ACTION

        logger.error(f"State machine entered error state. Reason '{self._message}'.")
        if self._error:
            logger.error(
                f"A task failed with error ({self._error.error_code}) "
                f"'{self._error.message}'."
            )
            if self._error.employee_id:
                emp_id = self._error.employee_id
                emp_name = (
                    self._error.employee_name
                    if self._error.employee_name
                    else "unknown"
                )
                emp_firstname = (
                    self._error.employee_firstname
                    if self._error.employee_firstname
                    else "unknown"
                )
                logger.error(
                    f"Error occurred with employee ID='{emp_id}', "
                    f"name='{emp_name}', "
                    f"firstname='{emp_firstname}'."
                )

        # Try to send an application report
        self.__send_report()

    def __send_report(self):
        """Build and send the appropriate error report."""
        if self.fsm.reporter is None:
            return

        body = f"The application entered error state.\n\nError message: {self._message}"

        if not self._error:
            # Most simple error report
            self._report = Report(ReportSeverity.ERROR, "Runtime exception", body)

        elif not self._error.employee_id:
            # Has error code and message
            body += f"\nError code: {self._error.error_code}"
            body += f"\nSpecific message: {self._error.message}"
            self._report = Report(ReportSeverity.ERROR, "Runtime exception", body)

        else:
            # Complete employee report
            body += f"\nError code: {self._error.error_code}"
            body += f"\nSpecific message: {self._error.message}"
            self._report = EmployeeReport(
                ReportSeverity.ERROR,
                "Employee runtime exception",
                body,
                employee_id=self._error.employee_id,
                name=self._error.employee_name,
                firstname=self._error.employee_firstname,
            )

        self.fsm.reporter.send_report(self._report.attach_logs())

    def do(self) -> Optional[IStateBehavior]:
        # Check if acknowledged
        if self.fsm.next_action == ViewModelAction.RESET_TO_CLOCK_ACTION:
            return _WaitClockActionState()

        if self._report and self._report.is_sent() and self._timeout is None:
            # Program the state timeout once a report has been sent
            # successfully
            self._timeout = time.time() + ERROR_STATE_TIMEOUT

        if self._timeout and time.time() > self._timeout:
            return _WaitClockActionState()

    @property
    def main_title_text(self):
        return "Une erreur est survenue"

    @property
    def main_subtitle_text(self):
        return "Veuillez vous adresser au secrétariat"
