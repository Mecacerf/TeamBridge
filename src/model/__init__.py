#!/usr/bin/env python3
"""
TeamBridge - An open-source timestamping application

Author: Bastian Cerf
Copyright (C) 2025 Mecacerf SA
License: AGPL-3.0 <https://www.gnu.org/licenses/>
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
