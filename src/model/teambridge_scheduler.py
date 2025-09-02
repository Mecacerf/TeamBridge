#!/usr/bin/env python3
"""
File: teambridge_scheduler.py
Author: Bastian Cerf
Date: 02/03/2025
Description:
    Provides an asynchronous way to manipulate employee time trackers.
    The scheduler allows to execute different tasks and get their result
    once finished.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import logging
from concurrent.futures import ThreadPoolExecutor, Future
import datetime as dt
import time

# Internal imports
from .data import *
from core.time_tracker import *
from core.time_tracker_factory import TimeTrackerFactory
from core.time_tracker_pool import TimeTrackerPool
from core.attendance.attendance_validator import AttendanceErrorStatus
from core.attendance.simple_attendance_validator import SimpleAttendanceValidator
from core.attendance.simple_attendance_validator import ERROR_MIDNIGHT_ROLLOVER_ID
from local_config import LocalConfig

logger = logging.getLogger(__name__)
config = LocalConfig()

# Maximal number of asynchronous tasks that can be handled simultaneously by
# the scheduler
MAX_TASK_WORKERS = 4


class TeamBridgeScheduler:
    """
    The scheduler holds a thread pool executor and can be used to perform
    various tasks, such as clocking in/out an employee, performing a
    balance query, and so on. The model can be polled to retrieve task
    results via the defined message containers. Note that this class is
    not thread safe, meaning that a single thread must post tasks and
    read results. Tasks are however executed in parallel using a thread
    pool executor.
    """

    def __init__(self, tracker_factory: TimeTrackerFactory):
        """
        Create the tasks scheduler.

        Args:
            tracker_factory (TimeTrackerFactory): The factory to use to
                create the time trackers.
        """
        self._factory = tracker_factory
        self._tracker_pool = TimeTrackerPool(tracker_factory)

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
        self._tracker_pool.close()

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

        A midnight rollover is done if:
        - This is the first event of the day and;
        - The datetime is in the morning (typically 00:00 <= now < 4:00) and;
        - The last clock-out is missing the day before and;
        - The time between now and the clock-in of yesterday is less than
            8 hours.

        Actual time values are configured in the local configuration file.
        """

        def check_midnight_rollover(tracker: TimeTrackerAnalyzer) -> bool:
            """Check the midnight rollover conditions."""
            if action is ClockAction.CLOCK_OUT:
                return False

            # Read config values
            rules = config.section("repository.rules")
            morning_clock_out = rules["last_morning_clock_out_time"]
            morning_clock_out = dt.datetime.strptime(morning_clock_out, "%H:%M").time()

            max_work_duration = rules["max_work_duration"]
            hours, minutes = map(int, max_work_duration.split(":"))
            max_work_duration = dt.timedelta(hours=hours, minutes=minutes)

            # Yesterday must be the same year
            yesterday = datetime - dt.timedelta(days=1)
            if yesterday.year != tracker.tracked_year:
                return False

            yesterday_evts = tracker.get_clocks(yesterday)
            if not yesterday_evts:
                return False

            yday_evt = yesterday_evts[-1]
            assert yday_evt
            yday_evt_dt = dt.datetime.combine(yesterday.date(), yday_evt.time)
            evts_delta_t = datetime - yday_evt_dt

            is_first_evt = len(tracker.get_clocks(datetime)) == 0
            is_morning = dt.time(0, 0) <= datetime.time() <= morning_clock_out
            is_in_yesterday = tracker.is_clocked_in(yesterday)
            is_dt_ok = evts_delta_t <= max_work_duration

            return is_first_evt and is_morning and is_in_yesterday and is_dt_ok

        try:
            with self._tracker_pool.acquire(employee_id, datetime) as tracker:
                # Register a midnight rollover if the condition is respected
                if check_midnight_rollover(tracker):
                    # To indicate a rollover, a special clock-out event is
                    # registered yesterday at midnight (24:00) and a clock-in
                    # event is registered today at midnight (00:00).
                    yesterday = datetime - dt.timedelta(days=1)
                    tracker.register_clock(yesterday, ClockEvent.midnight_rollover())
                    tracker.register_clock(
                        datetime,
                        ClockEvent(time=dt.time(0, 0), action=ClockAction.CLOCK_IN),
                    )
                    # A custom error is set to inform the HR
                    tracker.set_attendance_error(datetime, ERROR_MIDNIGHT_ROLLOVER_ID)

                    logger.info(f"Midnight rollover registered for {tracker!s}.")

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
            with self._tracker_pool.acquire(employee_id, datetime) as tracker:
                validator = SimpleAttendanceValidator()
                status = validator.validate(tracker, datetime)

                if status is AttendanceErrorStatus.ERROR:
                    # Cannot read tracker values
                    return EmployeeData(
                        name=tracker.name,
                        firstname=tracker.firstname,
                        id=employee_id,
                        date_errors=validator.date_errors,
                        dominant_error=validator.dominant_error,
                    )

                # The tracker might not be analyzed if the validate method
                # performed some write operations
                if not tracker.analyzed:
                    tracker.analyze(datetime)

                return EmployeeData(
                    name=tracker.name,
                    firstname=tracker.firstname,
                    id=employee_id,
                    date_errors=validator.date_errors,
                    dominant_error=validator.dominant_error,
                    clocked_in=tracker.is_clocked_in(datetime),
                    day_schedule_time=tracker.read_day_schedule(datetime),
                    day_worked_time=tracker.read_day_worked_time(datetime),
                    day_balance=tracker.read_day_balance(datetime),
                    month_expected_day_schedule=tracker.read_month_expected_daily_schedule(
                        datetime
                    ),
                    month_schedule_time=tracker.read_month_schedule(datetime),
                    month_worked_time=tracker.read_month_worked_time(datetime),
                    month_balance=tracker.read_month_balance(datetime),
                    month_to_yday_balance=tracker.read_month_to_yesterday_balance(),
                    month_vacation=tracker.read_month_vacation(datetime),
                    year_vacation=tracker.read_year_vacation(),
                    remaining_vacation=tracker.read_year_remaining_vacation(),
                    ytd_balance=tracker.read_year_to_date_balance(),
                    yty_balance=tracker.read_year_to_yesterday_balance(),
                    min_allowed_balance=tracker.min_allowed_balance,
                    max_allowed_balance=tracker.max_allowed_balance,
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
