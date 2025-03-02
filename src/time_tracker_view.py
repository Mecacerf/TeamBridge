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

import tkinter as tk
from tkinter import Label, Button
from time_tracker_viewmodel import TimeTrackerViewModel, ScannerViewModelState

class TimeTrackerView:
    """
    """
    
    def __init__(self, root, viewmodel: TimeTrackerViewModel):
        """
        """
        self.viewmodel = viewmodel
        self.root = root
        self.root.title("Time Tracker")
        self.root.geometry("640x480")
        
        # Status label
        self.status_label = Label(root, text="Waiting for scan...", font=("Arial", 14))
        self.status_label.grid()
        
        # Scanning label
        self.scanning_label = Label(root, text="", font=("Arial", 12))
        self.scanning_label.grid()
        
        # Action button
        self.close_button = Button(root, text="Close", command=self.close)
        self.close_button.grid()

        # Observe the viewmodel
        self.viewmodel.get_current_state().observe(lambda x: self.update_view())
        self.viewmodel.get_info_text().observe(lambda x: self.update_view())
        self.viewmodel.get_scanning_state().observe(lambda x: self.update_view())
        
        # Initial view update
        self.update_view()

    def update_view(self):
        # Update UI based on ViewModel state
        scanning = self.viewmodel.get_scanning_state().get_value()
        state = self.viewmodel.get_current_state().get_value()
        info_text = self.viewmodel.get_info_text().get_value()
        
        self.scanning_label.config(text=f"Scanning: {scanning}")
        
        if state == ScannerViewModelState.SCANNING:
            self.status_label.config(text=info_text, fg="blue")
        elif state == ScannerViewModelState.SUCCESS:
            self.status_label.config(text=info_text, fg="green")
            self.root.after(3000, lambda: self.viewmodel.reset_state())
        elif state == ScannerViewModelState.ERROR:
            self.status_label.config(text=info_text, fg="red")
            self.root.after(6000, lambda: self.viewmodel.reset_state())
    
    def close(self):
        self.viewmodel.close()
        self.root.destroy()
