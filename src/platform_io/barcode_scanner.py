#!/usr/bin/env python3
"""
File: barcode_scanner.py
Author: Bastian Cerf
Date: 02/03/2025
Description:
    Open a camera device mounted on the system and analyze the frames to find barcodes.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import logging
import cv2
import time
import threading
import uuid
import re
from typing import Optional, Any

# Third-party
import pyzbar.pyzbar
import numpy as np


logger = logging.getLogger(__name__)


class BarcodeScanner:
    """
    Open a camera device mounted on the system and analyze the frames to find barcodes.
    Barcodes values are decoded as strings and a regular expression can be used to match specific code
    formats and extract an information, such as an ID.
    Optionally, a timeout can be specified to prevent a barcode to be scanned in loop.
    When the scanner is opened, a background thread is started and will handle the scanning process at the
    specified rate. This process can be paused and resumed using provided methods.
    """

    def __init__(self):
        """
        Create a barcode scanner.
        """
        # Define a unique session ID to identify different scanners
        self._session_name = f"Session-{str(uuid.uuid1()).split('-')[0]}"

        # Flag to control the scanning thread lifecycle
        self._running = threading.Event()
        # Flag to pause/resume (not finishing) the scanning thread
        self._resume = threading.Event()
        # Flag set by the scanning thread to know if it is running
        self._scanning = threading.Event()
        # Pending codes set. These codes are waiting to be read
        self._pending_codes: set[str] = set()
        # Dictionary of codes that have been read and cannot be read again
        # before a timeout has expired
        self._cooldown_codes: dict[str, float] = {}
        # Create a lock for concurrent access to above collections
        self._lock = threading.Lock()
        self._thread = None

    def configure(
        self,
        regex: Optional[str] = None,
        extract_group: Optional[int] = None,
        timeout: float = 0.0,
        debug_mode: bool = False,
    ):
        """
        Configure the barcode scanner.

        The debug mode can be enabled to open a window that shows the
        camera stream in real time, which is helpful to understand the
        camera environment.

        Args:
            regex (str): Optional regular expression the scanned barcode
                must match with.
            extract_group (int): When a regular expression is provided,
                specify the group to extract the scanned ID from. If not
                specified, the entire scan is used as ID.
            timeout (float): Delay in seconds between two scans of the same
                barcode ID.
            debug_mode (bool): Enable the debug mode.
        """
        self._regex = regex
        self._extract_group = extract_group
        self._timeout = timeout
        self._debug_mode = debug_mode

        logger.info(f"Configured barcode scanner '{self._session_name}'.")

    def open(
        self, cam_idx: int = 0, scan_rate: float = 1.0, symbols: Any = None
    ) -> None:
        """
        Open a camera device and start the scanning process. A camera
        mounted on the system is identified by its index. The scan rate
        can be specified to tune the CPU usage / reactivity ratio. A list
        of symbols to be identified on scanned frames can also be specified.
        If left empty, all kinds of barcodes are decoded.

        Args:
            cam_idx (int): Camera index on the system.
            scan_rate (float): Scan rate [Hz].
            symbols (iter(ZBarSymbol)): The pyzbar symbol types to decode
                or `None` to decode all.

        Raises:
            RuntimeError: The scanner is already running.
        """
        with self._lock:
            if self._running.is_set():
                raise RuntimeError(
                    f"The barcode scanner '{self._session_name}' is already running."
                )

            self._running.set()  # General running
            self._resume.set()  # Set playing

        self._cam_idx = cam_idx
        self._symbols = symbols

        # Calculate the period between frames from the provided scan rate
        # Minimal period of 1 second
        self._frame_period_sec = 1.0 / max(1, scan_rate)

        # Create and start the scanning process
        self._thread = threading.Thread(
            target=self.__run, daemon=False, name=f"Scanner-{self._session_name}"
        )
        self._thread.start()

    def __run(self):
        """
        Scanning thread running function.
        """
        # Initial state:
        # _running: True
        # _scanning: False
        # Open the device
        device = cv2.VideoCapture(self._cam_idx)
        if device.isOpened():
            logger.info(
                f"Scanner '{self._session_name}' opened capture device "
                f"[id={self._cam_idx}, backend={device.getBackendName()}]."
            )
            self._scanning.set()

        else:
            logger.error(
                f"Scanner '{self._session_name}' failed to open capture device "
                f"[id={self._cam_idx}]."
            )
            self._running.clear()  # Do not enter the scanning loop

        while self._running.is_set():
            # The resume flag can pause the scanning thread. When paused, the
            # scanning flag is cleared to inform scanner user.
            self._scanning.clear()
            self._resume.wait()
            self._scanning.set()

            frame_ts = time.time()

            ret, frame = device.read()
            if not ret:
                # The device might be unavailable (disconnected for example)
                logger.error(
                    f"Scanner '{self._session_name}' failed to read frame from "
                    f"device [id={self._cam_idx}, opened={device.isOpened()}]."
                )

                # A frame reading error leads to the scanner to shutdown
                self._running.clear()
                break

            # Decode the frame as a list of barcodes. Each scanned barcode
            # has a data that can be decoded in utf-8 to get a string.
            barcodes: list[Any] = pyzbar.pyzbar.decode(frame, symbols=self._symbols)  # type: ignore library is not typed
            for code in barcodes:
                raw_data = code.data
                if raw_data is None:
                    continue

                try:
                    raw_value = raw_data.decode("utf-8")
                    value = raw_value
                except UnicodeDecodeError:
                    continue

                # A value has been scanned and decoded as a string
                # Check if the decoded value matches the optional regex
                if self._regex:
                    matching = re.match(self._regex, value)

                    if matching:
                        if self._extract_group:
                            value = matching.group(self._extract_group)
                    else:
                        # The value doesn't match the specified regex
                        value = None

                if value is not None:
                    # At this point, the value is a valid identifier
                    with self._lock:
                        # Flush all values that have timed out in the dictionary
                        now = time.time()
                        self._cooldown_codes = {
                            # Keep values that haven't expired
                            k: v
                            for k, v in self._cooldown_codes.items()
                            if v >= now
                        }

                        # If the value is still pending in the dictionary,
                        # ignore it. Otherwise the value is eligible to be
                        # added in the pending list.
                        if value not in self._cooldown_codes:
                            self._pending_codes.add(value)

                if self._debug_mode:
                    # Draw a rectangle around the scanned barcodes
                    # Red: not matching regular expression
                    # Blue: pending code
                    # Green: cooldown code
                    color = (0, 0, 255)
                    timeout = None

                    with self._lock:
                        if value is not None and value in self._pending_codes:
                            color = (255, 0, 0)
                        elif value is not None and (value in self._cooldown_codes):
                            color = (0, 255, 0)
                            timeout = self._cooldown_codes[value] - time.time()

                    # Draw the colored border rectangle around the barcode
                    pts = code.polygon
                    pts = [(pt.x, pt.y) for pt in pts]
                    cv2.polylines(
                        frame,
                        [np.array(pts, dtype=np.int32)],
                        isClosed=True,
                        color=color,
                        thickness=2,
                    )

                    # Display the decoded data on the frame
                    (x, y, _, _) = code.rect
                    cv2.putText(
                        frame,
                        raw_value,
                        (x, y - 10),
                        cv2.FONT_HERSHEY_COMPLEX,
                        0.5,
                        color,
                        1,
                    )

                    # Display identified value
                    if value:
                        cv2.putText(
                            frame,
                            f"id={value}",
                            (x, y - 25),
                            cv2.FONT_HERSHEY_COMPLEX,
                            0.5,
                            color,
                            1,
                        )

                    # Display timeout
                    if timeout:
                        cv2.putText(
                            frame,
                            f"{timeout:.1f}s",
                            (x, y - 40),
                            cv2.FONT_HERSHEY_COMPLEX,
                            0.5,
                            color,
                            1,
                        )

            if self._debug_mode:
                cv2.imshow(f"Debug {self._session_name}", frame)

            delta_ts = time.time() - frame_ts
            # Sleep required time to reach the specified scan rate.
            # Minimal sleep duration is 1ms, otherwise the waitKeys() function
            # is blocking.
            sleep_ms = max(1, int((self._frame_period_sec - delta_ts) * 1000.0))
            cv2.waitKey(sleep_ms)

        # Scanning process end
        device.release()
        self._scanning.clear()

        logger.info(f"Scanner '{self._session_name}' finished session.")

    def is_scanning(self) -> bool:
        """
        Returns:
            bool: `True` if scanning, False if not
        """
        return self._scanning.is_set()

    def available(self) -> bool:
        """
        Check if codes have been scanned. If this function returns True,
        `read_next()` can be called to get the next decoded value.

        Returns:
            bool: `True` if at least one code is available.
        """
        with self._lock:
            return bool(self._pending_codes)

    def read_next(self) -> str:
        """
        Read the next scanned code. The code matches the configured
        regular expression and if an `extract_group` has been specified
        only the extracted group will be returned from the matching
        expression.

        When a code is read with this method, it is added to the cooldown
        queue and cannot be scanned again before the specified timeout
        delay.

        Returns:
            str: Scanned code.

        Raises:
            KeyError: No code is available, use `available()` to avoid
                raising this error.
        """
        with self._lock:
            value = self._pending_codes.pop()
            self._cooldown_codes[value] = time.time() + self._timeout

        return value

    def clear(self) -> None:
        """
        Clear the pending codes and reset the timeouts.
        """
        with self._lock:
            self._pending_codes.clear()
            self._cooldown_codes.clear()

    def pause(self) -> None:
        """
        Pause the scanning process.
        """
        self._resume.clear()

    def resume(self) -> None:
        """
        Resume the scanning process.
        """
        self._resume.set()

    def close(self, join: bool = False):
        """
        Close the barcode scanner.

        Args:
            join: `True` to wait for the scanning thread to finish.
        """
        self._running.clear()
        self._resume.set()  # The thread may be waiting

        if join and self._thread:
            self._thread.join()
