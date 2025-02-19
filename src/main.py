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
import datetime
from spreadsheet_time_tracker import SpreadsheetTimeTracker
from time_tracker_interface import ClockEvent, ClockAction

def main() -> int:
    """
    """

    employee = SpreadsheetTimeTracker("samples/", "000", datetime.datetime.now().date())
    print(employee.get_firstname())
    print(employee.get_name())
    employee.register_clock(ClockEvent(datetime.datetime.now().time(), ClockAction.CLOCK_IN))
    employee.register_clock(ClockEvent((datetime.datetime.now()+datetime.timedelta(hours=1)).time(), ClockAction.CLOCK_OUT))
    print(f"Today events: {employee.get_clock_events_today()}")
    print(f"Monthly balance: {employee.get_monthly_balance()}")
    print(f"Today balance: {employee.get_worked_time_today()}")

if __name__ == "__main__":
    sys.exit(main())
