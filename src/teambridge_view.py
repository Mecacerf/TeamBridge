#!/usr/bin/env python3
"""
File: time_tracker_view.py
Author: Bastian Cerf
Date: 02/03/2025
Description: 
    This Kivy-based view displays dynamic text content provided by the ViewModel and
    interacts with it through the next action signal. It serves as the presentation
    layer, updating its interface based on ViewModel data and sending user-triggered 
    events back to the ViewModel to drive application logic.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Reduce visibility to public class
__all__ = ["TeamBridgeApp"]

# Configure kivy settings before importing it
import os
from os.path import join
os.environ["KIVY_LOG_MODE"] = 'MIXED'
os.environ["KIVY_NO_ARGS"] = '1'
if os.getenv("KIVY_FORCE_ANGLE_BACKEND") == "1":
    # Force to use the angle backend for device that doesn't 
    # support OpenGL directly.
    os.environ["KIVY_GL_BACKEND"] = 'angle_sdl2'

# Import Kivy libraries
from kivy.app import App
from kivy.core.window import Window
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.progressbar import ProgressBar
from kivy.animation import Animation
from kivy.properties import StringProperty, ObjectProperty, NumericProperty, DictProperty
from kivy.clock import Clock

# Get view module logger
import logging
LOGGER = logging.getLogger(__name__)

# Import application viewmodel
from teambridge_viewmodel import *

# Register text fonts
from kivy.core.text import LabelBase
LabelBase.register(name="InterRegular", fn_regular=join("assets", "Inter_28pt-Regular.ttf"))
LabelBase.register(name="InterMedium", fn_regular=join("assets", "Inter_28pt-Medium.ttf"))
# Register material design icons font
LabelBase.register(name="md-icons", fn_regular=join("assets", "md-icons/MaterialDesignIconsDesktop.ttf"))

# Import audio files
from kivy.core.audio import SoundLoader
SOUND_CLOCKED = SoundLoader.load(join("assets", "clocked.mp3"))
SOUND_SCANNED = SoundLoader.load(join("assets", "scanned.mp3"))
SOUND_ERROR   = SoundLoader.load(join("assets", "error.mp3"))

# Other imports
import time
from enum import Enum
from view_theme import *

# Try to set the locale to french
# TODO: texts and configurations in a specific file
import locale
SET_LOCALE = 'fr_FR.UTF-8'

# Import the sleep manager
from sleep_management import SleepManager

# Run method call interval in seconds
RUN_INTERVAL = float(1.0 / 30.0)

class TeamBridgeApp(App):
    """
    Teambridge application class. The application starts the graphic library and 
    create the main screen.
    """

    # The kv file is located in the assets/ folder
    kv_directory = "assets"
    
    # Set application theme to light by default
    # Set the rebind flag to trigger the observers when the theme changes 
    theme = ObjectProperty(LIGHT_THEME, rebind=True)

    def __init__(self, 
                 viewmodel: TeamBridgeViewModel, 
                 fullscreen=False, 
                 theme: ViewTheme=None,
                 sleep_manager: SleepManager=None,
                 sleep_timeout: float=60):
        """
        Initialize the application.

        Args:
            viewmodel: `TeamBridgeViewModel` viewmodel instance
            fullscreen: `bool` enable fullscreen mode
            theme: `ViewTheme` optional theme to customize the UI
            sleep_manager: `SleepManager` optional sleep manager to use
            sleep_timeout: `float` sleep timeout, a sleep manager must be provided
        """
        super().__init__()
        # Save parameters
        self._viewmodel = viewmodel
        self._sleep_manager = sleep_manager
        self._sleep_timeout = sleep_timeout

        # Create the sleep timer if a sleep manager is provided.
        if self._sleep_manager:
            # Enable the sleep manager.
            self._sleep_manager.enable()
            # Schedule the timer to call the timeout method after the given delay.
            self._sleep_timer = Clock.schedule_once(self._on_sleep_timeout, sleep_timeout)
            # Automatically call the activity method when the screen is touched.
            Window.bind(on_touch_down=self.on_screen_activity)
            LOGGER.info(f"The system will enter sleep mode after {sleep_timeout} seconds of inactivity.")
        else:
            LOGGER.info("The sleep mode is disabled.")

        # Set fullscreen mode
        Window.fullscreen = 'auto' if fullscreen else False
        if not fullscreen:
            Window.size = (1137, 640)

        # Set theme if provided
        if theme:
            self.theme = theme

        # Try to set the locale
        try:
            locale.setlocale(locale.LC_TIME, SET_LOCALE)
        except:
            LOGGER.warning(f"Unable to set the desired locale '{SET_LOCALE}'.")

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
        # Close the viewmodel.
        self._viewmodel.close()
        # Disable the sleep manager.
        if self._sleep_manager:
            self._sleep_manager.disable()
        LOGGER.info("Application closed, goodbye.")

    def on_screen_activity(self, *args):
        """
        To call when screen activity occurs. It will update the sleep
        timeout.
        """
        # Check that a sleep manager has been provided.
        if not self._sleep_manager:
            return # Nothing to do
        
        # Exit sleep mode.
        self._sleep_manager.soft_sleep = False
        # Reschedule the sleep timeout.
        self._sleep_timer.cancel()
        self._sleep_timer = Clock.schedule_once(self._on_sleep_timeout, self._sleep_timeout)

    def _on_sleep_timeout(self, *args):
        # Automatically called when the sleep timer finishes.
        # If this method is called, that means a sleep manager exists.
        self._sleep_manager.soft_sleep = True

    def __repr__(self):
        return self.__class__.__name__

class MainScreen(FloatLayout):
    """
    Application main screen.
    """

    ## Properties used by the kv file
    # Clock date and time
    clock_time = StringProperty("")
    clock_date = StringProperty("")
    # Main title and subtitle texts
    main_title_text = StringProperty("")
    main_title_color = ObjectProperty((1, 1, 1, 1))
    main_subtitle_text = StringProperty("")
    # Panel title, subtitle and content texts
    panel_title_text = StringProperty("")
    panel_subtitle_text = StringProperty("")
    panel_content_text = StringProperty("")

    ## Properties provided by the kv file
    # Toggle buttons
    consultation_button = ObjectProperty(None)
    clock_button = ObjectProperty(None)
    # Linear progress bar
    progress_bar = ObjectProperty(None)
    # Sliding box layout for information panel
    sliding_box_layout = ObjectProperty(None)
    # Collapse panel information icon
    collapse_panel_icon = ObjectProperty(None)
    
    def __init__(self, viewmodel: TeamBridgeViewModel):
        super().__init__()
        # Save viewmodel
        self._viewmodel = viewmodel
        # Save running application
        self._app = App.get_running_app()
        # Save playing/finished sound
        self._sound = SOUND_CLOCKED

        # Schedule the clock time update
        Clock.schedule_interval(self._update_clock_time, 1.0) 

        # Observe the viewmodel texts
        self._viewmodel.main_title_text.observe(self._upd_main_title)
        self._viewmodel.main_subtitle_text.observe(self._upd_main_subtitle)
        self._viewmodel.panel_title_text.observe(self.upd_panel_title)
        self._viewmodel.panel_subtitle_text.observe(self._upd_panel_subtitle)
        self._viewmodel.panel_content_text.observe(self._upd_panel_content)
        # Observe the viewmodel state
        self._viewmodel.current_state.observe(self._on_state_change)
        # Update the UI style on theme change
        self._app.bind(theme=self._update_style)

        # Initialize default states
        self.collapse_panel_icon.opacity = 0.0

    def _update_clock_time(self, _):
        """
        Update the clock time and date.
        """
        self.clock_time = time.strftime("%H:%M")
        self.clock_date = time.strftime("%d %B %Y")

    def _upd_main_title(self, txt: str):
        if txt is not None:
            self.main_title_text = txt

    def _upd_main_subtitle(self, txt: str):
        if txt is not None:
            self.main_subtitle_text = txt

    def upd_panel_title(self, txt: str):
        if txt is not None:
            self.panel_title_text = txt

    def _upd_panel_subtitle(self, txt: str):
        if txt is not None:
            self.panel_subtitle_text = txt

    def _upd_panel_content(self, txt: str):
        if txt is not None:
            self.panel_content_text = txt

    def _on_state_change(self, state):
        """
        Update the state of view elements when the viewmodel state changes.
        """
        # Call the application activity method to wakeup the screen
        activity_states = ['ClockActionState', 'ClockSuccessState', 'ConsultationActionState', 
                           'ConsultationSuccessState', 'ErrorState']
        if state in activity_states:
            self._app.on_screen_activity()

        # Set the states for which the buttons are enabled
        enabled_states = ['WaitClockActionState', 'WaitConsultationActionState', 'ConsultationSuccessState']
        self.consultation_button.enabled = (state in enabled_states)
        # Clock button is enabled in error state for acknowledgment as well
        enabled_states.append('ErrorState')
        self.clock_button.enabled = (state in enabled_states)

        # Set the buttons toggle state
        self.clock_button.toggle_state = (state == 'WaitClockActionState' or state == 'ErrorState')
        self.consultation_button.toggle_state = (state == 'WaitConsultationActionState')

        # Set the progress bar loading state
        loading_states = ['ClockActionState', 'ClockSuccessState', 'ConsultationActionState']
        self.progress_bar.loading = (state in loading_states)

        # Set the bottom panel expanded when in consultation success state
        show_panel = (state == 'ConsultationSuccessState')
        self.sliding_box_layout.expanded = show_panel
        # Show the collapse panel icon when the panel is expanded
        Animation(opacity=1.0 if show_panel else 0.0, duration=0.5).start(self.collapse_panel_icon)

        # Play sound depending on current state
        state_sounds = {
            'ClockActionState': SOUND_SCANNED,
            'ConsultationActionState': SOUND_SCANNED,
            'ClockSuccessState': SOUND_CLOCKED,
            'ErrorState': SOUND_ERROR
        }
        # Check if state has an available sound
        if state in state_sounds and state_sounds[state]:
            # Stop previous sound if still playing
            self._sound.stop()
            # Play new sound
            self._sound = state_sounds[state]
            self._sound.volume = 1.0
            self._sound.play()

        # Update UI elements style
        self._update_style()

    def _update_style(self, *args):
        """
        Update the style of UI elements.
        """
        # Get current viewmodel state
        state = self._viewmodel.current_state.value

        # Set main title text color
        main_title_colors = {
            'InitialState': self._app.theme.error_color,
            'ClockSuccessState': self._app.theme.success_color,
            'ConsultationSuccessState': self._app.theme.success_color,
            'ErrorState': self._app.theme.error_color
        }
        # If the color is defined in the dict, use it. Otherwise use the default primary one.
        if state in main_title_colors:
            self.main_title_color = main_title_colors[state]
        else:
            self.main_title_color = self._app.theme.text_primary_color

    def on_clock_action_press(self):
        """
        Called when the clock action button is pressed.
        """
        state = self._viewmodel.current_state.value
        # Choose action based on viewmodel state
        if state == 'WaitConsultationActionState':
            # Set the next action to clock action
            self._viewmodel.next_action = ViewModelAction.CLOCK_ACTION
        elif state == 'ConsultationSuccessState':
            # Reset the viewmodel to go back in scanning state clock action
            self._viewmodel.next_action = ViewModelAction.RESET_TO_CLOCK_ACTION
        elif state == 'ErrorState':
            # Acknowledge the error
            self._viewmodel.next_action = ViewModelAction.RESET_TO_CLOCK_ACTION

    def on_consultation_press(self):
        """
        Called when the consultation button is pressed.
        """
        state = self._viewmodel.current_state.value
        # Choose action based on viewmodel state
        if state == 'WaitClockActionState':
            # Set the next action to consultation action
            self._viewmodel.next_action = ViewModelAction.CONSULTATION
        elif state == 'ConsultationSuccessState':
            # Reset the viewmodel to go back in scanning state consultation action
            self._viewmodel.next_action = ViewModelAction.RESET_TO_CONSULTATION

    def on_attendance_press(self):
        """
        Called when the reset button is pressed.
        """
        self._app.set_theme(DARK_THEME if self._app.get_theme() == LIGHT_THEME else LIGHT_THEME)

    def on_info_panel_press(self):
        """
        Called when the information panel is pressed to collapse it.
        """
        # Reset to waiting state if in consultation success state.
        if self._viewmodel.current_state.value == 'ConsultationSuccessState':
            # Send reset signal
            self._viewmodel.next_action = ViewModelAction.RESET_TO_CLOCK_ACTION

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

    # Progress bar opactity
    bar_alpha = NumericProperty(1.0)

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
        # Update loading flag
        last_loading = self._loading
        self._loading = value

        # Start animation on loading rising edge
        if not last_loading and self._loading:
            self._start_anim()
        # Stop animation on loading falling edge
        elif last_loading and not self._loading:
            self._stop_anim()

    def _start_anim(self, *kargs):
        """
        Start loading animation. Called continuously while loading flag is set.
        """
        # Reset value
        self.value = 0
        # Reschedule animation if still loading
        if self._loading:
            # Animate value for sliding effect
            self._anim = Animation(value=self.max, duration=2.0, transition='linear')
            # Fade in the progress bar
            self._anim &= Animation(bar_alpha=1.0, duration=0.4, transition='linear')
            # Recall this function on completion and start animation
            self._anim.bind(on_complete=self._start_anim)
            self._anim.start(self)

    def _stop_anim(self):
        """
        Stop the loading animation smoothly.
        """
        # Fade out the progress bar
        fadeout = Animation(bar_alpha=0.0, duration=0.4, transition='linear')
        fadeout.start(self)

class SlidingBoxLayout(BoxLayout):
    """
    A BoxLayout that can be expanded and collapsed. Typically added inside a
    FloatLayout.
    """

    # Collapsed position
    collapsed_pos = DictProperty({'x': 0, 'y': -1})
    # Expanded position
    expanded_pos = DictProperty({'x': 0, 'y': 0})
    # Animation duration
    duration = NumericProperty(1.0)
    # Current layout position
    current_pos = DictProperty({'x': 0, 'y': 0})

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create animation
        self._anim = None
        # Save current state
        self._is_expanded = False
        # Register the panel press event
        self.register_event_type('on_panel_press')

    def on_kv_post(self, base_widget):
        super().on_kv_post(base_widget)
        # Set position to initially collapsed
        self.current_pos = self.collapsed_pos

    def on_panel_press(self):
        pass

    @property
    def expanded(self) -> bool:
        """
        Returns:
            bool: expanded state
        """
        return self._is_expanded
    
    @expanded.setter
    def expanded(self, value: bool):
        """
        Set expanded state.

        Args:
            value: `bool` expanded state
        """
        # Check if state must change
        if self._is_expanded == value:
            # Nothing to do
            return
        
        # Change the state
        self._is_expanded = value
        # Cancel running animation
        if self._anim:
            self._anim.cancel(self)
        # Create and start next animation
        self._anim = Animation(
            current_pos=self.expanded_pos if self._is_expanded else self.collapsed_pos, 
            duration=self.duration, transition='out_quad')
        self._anim.start(self)

    def on_touch_down(self, touch):
        """
        Eat the touch event to prevent pressing a button behind the panel.
        """
        # Check the panel is touched
        if self.collide_point(*touch.pos):
            # Dispatch the event and eat it
            self.dispatch('on_panel_press')
            return True
        # Normal behavior
        return super().on_touch_down(touch)

class IconLabel(Label):
    """
    Simple label containing an icon from the material design icons font.
    """

    # Icon hexadecimal code
    icon_code = StringProperty("blank")

    def on_icon_code(self, *args):
        try:
            self.text = chr(int(self.icon_code, 16))
        except ValueError:
            self.text = ""
            LOGGER.warning("Cannot convert icon code to unicode.", exc_info=True)
