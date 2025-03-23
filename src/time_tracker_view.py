#!/usr/bin/env python3
"""
File: time_tracker_view.py
Author: Bastian Cerf
Date: 02/03/2025
Description: 
    The view is responsible of displaying the view model state in an elegant manner.
    This implementation uses the classic tkinter graphic libaryr.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

#!/usr/bin/env python3
"""
File: time_tracker_view.py
Author: Bastian Cerf
Date: 02/03/2025
Description: 
    The view is responsible for displaying the view model state in an elegant manner.
    This implementation uses the classic tkinter graphic library.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

from tkinter import Label, Button
from time_tracker_viewmodel import TimeTrackerViewModel, ScannerViewModelState
import playsound3
import pathlib
import ctypes
import logging

LOGGER = logging.getLogger(__name__)

class TimeTrackerView:
    """GUI View for the Time Tracker application."""

    def __init__(self, root, viewmodel: TimeTrackerViewModel, fullscreen: bool=False, auto_wakeup: bool=False):
        """Initialize the UI and bind it to the ViewModel."""
        self.viewmodel = viewmodel
        self._pending_action_id = None
        self.root = root
        self.root.title("Time Tracker")
        self.root.geometry("640x480")
        self.root.attributes("-fullscreen", fullscreen)

        # Make the layout flexible
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=2)
        self.root.grid_rowconfigure(1, weight=2)
        self.root.grid_rowconfigure(2, weight=2)
        self.root.grid_rowconfigure(3, weight=1)

        # Labels
        self.status_label = Label(root, text="", font=("Arial", 14))
        self.status_label.grid(row=0, column=0, sticky="nsew", pady=10)
        self.data_label = Label(root, text="", font=("Arial", 12))
        self.data_label.grid(row=1, column=0, sticky="nsew", pady=10)
        self.scanning_label = Label(root, text="", font=("Arial", 12))
        self.scanning_label.grid(row=3, column=0, sticky="nsew", pady=10)

        # Reset button
        self.reset_button = Button(root, text="Ok", command=self.reset_viewmodel, width=20, height=5)
        self.reset_button.grid(row=2, column=0)

        # Close action
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        # Observe ViewModel state changes
        self.viewmodel.get_current_state().observe(self.update_view)
        self.viewmodel.get_info_text().observe(self.update_view)
        self.viewmodel.get_scanning_state().observe(self.update_view)
        self.viewmodel.get_employee_info_text().observe(self.update_view)

        # Schedule automatic reset once employee's data have been displayed
        self.viewmodel.get_employee_info_text().observe(self.__employee_text)

        # Play a sound on scanning
        self.old_state = ScannerViewModelState.SCANNING
        self._playing_sound = None
        self.viewmodel.get_current_state().observe(self.__play_state_sound)

        # Enable auto wakeup from sleep
        if auto_wakeup:
            self.wakeup_old_state = ScannerViewModelState.SCANNING
            self.viewmodel.get_current_state().observe(self.__auto_wakeup_screen)

        # Initial view update
        self.update_view()

    def __employee_text(self, text:str):
        if text.startswith("Solde"):
            self._pending_action_id = self.root.after(8000, self.reset_viewmodel)

    def __auto_wakeup_screen(self, state):
        if self.wakeup_old_state == ScannerViewModelState.SCANNING and state == ScannerViewModelState.LOADING:
            self.key_press_cnt = 5
            self.__press_ctrl_down()
        self.wakeup_old_state = state

    def __play_state_sound(self, state):
        scanned_file = pathlib.Path("samples/scanned.wav")
        clocked_file = pathlib.Path("samples/clocked.wav")
        error_file   = pathlib.Path("samples/error.mp3")
        if self.old_state == ScannerViewModelState.SCANNING and state == ScannerViewModelState.LOADING:
            self.__playsound(scanned_file)
        elif self.old_state == ScannerViewModelState.LOADING and state == ScannerViewModelState.SUCCESS:
            self.__playsound(clocked_file)
        elif self.old_state != ScannerViewModelState.ERROR and state == ScannerViewModelState.ERROR:
            self.__playsound(error_file)
        self.old_state = state

    def __playsound(self, file):
        # Stop current sound
        if self._playing_sound and self._playing_sound.is_alive():
            self._playing_sound.stop()
        # If file exists, play it
        if file.exists():
            self._playing_sound = playsound3.playsound(sound=file, block=False)

    def __press_ctrl_down(self):
        # Simulate CONTROL key press to unlock the session
        ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)  # CONTROL key down
        # Program key up
        self.root.after(50, self.__press_ctrl_up)

    def __press_ctrl_up(self):
        # Simulate CONTROL key press to unlock the session
        ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)  # CONTROL key up
        # Must continue
        if self.key_press_cnt > 0:
            self.key_press_cnt -= 1
            # Program key up
            self.root.after(50, self.__press_ctrl_down)

    def update_view(self, *_):
        """Update UI based on ViewModel state."""
        scanning = self.viewmodel.get_scanning_state().get_value()
        state = self.viewmodel.get_current_state().get_value()
        info_text = self.viewmodel.get_info_text().get_value()
        data_text = self.viewmodel.get_employee_info_text().get_value()

        # Scanning status
        self.scanning_label.config(text=f"Scan en fonction" if scanning else "Scan hors service")

        # Update status label
        color_map = {
            ScannerViewModelState.SCANNING: "blue",
            ScannerViewModelState.LOADING: "black",
            ScannerViewModelState.SUCCESS: "green",
            ScannerViewModelState.ERROR: "red",
        }
        if scanning:
            self.status_label.config(text=info_text, fg=color_map.get(state, "black"))
        else:
            self.status_label.config(text="Hors service", fg=color_map.get(ScannerViewModelState.ERROR, "black"))

        # Update data label
        self.data_label.config(text=data_text, fg='black')

        # Update the root
        self.root.update()

    def reset_viewmodel(self):
        # Reset pending action
        if self._pending_action_id:
            self.root.after_cancel(self._pending_action_id)
        self._pending_action_id = None
        # Reset viewmodel
        self.viewmodel.reset_state()

    def close(self):
        """Handle window close event."""
        self.viewmodel.close()
        self.root.destroy()
        LOGGER.info("Program closed by the View, goodbye.")
