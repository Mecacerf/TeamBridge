#!/usr/bin/env python3
"""
File: main.py
Author: Bastian Cerf
Date: 17/02/2025
Description: 
    TeamBridge program entry file.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

import sys
import os
import logging
from time_tracker_model import TimeTrackerModel
from time_tracker_viewmodel import TimeTrackerViewModel
from spreadsheet_time_tracker import SpreadsheetTimeTracker
from time_tracker_view import TimeTrackerView
import tkinter as tk
import argparse
from spreadsheets_database import SpreadsheetsDatabase

LOGGING_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

def main() -> int:
    """
    Application entry point.
    """
    # Create the console logs handler
    console_handler = logging.StreamHandler()
    # Apply the formatter for console logging
    console_handler.setFormatter(ColorFormatter())
    # Configure logging once for all modules
    logging.basicConfig(
        level=logging.DEBUG,    # Minimal level to log
        format=LOGGING_FORMAT,
        handlers=[
            logging.FileHandler("teambridge.log"),  # Logs to file
            console_handler                         # Logs to console
        ],
    )

    # Get module logger
    logger = logging.getLogger("Main")
    # Log welcome message
    logger.info("-- Mecacerf TeamBridge Application --")

    # Create the arguments parser
    parser = argparse.ArgumentParser(description="Mecacerf TeamBridge Application")
    parser.add_argument("--database-path", type=str, default="samples/", help="Database folder path")
    # Parse the arguments
    args = parser.parse_args()

    # Create the application model using a SpreadsheetTimeTracker
    database = SpreadsheetsDatabase(args.database_path)
    model = TimeTrackerModel(time_tracker_provider=lambda date, code: SpreadsheetTimeTracker(database=database, employee_id=code, date=date), debug=True, scan_rate=8)
    viewmodel = TimeTrackerViewModel(model)

    viewmodel.get_current_state().observe(lambda state: print(f"View model state = {state}"))
    viewmodel.get_info_text().observe(lambda txt: print(txt))
    viewmodel.get_scanning_state().observe(lambda scanning: print(f"Scanning: {scanning}"))

    root = tk.Tk()

    def update_model():
        model.run()
        root.after(ms=50, func=update_model)

    app = TimeTrackerView(root, viewmodel)
    root.after(ms=50, func=update_model)
    root.mainloop()

class ColorFormatter(logging.Formatter):
    """
    Custom log formatter that colors only the log level name if the terminal supports it.
    """
    
    COLORS = {
        "DEBUG": "\033[94m",    # Blue
        "INFO": "\033[92m",     # Green
        "WARNING": "\033[93m",  # Yellow
        "ERROR": "\033[91m",    # Red
        "CRITICAL": "\033[41m", # White on Red
        "RESET": "\033[0m"      # Reset color
    }

    def __init__(self):
        super().__init__(LOGGING_FORMAT)

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)

if __name__ == "__main__":
    sys.exit(main())
