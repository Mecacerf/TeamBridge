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
from src.core.time_tracker import ClockEvent

@dataclass(frozen=True)
class IModelMessage(ABC):
    """
    A generic asynchronous message sent by the model to upper layers.
    """
    pass

@dataclass(frozen=True)
class IEmployeeMessage(IModelMessage, ABC):
    """
    Base container for employee's message.

    Attributes:
        name: `str` employee's name
        firstname: `str` employee's firstname
        id: `str` employee's id
    """
    name: str
    firstname: str
    id: str

@dataclass(frozen=True)
class EmployeeEvent(IEmployeeMessage):
    """
    Describes a clock event for an employee.

    Attributes:
        name: `str` employee's name
        firstname: `str` employee's firstname
        id: `str` employee's id
        clock_evt: `ClockEvent` related clock event
    """
    clock_evt: ClockEvent

@dataclass(frozen=True)
class EmployeeData(IEmployeeMessage):
    """
    Container of different information about an employee.

    Attributes:
        name: `str` employee's name
        firstname: `str` employee's firstname
        id: `str` employee's id
        daily_worked_time: `timedelta` employee's daily worked time 
        daily_balance: `timedelta` employee's daily balance
        daily_scheduled_time: `timedelta` employee's daily scheduled time
        monthly_balance: `timedelta` employee's monthly balance
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
        error_code: error code
        message: error description message
    """
    error_code: int
    message: str
