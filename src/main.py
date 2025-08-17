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
import logging, logging.handlers
import locale
import argparse

# Internal libraries
from local_config import LocalConfig, CONFIG_FILE_PATH


def configure_logging():
    """
    Configure logging.
    """
    # Define file logs format
    LOGGING_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    class ColorFormatter(logging.Formatter):
        """
        Custom log formatter that colors only the log level name if the
        terminal supports it.
        """

        COLORS = {
            "DEBUG": "\033[94m",  # Blue
            "INFO": "\033[92m",  # Green
            "WARNING": "\033[93m",  # Yellow
            "ERROR": "\033[91m",  # Red
            "CRITICAL": "\033[41m",  # White on Red
            "RESET": "\033[0m",  # Reset color
        }

        def __init__(self):
            super().__init__(LOGGING_FORMAT)

        def format(self, record: logging.LogRecord):
            color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
            record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
            return super().format(record)

    # Create the console logs handler
    console_handler = logging.StreamHandler()
    # Apply the formatter for console logging
    console_handler.setFormatter(ColorFormatter())
    # Configure logging once for all modules
    logging.basicConfig(
        level=logging.DEBUG,  # Minimal level to log
        format=LOGGING_FORMAT,
        encoding="utf-8",
        handlers=[
            # Log to files
            logging.handlers.TimedRotatingFileHandler(
                filename="teambridge.log",
                when="midnight",
                interval=1,
                backupCount=7,
                encoding="utf-8",
            ),
            # Log to console
            console_handler,
        ],
    )


configure_logging()
logger = logging.getLogger("main")


def main() -> int:
    """
    Application entry point.
    """
    logger.info("-- Mecacerf TeamBridge Application --")

    parser = argparse.ArgumentParser(description="Mecacerf TeamBridge Application")
    parser.add_argument(
        "--config",
        type=str,
        default=CONFIG_FILE_PATH,
        help=(
            "Path to local configuration file (.ini). "
            "A default file is created if not existing."
        ),
    )

    args = parser.parse_args()

    # Load local configuration
    config = LocalConfig(args.config)
    config.show_config()

    general_conf = config.section("general")
    repo_conf = config.section("repository")
    scan_conf = config.section("scanner")
    sleep_conf = config.section("sleep")
    ui_conf = config.section("ui")
    debug_conf = config.section("debug")

    logger.info(f"Current device identifier is '{general_conf["device"]}'.")

    # Import program backend modules
    from core.spreadsheets.sheet_time_tracker_factory import SheetTimeTrackerFactory
    from platform_io.barcode_scanner import BarcodeScanner
    from platform_io.sleep_manager import SleepManager
    from viewmodel.teambridge_viewmodel import TeamBridgeViewModel
    from model.teambridge_scheduler import TeamBridgeScheduler

    # Create the model and inject a sheet time tracker factory
    factory = SheetTimeTrackerFactory(repo_conf["repository"])
    model = TeamBridgeScheduler(tracker_factory=factory)

    scanner = BarcodeScanner()
    viewmodel = TeamBridgeViewModel(model=model, scanner=scanner)

    # Configure sleep mode, it is disabled if timeout is None or 0
    sleep_timeout = 0
    sleep_manager = None
    # If the sleep timeout is specified, the sleep mode is enabled
    if sleep_conf["sleep_timeout"]:
        # Sleep mode is enabled, configure the sleep manager
        if sleep_conf["work_brightness"]:
            # Use specified work brightness
            sleep_manager = SleepManager(
                low_brightness_lvl=sleep_conf["sleep_brightness"],
                high_brightness_lvl=sleep_conf["work_brightness"],
            )
        else:
            # Use automatic screen brightness (do not specify it).
            sleep_manager = SleepManager(
                low_brightness_lvl=sleep_conf["sleep_brightness"]
            )
        # Set the sleep timeout
        sleep_timeout = sleep_conf["sleep_timeout"]

    # Configure locale
    if general_conf["locale"]:
        set_locale(general_conf["locale"])

    raise OSError("test euh error")

    def start_kivy_frontend():
        """
        Start the Kivy frontend.
        """
        # Import the view module first to configure Kivy first
        from kivy_view.teambridge_view import TeamBridgeApp

        # Configure UI theme
        from kivy_view.view_theme import DARK_THEME

        theme = DARK_THEME if ui_conf["dark_mode"] else None

        # Create the teambridge application using Kivy frontend
        app = TeamBridgeApp(
            viewmodel,
            fullscreen=ui_conf["fullscreen"],
            theme=theme,
            sleep_manager=sleep_manager,
            sleep_timeout=sleep_timeout,
        )

        # Start application
        logger.info(f"Starting application '{app}' using Kivy frontend.")
        app.run()

    # Start the application frontend
    start_kivy_frontend()

    return 0


def set_locale(value: str):
    """
    Try to set the desired locale configuration.
    """
    # Try to set the local language setting
    try:
        locale.setlocale(locale.LC_TIME, value)
        # Confirm the locale has been set
        actual = locale.getlocale(locale.LC_TIME)
        if actual[0] != value:
            raise UnicodeError(f"Cannot set locale to '{value}'.")

    except Exception as ex:
        logger.warning(f"Unable to set the desired locale '{value}': {ex}")

    actual = locale.getlocale(locale.LC_TIME)
    encoding = locale.getpreferredencoding(False)
    logger.info(f"Using locale {actual} with preferred encoding '{encoding}'.")


def show_error_dialog(exc: Exception):
    """
    Create a hidden Tkinter root just for the error dialog
    """
    print("error dialog show")
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        logger.error("Cannot show an error dialog, tkinter seems uninstalled.")

    root = tk.Tk()
    root.withdraw()

    messagebox.showerror(
        "Critical Error",
        f"The program has encountered a critical error:\n\n{exc}\n\n"
        "The application will now close.",
    )

    root.destroy()


# Program entry
if __name__ == "__main__":
    exit_code = 0
    try:
        main()
    except Exception as ex:
        exit_code = 1
        logger.info("will show dialog")
        show_error_dialog(ex)

    sys.exit(exit_code)
