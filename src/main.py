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
from time_tracker_model import TimeTrackerModel
from time_tracker_viewmodel import TimeTrackerViewModel
from spreadsheet_time_tracker import SpreadsheetTimeTracker
from time_tracker_view import TimeTrackerView
import tkinter as tk
import argparse
from spreadsheets_database import SpreadsheetsDatabase

def main() -> int:
    """
    """
    # Create the argument parser
    parser = argparse.ArgumentParser(description="TeamBridge Mecacerf Timbreuse.")
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

if __name__ == "__main__":
    sys.exit(main())
