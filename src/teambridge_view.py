#!/usr/bin/env python3
"""
File: time_tracker_view.py
Author: Bastian Cerf
Date: 02/03/2025
Description: 
    The view is responsible of displaying the view model state in an elegant manner.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Reduce visibility to public class
__all__ = ["TeamBridgeApp"]

# Logging system
import logging
LOGGER = logging.getLogger(__name__)

# Import application viewmodel
from teambridge_viewmodel import *

# Configure kivy settings
import os
os.environ["KIVY_LOG_MODE"] = 'MIXED'
os.environ["KIVY_NO_ARGS"] = '1'
if os.getenv("KIVY_FORCE_ANGLE_BACKEND") == "1":
    # Force to use the angle backend for device that doesn't 
    # support OpenGL directly.
    os.environ["KIVY_GL_BACKEND"] = 'angle_sdl2'

# Import kivy libraries
from kivy.app import App
from kivy.uix.widget import *
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock

# Run method call interval in seconds
RUN_INTERVAL = float(1.0 / 60.0)

class TeamBridgeApp(App):
    """
    Teambridge application class. The application starts the graphic library and create the view.
    """

    # The kv file is located in the assets/ folder
    kv_directory = "assets/"

    def __init__(self, viewmodel: TeamBridgeViewModel):
        """
        Initialize the application.

        Args:
            viewmodel: `TeamBridgeViewModel` viewmodel instance
        """
        super().__init__()
        # Save viewmodel
        self._viewmodel = viewmodel

    def build(self):
        # Create the view and schedule the run method calls
        view = TeamBridgeView(self._viewmodel)
        Clock.schedule_interval(view.run, RUN_INTERVAL)
        return view

    def on_stop(self):
        # Close the viewmodel
        self._viewmodel.close()
        LOGGER.info("Application closed, goodbye.")

    def __repr__(self):
        return self.__class__.__name__

class TeamBridgeView(BoxLayout):
    
    def __init__(self, viewmodel: TeamBridgeViewModel):
        super().__init__()
        # Save viewmodel
        self._viewmodel = viewmodel

    def run(self, dt):
        # Run the viewmodel
        self._viewmodel.run()

    def clock_action(self):
        self._viewmodel.next_action = ViewModelAction.CLOCK_ACTION
        LOGGER.info(f"Set {self._viewmodel.next_action.value}.")

    def consultation_action(self):
        self._viewmodel.next_action = ViewModelAction.CONSULTATION
        LOGGER.info(f"Set {self._viewmodel.next_action.value}.")

    def scan_action(self):
        self._viewmodel.next_action = ViewModelAction.RESET_ACTION
        LOGGER.info(f"Set {self._viewmodel.next_action.value}.")
