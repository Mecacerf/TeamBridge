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
import argparse
import logging, logging.handlers
from teambridge_model import TeamBridgeModel
from teambridge_viewmodel import TeamBridgeViewModel
from teambridge_view import TeamBridgeApp
from spreadsheet_time_tracker import SpreadsheetTimeTracker
from barcode_scanner import BarcodeScanner
from spreadsheets_repository import SpreadsheetsRepository

def main() -> int:
    """
    Application entry point.
    """
    # Configure logging and get module logger
    configure_logging()
    logger = logging.getLogger("Main")
    # Log welcome message
    logger.info("-- Mecacerf TeamBridge Application --")

    # Create the arguments parser
    parser = argparse.ArgumentParser(description="Mecacerf TeamBridge Application")
    parser.add_argument("--repository", type=str, default="assets/", help="Spreadsheets repository folder path")
    parser.add_argument("--scan-rate", type=int, default=6, help="Set scanning refresh rate [Hz]")
    parser.add_argument("--camera-id", type=int, default=0, help="Select the camera that will be used for scanning")
    parser.add_argument("--fullscreen", action="store_true", help="Enable fullscreen mode")
    parser.add_argument("--auto-wakeup", action="store_true", help="Enable auto screen wakeup on scanning event [NOT IMPLEMENTED]")
    parser.add_argument("--dark", action="store_true", help="Enable the UI dark mode")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    # Parse the arguments
    args = parser.parse_args()
    # Show configuration
    logger.info(f"Starting with configuration [repository='{args.repository}', scan-rate={args.scan_rate}, fullscreen={args.fullscreen}"+
                f", auto-wakeup={args.auto_wakeup}, debug={args.debug}]")

    # Configure application
    # Use a spreadsheet repository
    repository = SpreadsheetsRepository(args.repository)
    # Create the time trackers provider
    provider = lambda date, code: SpreadsheetTimeTracker(repository=repository, employee_id=code, date=date)
    # Create the application model
    model = TeamBridgeModel(time_tracker_provider=provider)
    # Create the barcode scanner
    scanner = BarcodeScanner()
    # Create the application viewmodel
    viewmodel = TeamBridgeViewModel(model=model, scanner=scanner, debug_mode=args.debug, scan_rate=args.scan_rate, cam_idx=args.camera_id)
    # Set UI theme
    from view_theme import DARK_THEME
    theme = DARK_THEME if args.dark else None
    # Create the teambridge application
    app = TeamBridgeApp(viewmodel, fullscreen=args.fullscreen, theme=theme)

    logger.info(f"Starting application '{app}'.")
    app.run()

def configure_logging():
    """
    Configure logging.
    """
    # Define file logs format
    LOGGING_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

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
            logging.handlers.TimedRotatingFileHandler(filename="teambridge.log", 
                                                      when="midnight", 
                                                      interval=1, 
                                                      backupCount=7, 
                                                      encoding="utf-8"),
            # Log to console
            console_handler                         
        ],
    )

# Program entry
if __name__ == "__main__":
    sys.exit(main())
