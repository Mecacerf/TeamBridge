#!/usr/bin/env python3
"""
TeamBridge - An open-source timestamping application

Author: Bastian Cerf
Copyright (C) 2025 Mecacerf SA
License: AGPL-3.0 <https://www.gnu.org/licenses/>
"""

# Import general purpose libraries
import sys
import logging

# Internal libraries
import bootstrap

logger = logging.getLogger("main")


def show_error_dialog(exc: Exception):
    """
    Try to show an error dialog using Tkinter to inform of the crash.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        logger.error("Cannot show an error dialog, tkinter seems uninstalled.")
        return

    root = tk.Tk()
    root.withdraw()

    # Show a blocking error message box
    messagebox.showerror(
        title="Error",
        message=f"The program encountered an error and cannot continue.\n\n{exc}\n\n",
    )

    root.destroy()


def report_crash(exc: Exception):
    """
    Try to send a crash report.
    """
    from common.config_parser import ConfigError

    try:
        from common.reporter import Report, ReportSeverity
        from local_config import LocalConfig

        with bootstrap.load_reporter(LocalConfig()) as reporter:
            reporter.send_report(
                Report(
                    ReportSeverity.CRITICAL,
                    "Crash report",
                    (
                        "Teambridge encountered a critical error and must be "
                        "restarted manually.\n\n"
                        f"{exc.__class__.__name__}: {exc}."
                    ),
                ).attach_logs()
            )

    except ConfigError:
        logger.warning(
            "No crash report sent. The configuration was not available at the "
            "time of crash."
        )
    except Exception as ex:
        logger.exception(f"An exception occurred sending the crash report: {ex}")


# Program entry
if __name__ == "__main__":
    exit_code = 0
    app = None

    try:
        # App bootstrap (logging, services, etc)
        app = bootstrap.app_bootstrap()

        app.run()

    except Exception as exc:
        exit_code = 1
        try:
            # Log the crash if logging is ready
            logger = logging.getLogger("main")
            logger.exception("An unhandled exception occurred.")
        except Exception:
            # Fallback to print
            print(f"An unhandled exception occurred {exc}.")

        report_crash(exc)
        show_error_dialog(exc)

        # Try to terminate the app
        try:
            if app:
                app.stop()
        except Exception:
            pass

    sys.exit(exit_code)
