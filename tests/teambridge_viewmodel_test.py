#!/usr/bin/env python3
"""
File: teambridge_viewmodel_test.py
Author: Bastian Cerf
Date: 20/04/2025
Description:
    Description:
        Unit test the TeamBridgeViewModel module to validate expected behaviors.
    Usage:
        Use pytest to execute the tests. You can run it by executing the command below in the TeamBridge/ folder.
        - pytest

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

import time
import logging
import datetime as dt
from viewmodel.teambridge_viewmodel import *
from platform_io.barcode_scanner import BarcodeScanner

################################################
#               Tests constants                #
################################################

LOGGER = logging.getLogger(__name__)

TEST_EMPLOYEE_ID = "unit-test"
TEST_DATE = dt.date(year=2025, month=3, day=10)  # 10 March 2025 is a monday

################################################
#                    Mocking                   #
################################################


class BarcodeScannerMock:
    """
    Mock the barcode scanner functions. The functions of the given object will
    be temporarily replaced.
    """

    def __init__(self, scanner: BarcodeScanner, monkeypatch):
        """ """

        # Create the barcode scanner mocked functions
        # No effect functions
        def void(*args, **kwargs):
            pass

        monkeypatch.setattr(scanner, "configure", void)
        monkeypatch.setattr(scanner, "open", void)
        monkeypatch.setattr(scanner, "clear", void)
        monkeypatch.setattr(scanner, "close", void)
        monkeypatch.setattr(scanner, "pause", void)
        monkeypatch.setattr(scanner, "resume", void)

        # Mock the scanning flag
        self._scanning = False
        monkeypatch.setattr(scanner, "is_scanning", self.__is_scanning)

        # Mock the available and read functions
        self._results = []
        monkeypatch.setattr(scanner, "available", self.__available)
        monkeypatch.setattr(scanner, "read_next", self.__read_next)

    def __is_scanning(self):
        return self._scanning

    def __available(self):
        return len(self._results) > 0

    def __read_next(self):
        return self._results.pop()

    def set_scanning(self, value: bool):
        self._scanning = value

    def add_result(self, result):
        self._results.append(result)


def wait_state(viewmodel: TeamBridgeViewModel, state: str, timeout=10):
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


################################################
#                  Unit tests                  #
################################################


def test_open_scanner(teambridge_viewmodel, monkeypatch):
    """
    Open / close the scanner and check the viewmodel state.
    """
    # Unpack the fixture
    viewmodel, scanner = teambridge_viewmodel
    # Create the scanner mocking object
    scanner = BarcodeScannerMock(scanner, monkeypatch)

    # Run the viewmodel and assert it is in initial state
    wait_state(viewmodel, "InitialState")

    # After the scanner has been opened, the state is waiting for a clock action
    scanner.set_scanning(True)
    wait_state(viewmodel, "WaitClockActionState")

    # On scanner failure, return to initial state and try to reopen
    scanner.set_scanning(False)
    wait_state(viewmodel, "InitialState")

    # If the scanner recovers, return to initial state
    scanner.set_scanning(True)
    wait_state(viewmodel, "WaitClockActionState")


def test_clock_action(teambridge_viewmodel, monkeypatch):
    """
    Clock in the test employee.
    """
    # Unpack the fixture
    viewmodel, scanner = teambridge_viewmodel
    # Create the barcode mocking object
    scanner = BarcodeScannerMock(scanner, monkeypatch)

    # Move to scanning state
    scanner.set_scanning(True)
    wait_state(viewmodel, "WaitClockActionState")

    # Set next action to clock action
    viewmodel.next_action = ViewModelAction.CLOCK_ACTION

    # Post an employee ID, shall move to clocking state
    scanner.add_result(TEST_EMPLOYEE_ID)
    wait_state(viewmodel, "ClockActionState")

    # Then shall move to ClockSuccessState
    wait_state(viewmodel, "ClockSuccessState")
    # Shall automatically move to consultation state
    wait_state(viewmodel, "ConsultationSuccessState")
    # And finally back to scanning state after the presentation duration
    wait_state(viewmodel, "WaitClockActionState", 21.0)

    # The next action has been reset
    assert viewmodel.next_action == ViewModelAction.DEFAULT_ACTION


def test_consultation(teambridge_viewmodel, monkeypatch):
    """
    Clock in the test employee.
    """
    # Unpack the fixture
    viewmodel, scanner = teambridge_viewmodel
    # Create the barcode mocking object
    scanner = BarcodeScannerMock(scanner, monkeypatch)

    # Move to scanning state
    scanner.set_scanning(True)
    wait_state(viewmodel, "WaitClockActionState")

    # Set next action to consultation
    viewmodel.next_action = ViewModelAction.CONSULTATION
    # Shall move to waiting for consultation action
    wait_state(viewmodel, "WaitConsultationActionState")

    # Post an employee ID, shall move to consultation action state
    scanner.add_result(TEST_EMPLOYEE_ID)
    wait_state(viewmodel, "ConsultationActionState")
    # Shall automatically move to consultation success state
    wait_state(viewmodel, "ConsultationSuccessState")

    # Shall return in consultation state on reset to consultation signal
    viewmodel.next_action = ViewModelAction.RESET_TO_CONSULTATION
    wait_state(viewmodel, "WaitConsultationActionState")

    # Shall be able to move back to wait for clock action state
    viewmodel.next_action = ViewModelAction.CLOCK_ACTION
    wait_state(viewmodel, "WaitClockActionState")


def test_error(teambridge_viewmodel, monkeypatch):
    """
    Enter the error state and reset to scanning state.
    """
    # Unpack the fixture
    viewmodel, scanner = teambridge_viewmodel
    # Create the barcode mocking object
    scanner = BarcodeScannerMock(scanner, monkeypatch)

    # Move to scanning state
    scanner.set_scanning(True)
    wait_state(viewmodel, "WaitClockActionState")

    # Set next action to clock action
    viewmodel.next_action = ViewModelAction.CLOCK_ACTION

    # Post a wrong employee ID, shall move to clocking state
    scanner.add_result("thisiswrongid8752145")
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
