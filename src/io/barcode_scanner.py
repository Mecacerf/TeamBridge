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

# Import logging and get the module logger
import logging
LOGGER = logging.getLogger(__name__)

import cv2
import pyzbar.pyzbar
import time
import threading
import numpy as np
import uuid
import re

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
        self._pending_codes = set()
        # Dictionary of codes that have been read and cannot be read again before a timeout has expired
        self._cooldown_codes: dict[str, float] = {}
        # Create a lock for concurrent access to above collections
        self._lock = threading.Lock()


    def configure(self, regex: str=None, extract_group=None, timeout: float=0.0, debug_mode: bool=False):
        """
        Configure the barcode scanner.

        The debug mode can be enabled to open a window that shows the camera stream, which is helpful
        to understand the camera environment.

        Args:
            regex: `str` optional regular expression to match the scanned barcodes.
            extract_group: `int` optionally specify the group to extract from the regular expression.
                If not specified, the whole barcode is returned.
            timeout: `float` delay in seconds before a matching barcode cannot be scanned again.
            debug_mode: `bool` enable the debug mode. 
        """
        # Save provided configuration
        self._regex = regex
        self._extract_group = extract_group
        self._timeout = timeout
        self._debug_mode = debug_mode

        # Log activity
        LOGGER.info(f"Configured barcode scanner '{self._session_name}'.")

    def open(self, cam_idx: int=0, scan_rate: float=1.0, symbols=None) -> None:
        """
        Open a camera device and start the scanning process. A camera mounted on the system is
        identified by its ID. The scan rate can be specified to tune the CPU usage / reactivity 
        ratio. A list of symbols to be identified on scanned frames can also be specified. If left
        empty, all kinds of barcodes are decoded.

        Args:
            cam_idx: `int` camera to use index
            scan_rate: `float` scan rate [Hz]
            symbols: `iter(ZBarSymbol)` the symbol types to decode or None to decode all
        Raises:
            RuntimeError: the scanner is already running
        """
        # Acquire the lock to guard the-check-and-set section
        with self._lock:
            # Check not already running
            if self._running.is_set():
                raise RuntimeError(f"The barcode scanner '{self._session_name}' is already running.")
            # Set running flag and resume flag
            self._running.set()
            self._resume.set()

        # Save camera id
        self._cam_idx = cam_idx
        # Set the scanning rate as the period between frames
        self._frame_period_sec = 1.0 / max(1, scan_rate)
        # Save symbols
        self._symbols = symbols
        # Create the scanning thread and start the process
        self._thread = threading.Thread(target=self.__run, daemon=False, name=f"Scanner-{self._session_name}")
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
        # Check device was successfully opened
        if device.isOpened():
            # Successfully opened device
            LOGGER.info(f"Scanner '{self._session_name}' opened capture device [id={self._cam_idx}, backend={device.getBackendName()}].")
            # Set the scanning flag 
            self._scanning.set()
        else:
            # Cannot open device
            LOGGER.error(f"Scanner '{self._session_name}' failed to open capture device [id={self._cam_idx}].")
            # Clear the running flag to prevent entering the scanning loop
            self._running.clear()

        # Run the scanning loop while the running flag is set
        while self._running.is_set():
            # Always wait for the resume flag to be set before continuing
            # Clear the scanning flag while waiting
            self._scanning.clear()
            self._resume.wait()
            # Set back the scanning flag
            self._scanning.set()
            # Get current timestamp
            frame_ts = time.time()
            # Read a frame
            ret, frame = device.read()
            # Check the returned frame status 
            if not ret:
                # That means the device might be unavailable (disconnected for example)
                LOGGER.error(f"Scanner '{self._session_name}' failed to read frame from device [id={self._cam_idx}, opened={device.isOpened()}].")
                # Abort scanning
                self._running.clear()
                break

            # The frame is valid and can be analyzed
            # Read barcodes
            barcodes = pyzbar.pyzbar.decode(frame, symbols=self._symbols)
            # Iterate barcodes and decode them
            for code in barcodes:
                # Get raw data and sanity check it
                raw_data = code.data
                if raw_data is None:
                    continue
                # Try to decode the raw data as a string
                try:
                    # Decoded raw string
                    decoded_value = raw_data.decode("utf-8")
                    # Output value
                    value = decoded_value
                except UnicodeDecodeError:
                    continue

                # Check if a regex is specified and if the value matches it
                if self._regex:
                    matching = re.match(self._regex, value)
                    # If a match is found, extract the group if one is provided
                    if matching:
                        if self._extract_group:
                            value = matching.group(self._extract_group)
                        # If no group is specified, keep the whole value
                    else:
                        # If not matching, nullify the value
                        value = None

                if value:
                    # Acquire the lock to safely access the dictionary and the set
                    with self._lock:
                        # Flush all values that have timed out in the dictionary
                        now = time.time()
                        self._cooldown_codes = {
                            # Keep values that haven't expired
                            k: v for k, v in self._cooldown_codes.items() if v >= now
                        }

                        # If the value is still pending in the dictionary, ignore it.
                        # Otherwise the value is eligible to be added in the pending list.
                        if not value in self._cooldown_codes:
                            self._pending_codes.add(value)

                # Check if debug mode is enabled
                if self._debug_mode:
                    # Draw a rectangle around the scanned barcode
                    # Red: not matching regular expression
                    # Blue: pending code
                    # Green: cooldown code
                    color = (0, 0, 255)
                    timeout = None
                    # Acquire the lock to read collections
                    with self._lock:
                        if value is not None and value in self._pending_codes:
                            color = (255, 0, 0)
                        elif value is not None and (value in self._cooldown_codes):
                            color = (0, 255, 0)
                            timeout = self._cooldown_codes[value] - time.time()

                    # Draw rectangle
                    pts = code.polygon
                    pts = [(pt.x, pt.y) for pt in pts]
                    cv2.polylines(frame, [np.array(pts, dtype=np.int32)], isClosed=True, color=color, thickness=2)
                    # Display the decoded data on the frame
                    (x, y, _, _) = code.rect
                    cv2.putText(frame, decoded_value, (x, y - 10), cv2.FONT_HERSHEY_COMPLEX, 0.5, color, 1)
                    # Display identified value
                    if value:
                        cv2.putText(frame, f"id={value}", (x, y - 25), cv2.FONT_HERSHEY_COMPLEX, 0.5, color, 1)
                    # Display timeout
                    if timeout:
                        cv2.putText(frame, f"{timeout:.1f}s", (x, y - 40), cv2.FONT_HERSHEY_COMPLEX, 0.5, color, 1)
                
            # Show window if in debug mode
            if self._debug_mode:
                cv2.imshow(f"Debug {self._session_name}", frame)

            # Get frame analysis duration
            delta_ts = time.time() - frame_ts
            # Sleep required time to reach the specified scan rate
            # Minimal sleep duration is 1ms, otherwise the waitKeys() function will block
            sleep_ms = max(1, int((self._frame_period_sec - delta_ts) * 1000.0))
            cv2.waitKey(sleep_ms)
        
        # Free device
        device.release()
        # Running is cleared at this point
        # Clear scanning flag to inform that the thread finished
        self._scanning.clear()
        # Log activity
        LOGGER.info(f"Scanner '{self._session_name}' finished session.")

    def is_scanning(self) -> bool:
        """
        Returns:
            bool: True if scanning, False if not
        """
        return self._scanning.is_set()

    def available(self) -> bool:
        """
        Check if codes have been scanned. If this function returns True, read_next() can be called to
        get the decoded value.

        Returns:
            bool: True if at least one code is available 
        """
        # Acquire lock to avoid collision with scanning thread
        with self._lock:
            # Set evaluates as False if empty
            return bool(self._pending_codes)

    def read_next(self) -> str:
        """
        Read the next scanned code. The code matches the configured regular expression and
        if an extract_group has been specified only the extracted group will be returned
        from the matching expression.

        After a code has been read, it cannot be scanned again within the timeout delay.

        Returns:
            str: scanned code that matches regular expression or only the specified group
        Raises:
            KeyError: no code is available, use available() to avoid raising this error
        """
        # Acquire lock to avoid collision with scanning thread
        with self._lock:
            value = self._pending_codes.pop()
            # Add the value in the cooldown dictionary to prevent scanning it again immediately
            self._cooldown_codes[value] = time.time() + self._timeout
        # Return the value
        return value
        
    def clear(self) -> None:
        """
        Clear the pending codes and reset the timeouts.
        """
        # Acquire lock to avoid collision with scanning thread
        with self._lock:
            self._pending_codes.clear()
            self._cooldown_codes.clear()

    def pause(self) -> None:
        """
        Pause the scanning process.
        """
        # Clear the resume flag
        self._resume.clear()

    def resume(self) -> None:
        """
        Resume the scanning process.
        """
        # Set the resume flag
        self._resume.set()

    def close(self, join: bool=False):
        """
        Close the barcode scanner.

        Args:
            join: True to wait for the background thread to finish before returning
        """
        # Clear the running flag to exit the scanning thread
        self._running.clear()
        # Ensure the thread is not waiting
        self._resume.set()
        # If join is set, wait for the background thread to finish
        if join and self._thread:
            # Join the background thread
            self._thread.join()
