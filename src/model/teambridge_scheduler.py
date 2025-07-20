#!/usr/bin/env python3
"""
File: teambridge_scheduler.py
Author: Bastian Cerf
Date: 02/03/2025
Description:
    Provides an asynchronous way to manipulate employee time trackers.
    The scheduler allows to execute different I/O bound tasks and get
    their result when they are finished.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, Future
import datetime as dt
import time

# Internal imports
from .data import *
from core.time_tracker import *
from core.time_tracker_factory import TimeTrackerFactory
from core.attendance.simple_attendance_validator import SimpleAttendanceValidator

logger = logging.getLogger(__name__)

# Maximal number of asynchronous tasks that can be handled simultaneously by
# the scheduler
MAX_TASK_WORKERS = 4


class TeamBridgeScheduler:
    """
    The scheduler holds a thread pool executor and can be used to perform
    various I/O bound tasks, such as clocking in/out an employee,
    performing a balance query, and so on. The model can be polled to
    retrieve task results via the defined message containers. Note that
    this class is not thread safe, meaning that a single thread must post
    tasks and read results. Tasks are however executed in parallel using
    the thread pool executor.
    """

    def __init__(self, tracker_factory: TimeTrackerFactory):
        """
        Create the tasks scheduler.

        Args:
            tracker_factory (TimeTrackerFactory): The factory to use to
                create the time trackers.
        """
        self._factory = tracker_factory
        self._factory_lock = threading.Lock()

        self._pool = ThreadPoolExecutor(
            max_workers=MAX_TASK_WORKERS, thread_name_prefix="Task-"
        )

        self._pending_tasks: dict[int, Future[IModelMessage]] = {}
        self._task_handle = -1  # Attribute a unique handle per task

    def start_clock_action_task(
        self,
        employee_id: str,
        datetime: dt.datetime,
        action: Optional[ClockAction] = None,
    ) -> int:
        """
        Start a clock action task for the employee with given identifier.

        It will post an `EmployeeEvent` on success or a `ModelError` on
        failure. The action (clock-in/out) can be specified or left `None`.
        In this case, the task automatically clocks in an employee who's
        clocked out and clocks out an employee who's clocked in, at given
        datetime.

        Args:
            employee_id (str): Employee's identifier.
            datetime (datetime.datetime): Date and time of clock action.
            action (Optional[ClockAction]): Clock action to register or
                `None` to choose automatically.

        Returns:
            int: Task handle.
        """
        # Submit a task on the executor and return its unique handle.
        self._task_handle += 1
        self._pending_tasks[self._task_handle] = self._pool.submit(
            self.__clock_action_task, employee_id, datetime, action
        )
        return self._task_handle

    def start_consultation_task(self, employee_id: str, datetime: dt.datetime) -> int:
        """
        Start a consultation task for the employee with given identifier.

        It will post an `EmployeeData` on success or a `ModelError` on
        failure. The employee's data is analyzed for the given date and
        time.

        Args:
            employee_id (str): Employee's identifier.
            datetime (datetime.datetime): Analysis date and time.

        Returns:
            int: Task handle.
        """
        # Submit a task on the executor and return its unique handle.
        self._task_handle += 1
        self._pending_tasks[self._task_handle] = self._pool.submit(
            self.__consultation_task, employee_id, datetime
        )
        return self._task_handle

    def start_attendance_list_task(self, datetime: dt.datetime) -> int:
        """
        Start an attendance list query task for the given date and time.

        The task polls all registered employees and check if they are
        clocked in on given date and time.

        Args:
            datetime (datetime.datetime): Date and time to query employees
                who are clocked in.

        Returns:
            int: Task handle.
        """
        # Submit a task on the executor and return its unique handle.
        self._task_handle += 1
        self._pending_tasks[self._task_handle] = self._pool.submit(
            self.__attendance_list_task, datetime
        )
        return self._task_handle

    def available(self, handle: int) -> bool:
        """
        Check if the task identified by the given handle has finished.

        `False` is returned wether the task is pending or doesn't exist.

        Returns:
            bool: `True` if the task result is available, `False` otherwise.
        """
        return handle in self._pending_tasks and self._pending_tasks[handle].done()

    def get_result(self, handle: int) -> Optional[IModelMessage]:
        """
        Get a task result.

        The result may be `None` if the task didn't finished properly
        and raised an exception.

        Args:
            handle (int): Task handle.

        Returns:
            Optional[IModelMessage]: Task result or `None` if unavailable.
        """
        if not self.available(handle):
            return None

        future = self._pending_tasks.pop(handle)

        try:
            # The task must return a valid message
            # However this line may raise a few exceptions, especially
            # if an exception occurred in the task. In this case the
            # returned message is None.
            return future.result()

        except Exception as e:
            logger.error(
                "An asynchronous task didn't finished properly.", exc_info=True
            )
            return ModelError(0, f"Task raised {e.__class__.__name__}.")

    def drop(self, handle: int):
        """
        Drop a task.

        This can be used when the task owner is finally not interested
        in getting its result. The task is removed, and will never get
        available. It is safe to call this method with any handle.
        """
        if handle in self._pending_tasks:
            self._pending_tasks.pop(handle)

    def close(self) -> None:
        """
        Close the model. Can take some time if tasks are currently running.
        """
        # Shutdown the thread pool executor, wait for the running tasks to
        # finish and cancel pending ones.
        self._pool.shutdown(wait=True, cancel_futures=True)

    def __enter__(self) -> "TeamBridgeScheduler":
        # Enter function when using a context manager
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        # Close function when using a context manager
        self.close()

    ### Tasks implementation

    def __clock_action_task(
        self, employee_id: str, datetime: dt.datetime, action: Optional[ClockAction]
    ) -> IModelMessage:
        """
        Clock in/out the employee at given datetime.
        """
        try:
            with self._factory.create(employee_id, datetime) as tracker:
                # No action specified: clock-out if clocked in and
                # clock-in if clocked out
                if action is None:
                    action = (
                        ClockAction.CLOCK_OUT
                        if tracker.is_clocked_in(datetime)
                        else ClockAction.CLOCK_IN
                    )

                # Create, register and save the clock event
                clock_evt = ClockEvent(time=datetime.time(), action=action)
                tracker.register_clock(datetime, clock_evt)
                tracker.save()

                logger.info(f"Registered a {clock_evt!s} for {tracker!s}.")

                return EmployeeEvent(
                    name=tracker.name,
                    firstname=tracker.firstname,
                    id=tracker.employee_id,
                    clock_evt=clock_evt,
                )

        except TimeTrackerException as e:
            logger.error(
                f"An exception occurred with employee '{employee_id}'", exc_info=True
            )
            return ModelError(error_code=0, message=str(e))

    def __consultation_task(
        self, employee_id: str, datetime: dt.datetime
    ) -> IModelMessage:
        """
        Consultation of employee's information.
        """
        try:
            with self._factory.create(employee_id, datetime) as tracker:
                validator = SimpleAttendanceValidator()
                status = validator.validate(tracker, datetime)

                logger.info(
                    f"Got status {status}, tracker analyzed ? {tracker.analyzed}"
                )

                if not tracker.analyzed:
                    tracker.analyze(datetime)

                return EmployeeData(
                    name=tracker.name,
                    firstname=tracker.firstname,
                    id=employee_id,
                    daily_worked_time=tracker.read_day_worked_time(datetime),
                    daily_balance=tracker.read_day_balance(datetime),
                    daily_scheduled_time=tracker.read_day_schedule(datetime),
                    monthly_balance=tracker.read_month_balance(datetime),
                )

        except TimeTrackerException as e:
            logger.error(
                f"An exception occurred with employee '{employee_id}'", exc_info=True
            )
            return ModelError(error_code=0, message=str(e))

    def __attendance_list_task(self, datetime: dt.datetime) -> IModelMessage:
        """
        Fetch employees attendance list for given date and time.
        """
        start_ts = time.time()

        def fetch(id: str) -> tuple[EmployeeInfo, Optional[bool]]:
            """
            Check if the employee with given identifier is currently
            clocked in.

            Returns:
                EmployeeInfo: A dataclass with the name, firstname and
                    employee ID. If an opening error occurs early, only
                    the ID may be available.
                Optional[bool]: `True` if clock-in, `False` if clocked-out
                    and `None` if an error occurred.
            """
            name = ""
            firstname = ""
            clocked_in = None

            try:
                with self._factory.create(id, datetime, readonly=True) as tracker:
                    name = tracker.name
                    firstname = tracker.firstname
                    clocked_in = tracker.is_clocked_in(datetime)
            except TimeTrackerException:
                pass

            # Name and firstname may be empty if clocked_in is None
            return EmployeeInfo(name, firstname, id), clocked_in

        # Fetch all registered employees for the given year
        result: list[tuple[EmployeeInfo, Optional[bool]]] = []
        for id in self._factory.list_employee_ids(datetime):
            result.append(fetch(id))

        return AttendanceList(
            present=[info for info, clocked_in in result if clocked_in is True],
            absent=[info for info, clocked_in in result if clocked_in is False],
            unknown=[info for info, clocked_in in result if clocked_in is None],
            fetch_time=time.time() - start_ts,
        )
