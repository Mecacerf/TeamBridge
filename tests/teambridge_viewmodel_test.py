#!/usr/bin/env python3
"""
File: teambridge_viewmodel_test.py
Author: Bastian Cerf
Date: 20/04/2025
Description:
    Description:
        Unit test the TeamBridgeViewModel module to validate expected
        behaviors.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import time
import logging
import datetime as dt

# Internal libraries
from .test_constants import *
from .classes_mocks import BarcodeScannerMock
from viewmodel.teambridge_viewmodel import *

########################################################################
#                           Tests constants                            #
########################################################################

logger = logging.getLogger(__name__)

TEST_DATE = dt.date(year=2025, month=3, day=10)  # 10 March 2025 is a monday

########################################################################
#                             Unit tests                               #
########################################################################


def wait_state(viewmodel: TeamBridgeViewModel, state: str, timeout: float = 20):
    """
    Run the viewmodel until it enters the expected state.
    Assert false after the timeout is elapsed.
    """
    timeout = time.time() + timeout
    while viewmodel.current_state.value != state:
        # Check that the timeout is not reached and run the viewmodel
        assert time.time() < timeout
        viewmodel.run()
        time.sleep(0.01)


def test_open_scanner(
    viewmodel_scanner: tuple[TeamBridgeViewModel, BarcodeScannerMock],
):
    """
    Open / close the scanner and check the viewmodel state.
    """
    viewmodel, scanner_mock = viewmodel_scanner

    # Run the viewmodel and assert it is in initial state
    wait_state(viewmodel, "InitialState")

    # After the scanner has been opened, the state is waiting for a clock action
    logger.info("Set scanning True")
    scanner_mock.set_scanning(True)
    wait_state(viewmodel, "WaitClockActionState")

    # On scanner failure, return to initial state and try to reopen
    logger.info("Set scanning False")
    scanner_mock.set_scanning(False)
    wait_state(viewmodel, "InitialState")

    # If the scanner recovers, return to initial state
    logger.info("Set scanning True")
    scanner_mock.set_scanning(True)
    wait_state(viewmodel, "WaitClockActionState")


def test_clock_action(
    viewmodel_scanner: tuple[TeamBridgeViewModel, BarcodeScannerMock],
):
    """
    Clock in the test employee.
    """
    viewmodel, scanner_mock = viewmodel_scanner

    # Move to scanning state
    scanner_mock.set_scanning(True)
    wait_state(viewmodel, "WaitClockActionState")

    # Set next action to clock action
    viewmodel.next_action = ViewModelAction.CLOCK_ACTION

    # Post an employee ID, shall move to clocking state
    scanner_mock.add_result(TEST_EMPLOYEE_ID)
    wait_state(viewmodel, "ClockActionState")

    # Then shall move to ClockSuccessState
    wait_state(viewmodel, "ClockSuccessState")
    # Shall automatically move to consultation state
    wait_state(viewmodel, "ConsultationSuccessState")
    # And finally back to scanning state after the presentation duration
    wait_state(viewmodel, "WaitClockActionState", 21.0)

    # The next action has been reset
    assert viewmodel.next_action == ViewModelAction.DEFAULT_ACTION


def test_consultation(
    viewmodel_scanner: tuple[TeamBridgeViewModel, BarcodeScannerMock],
):
    """
    Clock in the test employee.
    """
    viewmodel, scanner_mock = viewmodel_scanner

    # Move to scanning state
    scanner_mock.set_scanning(True)
    wait_state(viewmodel, "WaitClockActionState")

    # Set next action to consultation
    viewmodel.next_action = ViewModelAction.CONSULTATION
    # Shall move to waiting for consultation action
    wait_state(viewmodel, "WaitConsultationActionState")

    # Post an employee ID, shall move to consultation action state
    scanner_mock.add_result(TEST_EMPLOYEE_ID)
    wait_state(viewmodel, "ConsultationActionState")
    # Shall automatically move to consultation success state
    wait_state(viewmodel, "ConsultationSuccessState")

    # Shall return in consultation state on reset to consultation signal
    viewmodel.next_action = ViewModelAction.RESET_TO_CONSULTATION
    wait_state(viewmodel, "WaitConsultationActionState")

    # Shall be able to move back to wait for clock action state
    viewmodel.next_action = ViewModelAction.CLOCK_ACTION
    wait_state(viewmodel, "WaitClockActionState")


def test_error(viewmodel_scanner: tuple[TeamBridgeViewModel, BarcodeScannerMock]):
    """
    Enter the error state and reset to scanning state.
    """
    viewmodel, scanner_mock = viewmodel_scanner

    # Move to scanning state
    scanner_mock.set_scanning(True)
    wait_state(viewmodel, "WaitClockActionState")

    # Set next action to clock action
    viewmodel.next_action = ViewModelAction.CLOCK_ACTION

    # Post a wrong employee ID, shall move to clocking state
    scanner_mock.add_result("thisiswrongid8752145")
    wait_state(viewmodel, "ClockActionState")

    # Shall fail and move to error state
    wait_state(viewmodel, "ErrorState")
    # The next action has been reset
    assert viewmodel.next_action == ViewModelAction.DEFAULT_ACTION
    # Reset to scanning state, acknowledge the error
    viewmodel.next_action = ViewModelAction.RESET_TO_CLOCK_ACTION
    wait_state(viewmodel, "WaitClockActionState")
    # The next action has been reset to clock action
    assert viewmodel.next_action == ViewModelAction.CLOCK_ACTION
