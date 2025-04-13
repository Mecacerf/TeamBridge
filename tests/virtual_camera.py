#!/usr/bin/env python3
"""
File: virtual_camera.py
Author: Bastian Cerf
Date: 12/04/2025
Description: 
    Open a virtual camera on the system and allow to play a video into it.
    This file uses the pyvirtualcam library and require:
    - OBS studio on Windows
    - v4l2loopback on Linux 

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

import pyvirtualcam
import threading
import cv2
import uuid
import qrcode

class VirtualCamPlayer:
    """
    Virtual camera player class. It opens a virtual camera and automatically plays the given
    video content in its own thread.
    This class is not thread safe.
    """

    def __init__(self):
        """
        """
        # Create feeding thread and related flags
        self._feeder = threading.Thread(target=self.__run, name="CameraFeeder")
        self._playing = threading.Event()
        # Camera initially None
        self._camera = None

    def open(self, width: int, height: int, fps: float, identify: bool=False) -> int:
        """
        """
        # Cannot open more than once
        if self._camera:
            raise RuntimeError("Camera is already open.")
        # Create the camera with given parameters
        self._camera = pyvirtualcam.Camera(width=width, height=height, fps=fps)
        # If the camera must be identified on the system, create an ID and a QR code
        if identify:
            self._init_id = str(uuid.uuid1())
            self._qr_code = qrcode.make(self._init_id)
            # Convert to numpy image and use as the video frame

        return 0
 
    def play(self, path: str):
        """
        """
        # Check not already running
        if self._playing.is_set():
            raise RuntimeError("Camera already playing.")
        # Open file
        self._file = cv2.VideoCapture(path)
        # File must be available
        if not self._file.isOpened():
            raise RuntimeError(f"Cannot open video file at {path}.")
        # Set playing flag and start the feeder thread
        self._playing.set()
        self._feeder.start()

    def pause(self):
        """
        """

    def resume(self):
        """
        """

    def has_finished(self):
        """
        """

    def close(self):
        """
        """
        self._camera.close()
        self._camera = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.close()
        return False

    def __run(self):
        """
        """
        while self._playing.is_set():
            # Read next video frame
            
