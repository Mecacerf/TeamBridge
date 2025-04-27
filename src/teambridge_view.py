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

# Import Kivy libraries
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.progressbar import ProgressBar
from kivy.animation import Animation
from kivy.properties import StringProperty, ObjectProperty, NumericProperty
from kivy.clock import Clock

# Default window size
from kivy.core.window import Window
Window.size = (1280/1.4, 720/1.4)

# Register text fonts
from kivy.core.text import LabelBase
LabelBase.register(name="InterRegular", fn_regular="assets/Inter_28pt-Regular.ttf")
LabelBase.register(name="InterMedium", fn_regular="assets/Inter_28pt-Medium.ttf")

# Other imports
import time
from enum import Enum
from view_theme import *

# Run method call interval in seconds
RUN_INTERVAL = float(1.0 / 30.0)

class TeamBridgeApp(App):
    """
    Teambridge application class. The application starts the graphic library and create the view.
    """

    # The kv file is located in the assets/ folder
    kv_directory = "assets/"
    
    # Set application theme to light by default
    # Set the rebind flag to trigger the observers when the theme changes 
    theme = ObjectProperty(LIGHT_THEME, rebind=True)

    def __init__(self, viewmodel: TeamBridgeViewModel, theme: ViewTheme=None):
        """
        Initialize the application.

        Args:
            viewmodel: `TeamBridgeViewModel` viewmodel instance
            theme: `ViewTheme` optional theme to customize the UI
        """
        super().__init__()
        # Save viewmodel
        self._viewmodel = viewmodel
        # Set theme if provided
        if theme:
            self.theme = theme

    def get_theme(self) -> ViewTheme:
        """
        Get current application theme.

        Returns:
            ViewTheme: theme in use
        """
        return self.theme
    
    def set_theme(self, theme: ViewTheme):
        """
        Change application theme.

        Args:
            theme: `ViewTheme` new theme to use
        """
        self.theme = theme

    def _run_viewmodel(self, _):
        """
        Run the viewmodel.
        """
        self._viewmodel.run()

    def build(self):
        # Schedule the view model run method calls
        Clock.schedule_interval(self._run_viewmodel, RUN_INTERVAL)
        # Create the main screen
        return MainScreen(self._viewmodel)

    def on_stop(self):
        # Close the viewmodel
        self._viewmodel.close()
        LOGGER.info("Application closed, goodbye.")

    def __repr__(self):
        return self.__class__.__name__

class MainScreen(BoxLayout):
    """
    Application main screen root object.
    """

    # Clock date and time
    clock_time = StringProperty("")
    clock_date = StringProperty("")
    # Viewmodel texts
    instruction_text = StringProperty("")
    instruction_text_color = ObjectProperty((1, 1, 1, 1))
    greetings_text = StringProperty("")
    information_text = StringProperty("")
    # Toggle buttons
    consultation_button = ObjectProperty(None)
    clock_button = ObjectProperty(None)
    # Progress bar
    progress_bar = ObjectProperty(None)
    
    def __init__(self, viewmodel: TeamBridgeViewModel):
        super().__init__()
        # Save viewmodel
        self._viewmodel = viewmodel
        # Save running application
        self._app = App.get_running_app()

        # Schedule the clock time update
        Clock.schedule_interval(self._update_clock_time, 1.0) 

        # Observe the viewmodel texts
        self._viewmodel.instruction_text.observe(self._update_instruction_text)
        self._viewmodel.greetings_text.observe(self._update_greetings_text)
        self._viewmodel.information_text.observe(self._update_information_text)
        # Observe the viewmodel next action
        self._viewmodel.get_next_action().observe(self._update_action)
        # Observe the viewmodel state
        self._viewmodel.current_state.observe(self._update_state)

    def _update_clock_time(self, _):
        """
        Update the clock time and date.
        """
        self.clock_time = time.strftime("%H:%M")
        self.clock_date = time.strftime("%d %B %Y")

    def _update_instruction_text(self, txt: str):
        if txt is not None:
            self.instruction_text = txt

    def _update_greetings_text(self, txt: str):
        if txt is not None:
            self.greetings_text = txt

    def _update_information_text(self, txt: str):
        if txt is not None:
            self.information_text = txt

    def _update_action(self, *kargs):
        # Get next action
        action = self._viewmodel.next_action
        # Set button states
        self.consultation_button.toggle_state = (action == ViewModelAction.CONSULTATION)
        self.clock_button.toggle_state = (action == ViewModelAction.CLOCK_ACTION)

    def _update_state(self, state):
        """
        Update the state of UI elements depending on viewmodel state.
        """
        # Set the states the buttons are enabled
        enabled_states = ['ScanningState', 'ConsultationSuccessState']
        self.consultation_button.enabled = (state in enabled_states)
        # Clock button is enabled in error state for acknowledgment
        enabled_states.append('ErrorState')
        self.clock_button.enabled = (state in enabled_states)
        
        # Set instruction text color
        instruction_colors = {
            'InitialState': self._app.theme.error_color,
            'ClockSuccessState': self._app.theme.success_color,
            'ConsultationSuccessState': self._app.theme.success_color,
            'ErrorState': self._app.theme.error_color
        }
        # If the color is defined in the dict, use it. Otherwise use the default primary one.
        if state in instruction_colors:
            self.instruction_text_color = instruction_colors[state]
        else:
            self.instruction_text_color = self._app.theme.text_primary_color

        # Set the progress bar loading state
        loading_states = ['ClockActionState', 'ClockSuccessState', 'ConsultationActionState']
        self.progress_bar.loading = (state in loading_states)

        # Also update action
        self._update_action()

    def on_clock_action_press(self):
        """
        Called when the clock action button is pressed.
        """
        state = self._viewmodel.current_state.value
        # Choose action based on viewmodel state
        if state == 'ScanningState':
            # Set the next action to clock action
            self._viewmodel.next_action = ViewModelAction.CLOCK_ACTION
        elif state == 'ConsultationSuccessState':
            # Reset the viewmodel to go back in scanning state clock action
            self._viewmodel.next_action = ViewModelAction.RESET_TO_CLOCK_ACTION
        elif state == 'ErrorState':
            # Acknowledge the error
            self._viewmodel.next_action = ViewModelAction.RESET_ACTION
        else:
            raise RuntimeError("The clock button shouldn't be enabled.")

    def on_consultation_press(self):
        """
        Called when the consultation button is pressed.
        """
        state = self._viewmodel.current_state.value
        # Choose action based on viewmodel state
        if state == 'ScanningState':
            # Set the next action to consultation action
            self._viewmodel.next_action = ViewModelAction.CONSULTATION
        elif state == 'ConsultationSuccessState':
            # Reset the viewmodel to go back in scanning state consultation action
            self._viewmodel.next_action = ViewModelAction.RESET_TO_CONSULTATION_ACTION
        else:
            raise RuntimeError("The consultation button shouldn't be enabled.")

    def on_attendance_press(self):
        """
        Called when the reset button is pressed.
        """
        # TODO: test
        self._app.set_theme(DARK_THEME if self._app.get_theme() == LIGHT_THEME else LIGHT_THEME)

class IconButton(ButtonBehavior, RelativeLayout):
    """
    Simple material design like icon button.
    """

    # Button properties
    source = StringProperty(None)
    background_color = ObjectProperty((1, 1, 1, 1))
    actual_side = NumericProperty(0)
    current_side = NumericProperty(0)

    # Button states enumeration
    class ButtonState(Enum):
        # The button is disabled
        DISABLED = 0
        # The button is released
        RELEASED = 1
        # The button is pressed
        PRESSED = 2

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Store application instance
        self._app = App.get_running_app()

        # Define private parameters
        self._anim = None
        self._state = IconButton.ButtonState.DISABLED

        # Update the button style on theme change
        self._app.bind(theme=self.on_style_update)
        # Initial style update
        self.on_style_update()
    
    def on_style_update(self, *kargs):
        """
        Update the button style after a state change.
        """
        # Stop current animation (if still running)
        if self._anim:
            self._anim.stop(self)
        # Define the target color and size depending on current state
        if self._state == IconButton.ButtonState.DISABLED:
            color = self._app.theme.disabled_color
            side = self.actual_side * 0.98
            duration = 0.1
        elif self._state == IconButton.ButtonState.PRESSED:
            color = self._app.theme.primary_color
            side = self.actual_side * 0.98
            duration = 0.1
        elif self._state == IconButton.ButtonState.RELEASED:
            color = self._app.theme.secondary_color
            side = self.actual_side
            duration = 0.2
        # Start animation
        self._anim = Animation(background_color=color, duration=duration)
        self._anim &= Animation(current_side=side, duration=duration)
        self._anim.start(self)

    def on_parent(self, _, parent):
        """
        Called when the parent is defined.
        """
        # Sanity check
        if parent:
            # Bind the update size method to react when available place changes
            parent.bind(size=self._update_side)
            # Initial update of the size
            self._update_side()

    def _update_side(self, *args):
        """
        Called when the widget size must be evaluated.
        """
        # Sanity check the parent widget
        if self.parent:
            # Set the square side to the minimal available size in width and height
            self.actual_side = min(self.parent.size)
            # Update the style to automatically adapt the widget size
            self.on_style_update()

    @property
    def pressed(self) -> bool:
        """
        Returns:
            bool: True if button pressed, False otherwise
        """
        return (self._state == IconButton.ButtonState.PRESSED)

    @pressed.setter
    def pressed(self, value: bool):
        """
        Args:
            pressed: `bool` True for button press, False for button released
        """
        # The state cannot change if button is disabled
        if self._state == IconButton.ButtonState.DISABLED:
            return
        
        # Set state accordingly
        self._state = IconButton.ButtonState.PRESSED if value else IconButton.ButtonState.RELEASED
        # Update button style
        self.on_style_update()

    @property
    def enabled(self) -> bool:
        """
        Returns:
            bool: True if enabled, False if disabled
        """
        return (self._state != IconButton.ButtonState.DISABLED)
    
    @enabled.setter
    def enabled(self, value: bool):
        """
        Args:
            value: `bool` enabled state
        """
        # Set state accordingly
        if not value:
            # Set disabled
            self._state = IconButton.ButtonState.DISABLED
        elif self._state == IconButton.ButtonState.DISABLED:
            # Set enabled, initially released
            self._state = IconButton.ButtonState.RELEASED
        # Update button style
        self.on_style_update()

    def on_press(self):
        # Set in pressed state
        self.pressed = True

    def on_release(self):
        # Set in released state
        self.pressed = False

class ToggleIconButton(IconButton):
    """
    Icon button that overrides the default pressed/released behavior
    to show a boolean state.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Define toggle attribute
        self._toggle_state = False

    @property
    def toggle_state(self) -> bool:
        """
        Returns:
            bool: current button state
        """
        return self._toggle_state
    
    @toggle_state.setter
    def toggle_state(self, value: bool):
        """
        Args:
            value: `bool` new button state
        """
        self._toggle_state = value
        # Toggled button is pressed
        self.pressed = value

    @IconButton.enabled.setter
    def enabled(self, value: bool):
        """
        Override default enabled setter to automatically apply the 
        toggled state when enabled.
        """
        # Call the super setter
        super(ToggleIconButton, self.__class__).enabled.fset(self, value)
        # Toggled button is pressed
        self.pressed = value

    def on_press(self):
        # Delete default behavior
        pass

    def on_release(self):
        # Delete default behavior
        pass

class LinearProgressBar(ProgressBar):
    """
    Linear progress bar (does not define a progress, just show whether it
    is loading or not).
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set max value
        self.max = 1000
        # Set loading flag
        self._loading = False
        # Declare animation
        self._anim = None

    @property
    def loading(self) -> bool:
        """
        Returns:
            bool: loading flag
        """
        return self._loading
    
    @loading.setter
    def loading(self, value: bool):
        """
        Args:
            value: `bool` loading flag
        """
        # Do not start animation if already started
        if value and self.loading:
            return
        # Update flag
        self._loading = value
        # Start animation if loading is set
        if self._loading:
            self._start_anim()

    def _start_anim(self, *kargs):
        """
        Start loading animation. Called continuously while loading flag is set.
        """
        # Reset value
        self.value = 0
        # Reschedule animation if still loading
        if self._loading:
            self._anim = Animation(value=self.max, duration=2.0, transition='linear')
            self._anim.bind(on_complete=self._start_anim)
            self._anim.start(self)
