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

from dataclasses import dataclass
import datetime as dt
from abc import ABC

# Internal import: ClockEvent is used as is in some dataclasses
from core.time_tracker import ClockEvent


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
        daily_worked_time (dt.timedelta): Employee's daily worked time.
        daily_balance (dt.timedelta): Employee's daily balance.
        daily_scheduled_time (dt.timedelta): Employee's daily scheduled time.
        monthly_balance (dt.timedelta): Employee's monthly balance.
    """

    daily_worked_time: dt.timedelta
    daily_balance: dt.timedelta
    daily_scheduled_time: dt.timedelta
    monthly_balance: dt.timedelta


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
