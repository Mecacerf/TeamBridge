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
    try:
        from common.reporter import Reporter, Report, ReportSeverity

        reporter: Reporter = bootstrap.load_reporter(sync=True)
        reporter.report(
            Report(
                ReportSeverity.CRITICAL,
                "Crash report",
                (
                    "Teambridge encountered a critical error and must be manually "
                    "restarted.\n\n"
                    f"Exception: {exc}."
                ),
            ).attach_logs()
        )
    except Exception as e:
        logger.error(f"An error occurred sending the error report: {e}.")


# Program entry
if __name__ == "__main__":
    exit_code = 0
    app = None

    try:
        # App bootstrap (logging, services, etc)
        app = bootstrap.app_bootstrap()

        # Start application
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
