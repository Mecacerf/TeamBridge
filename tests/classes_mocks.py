#!/usr/bin/env python3

# Standard libraries
import logging
from pytest import MonkeyPatch
from typing import Any

# Internal libraries
from tests.test_constants import *
from platform_io.barcode_scanner import BarcodeScanner

logger = logging.getLogger(__name__)

########################################################################
#                           Barcode scanner mock                       #
########################################################################


class BarcodeScannerMock:
    """
    Mock implementation of a barcode scanner interface.

    This class replaces the methods of a given `BarcodeScanner` instance
    with mocked behaviors using pytest's `monkeypatch`. It allows other
    modules to simulate and control scanner behavior for testing purposes.
    """

    def __init__(self, scanner: BarcodeScanner, monkeypatch: MonkeyPatch):
        """
        Replace the methods of the provided `BarcodeScanner` instance
        with mock implementations.

        Args:
            scanner (BarcodeScanner): The scanner instance whose methods
                will be mocked.
            monkeypatch (MonkeyPatch): A pytest `monkeypatch` object
                used to apply the mocks.
        """
        # No-op functions
        monkeypatch.setattr(scanner, "configure", self.__configure)
        monkeypatch.setattr(scanner, "open", self.__open)
        monkeypatch.setattr(scanner, "clear", self.__clear)
        monkeypatch.setattr(scanner, "close", self.__close)
        monkeypatch.setattr(scanner, "pause", self.__pause)
        monkeypatch.setattr(scanner, "resume", self.__resume)

        # Mock scanning state
        self._scanning = False
        monkeypatch.setattr(scanner, "is_scanning", self.__is_scanning)

        # Mock result queue
        self._results: list[str] = []
        monkeypatch.setattr(scanner, "available", self.__available)
        monkeypatch.setattr(scanner, "read_next", self.__read_next)

    def __configure(self, *args: tuple[Any], **kwargs: dict[Any, Any]):
        """
        Stub method that does nothing (used to replace non-essential
        scanner methods).
        """
        logger.debug(f"[{self.__class__.__name__}] configure() stub call.")

    def __open(self, *args: tuple[Any], **kwargs: dict[Any, Any]):
        """
        Stub method that does nothing (used to replace non-essential
        scanner methods).
        """
        logger.debug(f"[{self.__class__.__name__}] open() stub call.")

    def __clear(self, *args: tuple[Any], **kwargs: dict[Any, Any]):
        """
        Stub method that does nothing (used to replace non-essential
        scanner methods).
        """
        logger.debug(f"[{self.__class__.__name__}] clear() stub call.")

    def __close(self, *args: tuple[Any], **kwargs: dict[Any, Any]):
        """
        Stub method that does nothing (used to replace non-essential
        scanner methods).
        """
        logger.debug(f"[{self.__class__.__name__}] close() stub call.")

    def __pause(self, *args: tuple[Any], **kwargs: dict[Any, Any]):
        """
        Stub method that does nothing (used to replace non-essential
        scanner methods).
        """
        logger.debug(f"[{self.__class__.__name__}] pause() stub call.")

    def __resume(self, *args: tuple[Any], **kwargs: dict[Any, Any]):
        """
        Stub method that does nothing (used to replace non-essential
        scanner methods).
        """
        logger.debug(f"[{self.__class__.__name__}] resume() stub call.")

    def __is_scanning(self) -> bool:
        """Return the current mocked scanning state."""
        return self._scanning

    def __available(self) -> bool:
        """Return True if there are mock scan results available to read."""
        return len(self._results) > 0

    def __read_next(self) -> str:
        """Return and remove the next mock scan result from the queue."""
        return self._results.pop()

    def set_scanning(self, value: bool):
        """
        Set the scanning state of the mocked scanner.

        Args:
            value (bool): True to simulate scanning in progress, False
                otherwise.
        """
        self._scanning = value

    def add_result(self, result: str):
        """
        Add a mock scan result to the queue.

        Args:
            result (str): A string representing a barcode value to simulate.
        """
        self._results.append(result)
