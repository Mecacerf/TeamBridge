#!/usr/bin/env python3
"""
File: sleep_management.py
Author: Bastian Cerf
Date: 09/05/2025
Description: 
    This module allows to enable / disable the program sleep mode.
    It is used to prevent the computer from going to sleep while the program is running.
    Currently, it only works on Windows.
    
Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

import logging

# Screen brightness control library
import screen_brightness_control as sbc

# Import thread pool executor to asynchronously set the screen brightness.
from concurrent.futures import ThreadPoolExecutor

__all__ = ['SleepManager']

LOGGER = logging.getLogger(__name__)

# Windows constants
ES_CONTINUOUS       = 0x80000000 # Tells the system to keep applying the setting.
ES_SYSTEM_REQUIRED  = 0x00000001 # Prevents sleep.
ES_DISPLAY_REQUIRED = 0x00000002 # Keeps the screen from turning off.

# Display ID to control
DISPLAY = 0

class SleepManager:
    """
    The class manages different computer parameters such as sleep mode and screen
    brightness. It basically disable the OS sleep mode that would prevent the user
    from interacting with the application and provides a soft sleep mode, that 
    typically involves reducing the screen brightness.
    """

    def __init__(self, 
                 low_brightness_lvl: int, 
                 high_brightness_lvl: int = None):
        """
        Initialize the sleep manager.
        If the high brightness level is not set, it will use the current value.

        Args:
            low_brightness_lvl: `int` brightness level of the screen in soft sleep mode [0-100]
            high_brightness_lvl: `int` brightness level of the screen in working mode [0-100]
        """
        self._enabled = False
        self._soft_sleep = False
        # Clamp the values.
        self._low_brightness_lvl = min(100, max(0, low_brightness_lvl))
        # Check if high brightness has been provided.
        if high_brightness_lvl:
            self._high_brightness_lvl = min(100, max(0, high_brightness_lvl))
        else:
            try:
                self._high_brightness_lvl = sbc.get_brightness(display=DISPLAY)[0]
            except sbc.ScreenBrightnessError:
                LOGGER.error("Unable to retrieve current screen brightness.", exc_info=True)
                # Use a default value.
                self._high_brightness_lvl = 100

        # Create a simple thread pool executor to execute the set brightness task.
        self._executor = ThreadPoolExecutor(max_workers=1)

        # Log the sleep manager initialization.
        LOGGER.info(("Initialized the sleep manager "
                    f"[low_brightness={self._low_brightness_lvl}, high_brightness={self._high_brightness_lvl}]"))

    def enable(self):
        """
        Enable the manager operations.
        """
        # Do not enable twice.
        if self._enabled:
            return

        try:
            # Call the thread execution state of win32 by using ctypes.
            import ctypes
            FLAGS = (ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
            ctypes.windll.kernel32.SetThreadExecutionState(FLAGS)
        except:
            LOGGER.error("Unable to disable Windows sleep mode.")
        finally:
            # Always set the enabled flag.
            self._enabled = True

    def disable(self):
        """
        Disable the manager operations.
        """
        # Do not disable twice.
        if not self._enabled:
            return
        
        try:    
            # Call the thread execution state of win32 by using ctypes.
            import ctypes
            # Remove system and display flags.
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        except:
            LOGGER.error("Unable to reactivate Windows sleep mode.")
        finally:
            # Exit soft sleep mode if enabled.
            self.soft_sleep = False
            # Always reset the enabled flag.
            self._enabled = False

    @property
    def soft_sleep(self):
        """
        Get the soft sleep status.

        Returns:
            bool: soft sleep mode status
        """
        return self._soft_sleep
    
    @soft_sleep.setter
    def soft_sleep(self, status: bool):
        """
        Change the soft sleep mode.

        Args:
            status: `bool` soft sleep mode
        """
        # The manager must be enabled and the value has changed.
        if not self._enabled or self._soft_sleep == status:
            return
        # Change status
        self._soft_sleep = status

        # Apply change
        if self._soft_sleep:
            # Set the brightness level to low value.
            self._executor.submit(self.__set_brightness_async, self._low_brightness_lvl)
            LOGGER.info("Entered sleep mode.")
        else:
            # Set the brightness level to high value.
            self._executor.submit(self.__set_brightness_async, self._high_brightness_lvl)
            LOGGER.info("Exited sleep mode.")

    def __set_brightness_async(self, brightness: int):
        # Asynchronously set the screen brightness.
        try:
            # Force to True allows to turn off the backlight on Linux.
            sbc.set_brightness(brightness, display=DISPLAY, force=True)
        except sbc.ScreenBrightnessError:
            LOGGER.error("Unable to change the screen brightness.", exc_info=True)

    def __enter__(self):
        # Automatic enable using a context manager.
        self.enable()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Automatic disable using a context manager.
        self.disable()
