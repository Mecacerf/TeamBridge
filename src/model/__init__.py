#!/usr/bin/env python3
"""
File: __init__.py
Author: Bastian Cerf
Date: 11/05/2025
Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Expose everything from data and scheduler modules
from .data import *
from .teambridge_scheduler import *

__all__ = [
    "IModelMessage",
    "EmployeeInfo",
    "EmployeeEvent",
    "EmployeeData",
    "AttendanceList",
    "ModelError",
    "TeamBridgeScheduler",
]
