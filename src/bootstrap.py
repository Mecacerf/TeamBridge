#!/usr/bin/env python3
"""
File: bootstrap.py
Author: Bastian Cerf
Date: 23/08/2025
Description:
    TeamBridge program bootstrap.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import logging, logging.handlers
import argparse
import locale
from typing import Any

# Internal libraries
from local_config import LocalConfig, CONFIG_FILE_PATH

logger = logging.getLogger(__name__)
reporter: Any = None


# Logging configuration
LOGGING_FILE_NAME = "teambridge.log"
LOGGING_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def _configure_logging():
    """
    Configure the logging module.

    Logs are saved in log files (.log) with a time rotating strategy.
    A new log file is created at midnight and they are available up to
    7 days. Logs are also printed in the standard output stream.
    """

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
            # Log to files with a time rotating strategy
            logging.handlers.TimedRotatingFileHandler(
                filename=LOGGING_FILE_NAME,
                when="midnight",
                interval=1,
                backupCount=7,
                encoding="utf-8",
            ),
            # Log to console
            console_handler,
        ],
    )


def _load_config() -> LocalConfig:
    """
    Parse the program arguments and check if a custom configuration file
    path is configured. If not, fallback to `CONFIG_FILE_PATH`.

    The local configuration file is then parsed and validated against
    its schema.

    Returns:
        LocalConfig: Local configuration handle.
    """
    # Parse the config program argument
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

    return config


def _load_reporter():
    """
    Load a program reporter module. An object respecting the `Reporter`
    interface is then available globally.
    """
    from common.email_reporter import EmailReporter

    global reporter
    reporter = EmailReporter()


def _set_locale(value: str):
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


def _load_backend(config: LocalConfig) -> Any:
    """
    Load the application backend services. It returns a handle on a
    backend object to inject into frontend services.

    Returns:
        Any: Loaded backend handle.
    """
    repo_conf = config.section("repository")

    # Import program backend modules
    from core.spreadsheets.sheet_time_tracker_factory import SheetTimeTrackerFactory
    from platform_io.barcode_scanner import BarcodeScanner
    from viewmodel.teambridge_viewmodel import TeamBridgeViewModel
    from model.teambridge_scheduler import TeamBridgeScheduler

    # Create the tasks scheduler with a SheetTimeTrackerFactory
    factory = SheetTimeTrackerFactory(repo_conf["repository"])
    model = TeamBridgeScheduler(tracker_factory=factory)

    # Create the viewmodel with a standard barcode scanner
    scanner = BarcodeScanner()
    return TeamBridgeViewModel(model=model, scanner=scanner)


def _load_sleep_manager(config: LocalConfig) -> Any:
    """
    Load a sleep manager, if specified by the local configuration.

    Returns:
        Any: Sleep manager handle.
    """
    sleep_conf = config.section("sleep")

    from platform_io.sleep_manager import SleepManager

    # Create a sleep manager
    # It is disabled if timeout is None or 0
    if not sleep_conf["sleep_timeout"]:
        return None

    if sleep_conf["work_brightness"]:
        return SleepManager(
            sleep_conf["sleep_timeout"],
            low_brightness_lvl=sleep_conf["sleep_brightness"],
            high_brightness_lvl=sleep_conf["work_brightness"],
        )
    else:
        # Use automatic screen brightness (not specified).
        return SleepManager(
            sleep_conf["sleep_timeout"],
            low_brightness_lvl=sleep_conf["sleep_brightness"],
        )


def _load_kivy_frontend(config: LocalConfig, backend: Any, sleep_manager: Any) -> Any:
    """
    Load the Kivy frontend. Requires handles on the backend and optionally
    a sleep manager.

    Returns:
        Any: Application handle.
    """
    ui_conf = config.section("ui")

    # Import the view module to configure Kivy
    from kivy_view.teambridge_view import TeamBridgeApp
    from kivy_view.view_theme import DARK_THEME

    theme = DARK_THEME if ui_conf["dark_mode"] else None

    app = TeamBridgeApp(
        backend,
        fullscreen=ui_conf["fullscreen"],
        theme=theme,
        sleep_manager=sleep_manager,
    )

    logger.info(f"'{app}' configured with Kivy frontend.")
    return app


def app_bootstrap() -> Any:
    """
    Standard application bootstrap. Load the logging module, the program
    configuration, the backend services and finally the configured
    frontend.

    Returns:
        Any: An application handle that supports calling a blocking
            run() and a stop() on it.
    """
    _configure_logging()
    logger.info("... TeamBridge Application Startup ...")

    config = _load_config()
    general_conf = config.section("general")

    logger.info(f"Application device identifier is '{general_conf["device"]}'.")

    _load_reporter()

    if general_conf["locale"]:
        _set_locale(general_conf["locale"])

    backend = _load_backend(config)
    sleep_manager = _load_sleep_manager(config)

    if str(general_conf["frontend"]).lower() == "kivy":
        app = _load_kivy_frontend(config, backend, sleep_manager)
    else:
        raise NotImplementedError(
            f"The frontend '{general_conf["frontend"]}' is not supported."
        )

    return app
