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
from spreadsheet_time_tracker import SpreadsheetTimeTracker
import time

def main() -> int:
    """
    """
    # Create the application model using a SpreadsheetTimeTracker
    model = TimeTrackerModel(time_tracker_provider=lambda date, code: SpreadsheetTimeTracker("samples/", code, date))

    # Run
    while True:
        time.sleep(0.1)
        model.run()

if __name__ == "__main__":
    sys.exit(main())
