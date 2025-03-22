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

import tkinter as tk
from tkinter import Label, Button
from time_tracker_viewmodel import TimeTrackerViewModel, ScannerViewModelState
import playsound3
import pathlib
import ctypes

class TimeTrackerView:
    """GUI View for the Time Tracker application."""

    def __init__(self, root, viewmodel: TimeTrackerViewModel):
        """Initialize the UI and bind it to the ViewModel."""
        self.viewmodel = viewmodel
        self.root = root
        self.root.title("Time Tracker")
        self.root.geometry("640x480")

        # Make the layout flexible
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_rowconfigure(2, weight=1)

        # Status label
        self.status_label = Label(root, text="Waiting for scan...", font=("Arial", 14))
        self.status_label.grid(row=0, column=0, sticky="nsew", pady=10)

        # Scanning label
        self.scanning_label = Label(root, text="", font=("Arial", 12))
        self.scanning_label.grid(row=1, column=0, sticky="nsew", pady=10)

        # Close button
        self.close_button = Button(root, text="Close", command=self.close)
        self.close_button.grid(row=2, column=0, sticky="nsew", pady=20)

        # Observe ViewModel state changes
        self.viewmodel.get_current_state().observe(self.update_view)
        self.viewmodel.get_info_text().observe(self.update_view)
        self.viewmodel.get_scanning_state().observe(self.update_view)

        # Play a sound on scanning
        self.old_state = ScannerViewModelState.SCANNING
        self._playing_sound = None
        self.viewmodel.get_current_state().observe(self.__play_state_sound)

        # Initial view update
        self.update_view()

    def __play_state_sound(self, state):
        scanned_file = pathlib.Path("samples/scanned.wav")
        clocked_file = pathlib.Path("samples/clocked.wav")
        error_file   = pathlib.Path("samples/error.mp3")
        if self.old_state == ScannerViewModelState.SCANNING and state == ScannerViewModelState.LOADING:
            self.key_press_cnt = 5
            self.__press_ctrl_down()
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

        # Avoid redundant updates
        if self.scanning_label["text"] != f"Scanning: {scanning}":
            self.scanning_label.config(text=f"Scanning: {scanning}")

        # Update status label only if needed
        color_map = {
            ScannerViewModelState.SCANNING: "blue",
            ScannerViewModelState.LOADING: "black",
            ScannerViewModelState.SUCCESS: "green",
            ScannerViewModelState.ERROR: "red",
        }
        new_color = color_map.get(state, "black")

        if self.status_label["text"] != info_text or self.status_label["fg"] != new_color:
            self.status_label.config(text=info_text, fg=new_color)

        # Schedule automatic reset for success and error states
        if state == ScannerViewModelState.SUCCESS:
            self.root.after(4000, self.viewmodel.reset_state)
        elif state == ScannerViewModelState.ERROR:
            self.root.after(6000, self.viewmodel.reset_state)

        self.root.update()

    def close(self):
        """Handle window close event."""
        self.viewmodel.close()
        self.root.destroy()


# import tkinter as tk
# from tkinter import Label, Button
# from time_tracker_viewmodel import TimeTrackerViewModel, ScannerViewModelState

# class TimeTrackerView:
#     """
#     """
    
#     def __init__(self, root, viewmodel: TimeTrackerViewModel):
#         """
#         """
#         self.viewmodel = viewmodel
#         self.root = root
#         self.root.title("Time Tracker")
#         self.root.geometry("640x480")
        
#         # Status label
#         self.status_label = Label(root, text="Waiting for scan...", font=("Arial", 14))
#         self.status_label.grid()
        
#         # Scanning label
#         self.scanning_label = Label(root, text="", font=("Arial", 12))
#         self.scanning_label.grid()
        
#         # Action button
#         self.close_button = Button(root, text="Close", command=self.close)
#         self.close_button.grid()

#         # Observe the viewmodel
#         self.viewmodel.get_current_state().observe(lambda x: self.update_view())
#         self.viewmodel.get_info_text().observe(lambda x: self.update_view())
#         self.viewmodel.get_scanning_state().observe(lambda x: self.update_view())
        
#         # Initial view update
#         self.update_view()

#     def update_view(self):
#         # Update UI based on ViewModel state
#         scanning = self.viewmodel.get_scanning_state().get_value()
#         state = self.viewmodel.get_current_state().get_value()
#         info_text = self.viewmodel.get_info_text().get_value()
        
#         self.scanning_label.config(text=f"Scanning: {scanning}")
        
#         if state == ScannerViewModelState.SCANNING:
#             self.status_label.config(text=info_text, fg="blue")
#         elif state == ScannerViewModelState.LOADING:
#             self.status_label.config(text=info_text, fg="black")
#         elif state == ScannerViewModelState.SUCCESS:
#             self.status_label.config(text=info_text, fg="green")
#             self.root.after(4000, lambda: self.viewmodel.reset_state())
#         elif state == ScannerViewModelState.ERROR:
#             self.status_label.config(text=info_text, fg="red")
#             self.root.after(6000, lambda: self.viewmodel.reset_state())

#         self.root.update()
    
#     def close(self):
#         self.viewmodel.close()
#         self.root.destroy()
