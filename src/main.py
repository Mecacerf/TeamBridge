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

# Import general purpose libraries
import sys
import argparse
import logging, logging.handlers

def main() -> int:
    """
    Application entry point.
    """
    # Configure logging and get module logger
    configure_logging()
    logger = logging.getLogger("Main")
    # Log a welcome message
    logger.info("-- Mecacerf TeamBridge Application --")

    # Custom function to parse positive integer.
    def positive_int(value):
        ivalue = int(value)
        if ivalue < 0:
            raise argparse.ArgumentTypeError("The value must be a positive integer")
        return ivalue

    # Create the arguments parser
    parser = argparse.ArgumentParser(description="Mecacerf TeamBridge Application")
    parser.add_argument("--repository", type=str, default="samples/", help="Spreadsheets repository folder path")
    parser.add_argument("--scan-rate", type=positive_int, default=4, help="Set scanning refresh rate [Hz]")
    parser.add_argument("--camera-id", type=positive_int, default=0, help="Select the camera that will be used for scanning")
    parser.add_argument("--fullscreen", action="store_true", help="Enable fullscreen mode")
    parser.add_argument("--dark", action="store_true", help="Enable the UI dark mode")
    parser.add_argument("--sleep-brightness", type=positive_int, default=0, help="Screen brightness in sleep mode")
    parser.add_argument("--work-brightness", type=positive_int, default=argparse.SUPPRESS, help="Screen brightness in normal/working mode, if not set, the current brightness at application startup is selected")
    parser.add_argument("--sleep-timeout", type=positive_int, default=argparse.SUPPRESS, help="Sleep timeout in seconds, if not specified the sleep mode is disabled")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    # Parse the arguments
    args = parser.parse_args()
    # Show configuration
    logger.info(f"Starting with configuration [repository='{args.repository}', scan-rate={args.scan_rate}, camera-id={args.camera_id}, "
                f"fullscreen={args.fullscreen}, dark_mode={args.dark}, sleep_brightness={args.sleep_brightness}, "
                f"work_brightness={args.work_brightness if hasattr(args, 'work_brightness') else "auto"}, "
                f"sleep_timeout={args.sleep_timeout if hasattr(args, 'sleep_timeout') else 'disabled'}, debug={args.debug}]")

    # Import program backend modules
    from core.spreadsheets_repository import SpreadsheetsRepository
    from core.spreadsheet_time_tracker import SpreadsheetTimeTracker
    from platform_io.barcode_scanner import BarcodeScanner
    from platform_io.sleep_manager import SleepManager
    from viewmodel.teambridge_viewmodel import TeamBridgeViewModel
    from model.teambridge_scheduler import TeamBridgeScheduler

    # Configure application
    # Use a spreadsheet repository
    repository = SpreadsheetsRepository(args.repository)
    # Create the time trackers provider
    provider = lambda date, code: SpreadsheetTimeTracker(repository=repository, employee_id=code, date=date)
    # Create the application model
    model = TeamBridgeScheduler(time_tracker_provider=provider)
    # Create the barcode scanner
    scanner = BarcodeScanner()
    # Create the application viewmodel
    viewmodel = TeamBridgeViewModel(model=model, scanner=scanner, debug_mode=args.debug, scan_rate=args.scan_rate, cam_idx=args.camera_id)

    # Configure sleep mode, it is disabled by default.
    sleep_timeout = 0
    sleep_manager = None
    # If the sleep timeout is specified, the sleep mode is enabled.
    if hasattr(args, 'sleep_timeout'):
        # Sleep mode is enabled, configure the sleep manager.
        if hasattr(args, 'work_brightness'):
            # Use specified work brightness.
            sleep_manager = SleepManager(low_brightness_lvl=args.sleep_brightness,
                                         high_brightness_lvl=args.work_brightness)
        else:
            # Use automatic screen brightness (do not specify it).
            sleep_manager = SleepManager(low_brightness_lvl=args.sleep_brightness)
        # Set the sleep timeout.
        sleep_timeout = args.sleep_timeout

    def start_kivy_frontend():
        """
        Start the Kivy frontend.
        """
        # Import the view module first to configure Kivy first
        from kivy_view.teambridge_view import TeamBridgeApp

        # Configure UI theme
        from kivy_view.view_theme import DARK_THEME
        theme = DARK_THEME if args.dark else None

        # Create the teambridge application using Kivy frontend       
        app = TeamBridgeApp(viewmodel, 
                            fullscreen=args.fullscreen, 
                            theme=theme,
                            sleep_manager=sleep_manager,
                            sleep_timeout=sleep_timeout)

        # Start application
        logger.info(f"Starting application '{app}' using Kivy frontend.")
        app.run()

    # Start the frontend to use.
    start_kivy_frontend()

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
