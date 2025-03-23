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
import logging
from logging.handlers import TimedRotatingFileHandler
from time_tracker_model import TimeTrackerModel
from time_tracker_viewmodel import TimeTrackerViewModel
from spreadsheet_time_tracker import SpreadsheetTimeTracker
from time_tracker_view import TimeTrackerView
import tkinter as tk
import argparse
from spreadsheets_repository import SpreadsheetsRepository

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
            # Log to files
            TimedRotatingFileHandler(filename="teambridge.log", when="midnight", interval=1, backupCount=7, encoding="utf-8"),
            # Log to console
            console_handler                         
        ],
    )

    # Get module logger
    logger = logging.getLogger("Main")
    # Log welcome message
    logger.info("-- Mecacerf TeamBridge Application --")

    # Create the arguments parser
    parser = argparse.ArgumentParser(description="Mecacerf TeamBridge Application")
    parser.add_argument("--repository", type=str, default="samples/", help="Spreadsheets repository folder path")
    parser.add_argument("--scan-rate", type=int, default=6, help="Set scanning refresh rate [Hz]")
    parser.add_argument("--fullscreen", action="store_true", help="Enable fullscreen mode")
    parser.add_argument("--auto-wakeup", action="store_true", help="Enable auto screen wakeup on scanning event")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    # Parse the arguments
    args = parser.parse_args()
    # Show configuration
    logger.info(f"Starting with configuration [repository='{args.repository}', scan-rate={args.scan_rate}, fullscreen={args.fullscreen}"+
                f", auto-wakeup={args.auto_wakeup}, debug={args.debug}]")

    # Create the application model using a SpreadsheetTimeTracker
    repository = SpreadsheetsRepository(args.repository)
    time_tracker_provider=lambda date, code: SpreadsheetTimeTracker(repository=repository, employee_id=code, date=date)
    model = TimeTrackerModel(time_tracker_provider=time_tracker_provider, debug=args.debug, scan_rate=args.scan_rate)
    viewmodel = TimeTrackerViewModel(model)

    # Log some state changes
    viewmodel.get_scanning_state().observe(lambda scanning: logger.info(f"Camera scanning state: {scanning}"))
    viewmodel.get_current_state().observe(lambda state: logger.debug(f"ViewModel changes state '{state}'"))
    
    # Run tkinter
    root = tk.Tk()

    def update_model():
        model.run()
        root.after(ms=50, func=update_model)

    app = TimeTrackerView(root, viewmodel, fullscreen=args.fullscreen, auto_wakeup=args.auto_wakeup)
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
