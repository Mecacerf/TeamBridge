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

# Get module logger
LOGGER = logging.getLogger(__name__)

# Maximal number of asynchronous tasks that can be handled simultaneously
MAX_TASK_WORKERS = 4

class ModelMessage:
    """
    A generic asynchronous message sent by the model to upper layers.
    """
    def __init__(self):
        pass

class EmployeeEvent(ModelMessage):
    """
    Describes an event related to an employee.
    """

    def __init__(self, name: str, firstname: str, id: str, clock_evt: ClockEvent):
        """
        Create an employee event.

        Args:
            name: `str` employee's name
            firstname: `str` employee's firstname
            id: `str` employee's id
            clock_evt: `ClockEvent` related clock event
        """
        # Save event parameters
        self.name = name
        self.firstname = firstname
        self.id = id
        self.clock_evt = clock_evt

    def __repr__(self):
        return f"{self.__class__.__name__}[name={self.name}, firstname={self.firstname}, id={self.id}, evt={self.clock_evt}]"

class EmployeeData(ModelMessage):
    """
    Container of different information about an employee.
    """

    def __init__(self, name: str, 
                 firstname: str, 
                 id: str, 
                 daily_worked_time: dt.timedelta, 
                 daily_balance: dt.timedelta,
                 daily_scheduled_time: dt.timedelta, 
                 monthly_balance: dt.timedelta):
        """
        Create an employee's data container.

        Args:
            name: `str` employee's name
            firstname: `str` employee's firstname
            id: `str` employee's id
            daily_worked_time: `timedelta` employee's daily worked time 
            daily_balance: `timedelta` employee's daily balance
            daily_scheduled_time: `timedelta` employee's daily scheduled time
            monthly_balance: `timedelta` employee's monthly balance
        """
        # Save parameters
        self.name = name
        self.firstname = firstname
        self.id = id
        self.daily_worked_time = daily_worked_time
        self.daily_balance = daily_balance
        self.daily_scheduled_time = daily_scheduled_time
        self.monthly_balance = monthly_balance

    def __repr__(self):
        return (f"{self.__class__.__name__}[name={self.name}, firstname={self.firstname}, id={self.id}, "
        f"daily_worked_time={self.daily_worked_time}, daily_balance={self.daily_balance}, "
        f"daily_scheduled_time={self.daily_scheduled_time}, monthly_balance={self.monthly_balance}]")

class ModelError(ModelMessage):
    """
    Error message container.
    """

    class ErrorType(Enum):
        """
        Error types enumeration.
        """
        # Generic error, refer to the message
        GENERIC_ERROR = 0
        # The scanning device (likely a webcam) ran into error
        SCANNING_DEVICE_ERROR = 1
        # The employee wasn't found in the database
        EMPLOYEE_NOT_FOUND = 2

    def __init__(self, type: ErrorType, msg: str=None):
        """
        Create a model error container.

        Args:
            type: `ErrorType` error type
            msg: `str` optional error message
        """
        self.type = type
        self.message = msg

    def __repr__(self):
        return f"{self.__class__.__name__}[type={self.type}, message={self.message}]"

class TeamBridgeModel:
    """
    The model starts asynchronous tasks and sends responses through the message bus.
    """

    def __init__(self, time_tracker_provider: Callable[[dt.date, str], ITodayTimeTracker]):
        """
        Create a time tracker model able to handle asynchronous tasks.

        Args:
            time_tracker_provider: `Callable[[dt.date, str], ITodayTimeTracker]` the time tracker provider
                as a callable object
        """
        # Save the provider method and create a lock for concurrent access
        self._provider = time_tracker_provider
        self._lock = threading.Lock()
        # Create the threads pool
        self._pool = ThreadPoolExecutor(max_workers=MAX_TASK_WORKERS, thread_name_prefix="Task-")
        # Create the list of future objects
        self._pending_tasks: list[Future] = []
        # Create the messages bus used to send responses
        self._bus = LiveData[ModelMessage](None, bus_mode=True)

    def start_clock_action_task(self, id: str, datetime: dt.datetime, action: ClockAction=None) -> None:
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
        """
        # Submit the task to the executor and save the future object
        self._pending_tasks.append(self._pool.submit(self.__clock_action_task, id, datetime, action))

    def start_consultation_task(self, id: str, datetime: dt.datetime) -> None:
        """
        Start a consultation task for the employee with given identifier at given date.
        It will post an EmployeeData on success and a ModelError on failure.

        Args:
            id: `str` employee's identifier
            datetime: `datetime` consultation date
        """
        # Submit the task to the executor and save the future object
        self._pending_tasks.append(self._pool.submit(self.__consultation_task, id, datetime))

    def run(self):
        """
        The run method must be called regularly to poll the tasks list and post 
        pending messages on the bus.
        """
        # Iterate the future objects and check if a task is completed
        for future in self._pending_tasks:
            if future.done():
                try:
                    # Try to read the task result
                    message = future.result()
                    # The message cannot be None
                    if message is None:
                        raise RuntimeError("The task didn't return a message.")
                    # Send the result on the messages bus
                    self._bus.set_value(message)
                except:
                    LOGGER.error("An asynchronous task didn't finished properly.", exc_info=True)
        # Flush finished tasks from the list
        self._pending_tasks = [future for future in self._pending_tasks if not future.done()]

    def get_message_bus(self) -> LiveData[ModelMessage]:
        """
        Returns:
            LiveData[ModelMessage]: the message bus on which tasks results are posted
        """
        return self._bus

    def close(self) -> None:
        """
        Close the model. Can take some time if tasks are currently running.
        """
        # Shutdown the thread pool executor, wait for the running tasks to finish and
        # cancel pending ones.
        self._pool.shutdown(wait=True, cancel_futures=True)

    def __clock_action_task(self, id: str, datetime: dt.datetime, action: ClockAction) -> ModelMessage:
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
            message = EmployeeEvent(name=name, firstname=firstname, id=id, clock_evt=clock_evt)

        # Catch the exceptions that may occur during the process and create the ModelError message
        except Exception as e:
            message = ModelError(type=ModelError.ErrorType.GENERIC_ERROR, msg=str(e))
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

    def __consultation_task(self, id: str, datetime: dt.datetime) -> ModelMessage:
        """
        Consultation of employee's data.
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
            message = ModelError(type=ModelError.ErrorType.GENERIC_ERROR, msg=str(e))
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
