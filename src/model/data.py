#!/usr/bin/env python3
"""
File: data.py
Author: Bastian Cerf
Date: 11/05/2025
Description:
    Provides dataclasses used to communicate sets of information about
    employees between the program components.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
from dataclasses import dataclass, field
from typing import Optional
import datetime as dt
from abc import ABC

# Internal imports
from core.time_tracker import ClockEvent
from core.attendance.attendance_validator import AttendanceError


@dataclass(frozen=True)
class IModelMessage(ABC):
    """
    A generic asynchronous message sent by the model to upper layers.
    """

    pass


@dataclass(frozen=True)
class EmployeeInfo(IModelMessage, ABC):
    """
    Base container for employee's message.

    Attributes:
        name (str): Employee's name.
        firstname (str): Employee's firstname.
        id (str): Employee's id.
    """

    name: str
    firstname: str
    id: str


@dataclass(frozen=True)
class EmployeeEvent(EmployeeInfo):
    """
    Describes a clock event for an employee.

    Attributes:
        name (str): Employee's name.
        firstname (str): Employee's firstname.
        id (str): Employee's id.
        clock_evt (ClockEvent): Related clock event.
    """

    clock_evt: ClockEvent


@dataclass(frozen=True)
class EmployeeData(EmployeeInfo):
    """
    Container of different information about an employee.

    Attributes:
        name (str): Employee's name.
        firstname (str): Employee's firstname.
        id (str): Employee's id.
        date_errors (dict[dt.date, AttendanceError]): Dictionary of all
            errors found from the first of January to now.
        dominant_error (AttendanceError): Most critical error found, if
            its status is error, some information may be missing.
        clocked_in (bool): `True` if the employee is clocked in.
        day_schedule_time (dt.timedelta): Employee's day scheduled work
            time.
        day_worked_time (dt.timedelta): Employee's day worked time.
        day_balance (dt.timedelta): Employee's day balance.
        month_expected_day_schedule (dt.timedelta): Expected month's day
            schedule.
        month_schedule_time (dt.timedelta): Scheduled work time for the
            month.
        month_worked_time (dt.timedelta): Worked time in the month.
        month_balance (dt.timedelta): Time balance for the month.
        month_to_yday_balance (dt.timedelta): Month-to-yesterday balance.
        month_vacation (dt.timedelta): Planned vacation for the month.
        year_vacation (float): Planned vacation for the whole year.
        remaining_vacation (float): Remaining vacation to be planned.
        ytd_balance (dt.timedelta): Year-to-date balance.
        yty_balance (dt.timedelta): Year-to-yesterday balance.

        The optional indicates that the value may be missing if an error
        exists (dominant_error status is critical).
    """

    date_errors: dict[dt.date, AttendanceError]
    dominant_error: AttendanceError
    clocked_in: Optional[bool] = field(default=None)
    day_schedule_time: Optional[dt.timedelta] = field(default=None)
    day_worked_time: Optional[dt.timedelta] = field(default=None)
    day_balance: Optional[dt.timedelta] = field(default=None)
    month_expected_day_schedule: Optional[dt.timedelta] = field(default=None)
    month_schedule_time: Optional[dt.timedelta] = field(default=None)
    month_worked_time: Optional[dt.timedelta] = field(default=None)
    month_balance: Optional[dt.timedelta] = field(default=None)
    month_to_yday_balance: Optional[dt.timedelta] = field(default=None)
    month_vacation: Optional[float] = field(default=None)
    year_vacation: Optional[float] = field(default=None)
    remaining_vacation: Optional[float] = field(default=None)
    ytd_balance: Optional[dt.timedelta] = field(default=None)
    yty_balance: Optional[dt.timedelta] = field(default=None)


@dataclass(frozen=True)
class ModelError(IModelMessage):
    """
    Error message container.

    Attributes:
        error_code (int): Error code.
        message (str): Error description.
    """

    error_code: int
    message: str


@dataclass(frozen=True)
class AttendanceList(IModelMessage):
    """
    Attendance list message container.

    Attributes:
        present (list[EmployeeInfo]): List of present employees.
        absent (list[EmployeeInfo]): List of absent employees.
        unkown (list[EmployeeInfo]): List of not fetchable employees.
        fetch_time (float): Duration of the fetching process [s].
    """

    present: list[EmployeeInfo]
    absent: list[EmployeeInfo]
    unknown: list[EmployeeInfo]
    fetch_time: float
