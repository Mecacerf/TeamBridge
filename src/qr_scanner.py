#!/usr/bin/env python3
"""
File: qr_scanner.py
Author: Bastian Cerf
Date: 02/03/2025
Description: 
    Open a camera and start scanning QR codes.    

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

import cv2
import pyzbar.pyzbar
import time
import threading
import numpy as np
import logging

# Get module logger
LOGGER = logging.getLogger(__name__)

class QRScanner:
    """
    Class for accessing a webcam and scan QR codes.
    """

    def __init__(self):
        """
        Initialize internal state.
        """
        # Use a running flag to know when the internal thread is running or not 
        self._running = False
        # Use a scanning flag to know when the internal thread is supposed to work or not
        self._scanning = threading.Event()
        # Create a lock for multithreading access
        self._lock = threading.Lock()
        # Create the internal QR values set
        self._qr_values = set()

    def open(self, cam_idx: int=0, scan_rate: float=1.0, daemon: bool=False, debug_window: bool=False):
        """
        Open the webcam and start scanning QR codes.

        Parameters:
            cam_idx: webcam index, typically 0
            scan_rate: QR code scan rate in hertz
            daemon: if True, the internal thread will automatically shut down on program exit
            debug_window: True to show a debugging window and discover what the camera is seeing 
        """
        with self._lock:
            # Check not already running
            if self._running:
                raise RuntimeError("The process is already running.")
            # Set the running flag
            self._running = True

        # Save parameters
        self._cam_idx = cam_idx
        self._debug = debug_window
        # Save the scanning rate as the period between frames
        self._frame_period_sec = 1.0 / scan_rate
        # Create internal thread
        self._thread = threading.Thread(target=self.__run, daemon=daemon, name="QR-Scanner-Thread")
        # Start the thread
        self._thread.start()

    def __run(self):
        """
        Internal thread running function.
        """
        # Open the device
        device = cv2.VideoCapture(self._cam_idx)
        # Check device was successfully opened
        if device.isOpened():
            # Show a message
            LOGGER.info(f"Opened video capture device '{device.getBackendName()}'")
        else:
            # Cannot open device, abort scanning
            self._scanning.clear()
            LOGGER.error("Error opening video capture device.")

        # Set the scanning flag
        self._scanning.set()
        # Run while scanning flag is set
        while self._scanning.is_set():
            # Get current timestamp
            frame_ts = time.time()
            # Read a frame
            ret, frame = device.read()
            # Check returned frame is valid
            if not ret:
                # That means the device might be unavailable (disconnected for example)
                # Abort scanning
                self._scanning.clear()
            else:
                # The frame is valid and can be analyzed
                # Get QR codes
                qr_codes = pyzbar.pyzbar.decode(frame)
                # Iterate QR codes and decode them
                for qr in qr_codes:
                    # Get decoded value
                    qr_value = qr.data.decode("utf-8")
                    # Add the decoded value to the set 
                    # The set ensures uniqueness in case a QR code is decoded multiple times
                    with self._lock:
                        self._qr_values.add(qr_value)
                    # Check if debug mode is enabled
                    if self._debug:
                        # Draw a rectangle around the QR code
                        pts = qr.polygon
                        pts = [(pt.x, pt.y) for pt in pts]
                        cv2.polylines(frame, [np.array(pts, dtype=np.int32)], isClosed=True, color=(0, 255, 0), thickness=3)
                        # Display the decoded data on the frame
                        (x, y, _, _) = qr.rect
                        cv2.putText(frame, qr_value, (x, y - 10), cv2.FONT_HERSHEY_COMPLEX, 1.0, (100, 0, 0), 2)

                # If debug mode is enabled, show the debug window
                if self._debug:
                    cv2.imshow("QR Scanner Debug", frame)
                
            # Get frame analysis duration
            delta_ts = time.time() - frame_ts
            # Sleep required time to reach the specified scan rate
            # Minimal sleep duration is 1ms, otherwise the waitKeys() function will block
            sleep_ms = max(1, int((self._frame_period_sec - delta_ts) * 1000.0))
            cv2.waitKey(sleep_ms)
        
        # Free device
        device.release()
        # Scanner thread exits, release running flag
        with self._lock:
            self._running = False

    def close(self):
        """
        Close the webcam.
        """
        # Reset the scanning flag to exit the internal thread
        self._scanning.clear()

    def is_scanning(self) -> bool:
        """
        Returns:
            bool: True if scanning, False otherwise
        """
        return self._scanning.is_set()

    def available(self) -> bool:
        """
        Check if QR codes have been scanned. If this function returns True, get_next() can be called to
        get the decoded value.

        Returns:
            bool: True if available codes 
        """
        with self._lock:
            # Set evaluates as False if empty
            return bool(self._qr_values)

    def get_next(self) -> str | None:
        """
        Get the next QR value from the internal set.

        Returns:
            str: scanned code as a string or None if the set is empty
        """
        with self._lock:
            return self._qr_values.pop()
        
    def flush(self) -> None:
        """
        Flush the pending QR values.
        """
        with self._lock:
            self._qr_values.clear()
