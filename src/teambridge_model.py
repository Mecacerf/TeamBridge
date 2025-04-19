#!/usr/bin/env python3
"""
File: teambridge_model.py
Author: Bastian Cerf
Date: 02/03/2025
Description: 
    Gives an asynchronous way of manipulating employees time tracker through the
    TimeTrackerModel object. Different tasks can be started and responses can
    be listened by observing the message bus.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

from time_tracker_interface import ITodayTimeTracker, ClockEvent, ClockAction
from typing import Callable
import datetime as dt
from live_data import LiveData
import logging
import threading
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future
from abc import ABC
from dataclasses import dataclass

# Get module logger
LOGGER = logging.getLogger(__name__)

# Maximal number of asynchronous tasks that can be handled simultaneously
MAX_TASK_WORKERS = 4

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

class TeamBridgeModel:
    """
    The model holds a thread pool executor and can be used to perform various I/O bound tasks, such as 
    clocking in/out an employee, performing a balance query, and so on. The model can be polled to retrieve 
    task results via the defined message containers.
    Note that this class is not thread safe, meaning that a single thread shall post tasks and read results.
    """

    def __init__(self, time_tracker_provider: Callable[[dt.date, str], ITodayTimeTracker]):
        """
        Create the model.

        Args:
            time_tracker_provider: `Callable[[dt.date, str], ITodayTimeTracker]` the time tracker provider
                as a callable object
        """
        # Save the provider method and create a lock for concurrent access
        self._provider = time_tracker_provider
        self._lock = threading.Lock()
        # Create the threads pool
        self._pool = ThreadPoolExecutor(max_workers=MAX_TASK_WORKERS, thread_name_prefix="Task-")
        # Create the tasks dictionary
        self._pending_tasks: dict[int, Future] = {}
        # Task handle counter
        self._task_handle = -1

    def start_clock_action_task(self, id: str, datetime: dt.datetime, action: ClockAction=None) -> int:
        """
        Start a clock action task for the employee with given identifier.
        It will post an EmployeeEvent on success and a ModelError on failure.  
        The action (clock in or out) can be specified or left None. In this case, 
        the task automatically clocks in an employee who's clocked out and clocks
        out an employee who's clocked in at given datetime.

        Args:
            id: `str` employee's identifier
            datetime: `datetime` time and date for the clock action
            action: `action` clock action to register or None to leave the task choose
        Returns:
            int: task handle
        """
        # Increment tasks counter
        self._task_handle += 1
        # Submit the task to the executor and save the future object
        self._pending_tasks[self._task_handle] = self._pool.submit(self.__clock_action_task, id, datetime, action)
        # Return the task handle
        return self._task_handle

    def start_consultation_task(self, id: str, datetime: dt.datetime) -> int:
        """
        Start a consultation task for the employee with given identifier at given date.
        It will post an EmployeeData on success and a ModelError on failure.

        Args:
            id: `str` employee's identifier
            datetime: `datetime` consultation date
        Returns:
            int: task handle
        """
        # Increment tasks counter
        self._task_handle += 1
        # Submit the task to the executor and save the future object
        self._pending_tasks[self._task_handle] = self._pool.submit(self.__consultation_task, id, datetime)
        # Return the task handle
        return self._task_handle

    def available(self, handle: int) -> bool:
        """
        Check if the task identified by given handle has finished.

        Returns:
            bool: True if the task result is available 
        """
        return (handle in self._pending_tasks and self._pending_tasks[handle].done())

    def get_result(self, handle: int) -> IModelMessage:
        """
        Get task result. 

        Args:
            handle: `int` task handle
        Returns:
            IModelMessage: task result or None if unavailable
        """
        # Check that the task is available
        if not self.available(handle):
            return None
        
        # Pop the future object from the dictionary
        future = self._pending_tasks.pop(handle)
        
        try:
            # Try to read the task result
            message = future.result()
            # A task must return a valid message
            if message is None:
                raise RuntimeError("The task didn't return a message.")
            # Return the task message
            return message
        except:
            # Log the error and return None 
            LOGGER.error("An asynchronous task didn't finished properly.", exc_info=True)
            return None

    def close(self) -> None:
        """
        Close the model. Can take some time if tasks are currently running.
        """
        # Shutdown the thread pool executor, wait for the running tasks to finish and
        # cancel pending ones.
        self._pool.shutdown(wait=True, cancel_futures=True)

    def __clock_action_task(self, id: str, 
                            datetime: dt.datetime, 
                            action: ClockAction) -> IModelMessage:
        """
        Clock in/out the employee at given datetime.
        """
        # Employee and result message are initially None
        employee = None
        message = None
        try:
            # Open the employee time tracker, acquire the lock since other tasks might be 
            # using the provider concurrently.
            with self._lock:
                employee = self._provider(datetime.date(), id)

            # Get employee name and firstname
            name = employee.get_name()
            firstname = employee.get_firstname()

            # Log that time tracker is open
            LOGGER.info(f"Opened time tracker for employee '{firstname} {name}' with id '{id}'.")

            # If no action is specified, clock out if clocked in and clock in if clocked out.
            if action is None:
                action = ClockAction.CLOCK_OUT if employee.is_clocked_in_today() else ClockAction.CLOCK_IN

            # Create and register the clock event
            clock_evt = ClockEvent(time=datetime.time(), action=action)
            employee.register_clock(clock_evt)
            # Commit changes
            employee.commit()
            # Close the time tracker
            # If this operation fails the data might not be correctly saved
            employee.close()
            # Nullify to prevent closing it again
            employee = None

            LOGGER.info(f"{action} saved for employee ['{firstname} {name}' with id '{id}'].")

            # Everything went fine
            # Create the employee event
            message = EmployeeEvent(name=name, 
                                    firstname=firstname, 
                                    id=id, 
                                    clock_evt=clock_evt)

        # Catch the exceptions that may occur during the process and create the ModelError message
        except Exception as e:
            message = ModelError(error_code=0, message=str(e))
            LOGGER.error(f"Error occurred operating time tracker of employee '{id}'.", exc_info=True)
        finally:
            # Always close the time tracker once operations are finished
            try:
                if employee:
                    employee.close()
            except:
                LOGGER.error(f"Error occurred closing time tracker of employee '{id}'.", exc_info=True)
            
        # Return the resulting message
        return message

    def __consultation_task(self, id: str, datetime: dt.datetime) -> IModelMessage:
        """
        Consultation of employee's information.
        """        
        # Employee and result message are initially None
        employee = None
        message = None
        try:
            # Open the employee time tracker, acquire the lock since other tasks might be 
            # using the provider concurrently.
            with self._lock:
                employee = self._provider(datetime.date(), id)

            # Get employee name and firstname
            name = employee.get_name()
            firstname = employee.get_firstname()

            # Log that time tracker is open
            LOGGER.info(f"Opened time tracker for employee '{firstname} {name}' with id '{id}'.")

            # If the time tracker is not readable, evaluate it
            if not employee.is_readable():
                employee.evaluate()
            
            # Read methods are available, build an EmployeeData container
            message = EmployeeData(
                name=name, firstname=firstname, id=id,
                daily_worked_time=employee.get_daily_worked_time(),
                daily_balance=employee.get_daily_balance(),
                daily_scheduled_time=employee.get_daily_schedule(),
                monthly_balance=employee.get_monthly_balance()
            )

            # Close and nullify the time tracker
            employee.close()
            employee = None

        # Catch the exceptions that may occur during the process and create the ModelError message
        except Exception as e:
            message = ModelError(error_code=0, message=str(e))
            LOGGER.error(f"Error occurred operating time tracker of employee '{id}'.", exc_info=True)
        finally:
            # Always close the time tracker once operations are finished
            try:
                if employee:
                    employee.close()
            except:
                LOGGER.error(f"Error occurred closing time tracker of employee '{id}'.", exc_info=True)
            
        # Return the resulting message
        return message
