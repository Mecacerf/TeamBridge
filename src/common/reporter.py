#!/usr/bin/env python3
"""
File: reporter.py
Author: Bastian Cerf
Date: 25/08/2025
Description:
    Define a generic interface to report events to any recipient.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
from abc import ABC, abstractmethod
from enum import IntEnum
from dataclasses import dataclass, field
import datetime as dt
from typing import Optional, Type
from types import TracebackType
import os

# Internal libraries
from threading import Event
from bootstrap import LOGGING_FILE_NAME
from local_config import LocalConfig

config = LocalConfig()


class ReportSeverity(IntEnum):
    """
    Severity of the report.
    """

    INFO = 0
    WARNING = 1
    ERROR = 2
    CRITICAL = 3

    @classmethod
    def parse(cls, value: str) -> "ReportSeverity":
        """
        Parse a string literal to an enum member, if possible.

        Raises:
            ValueError: Given string doesn't match any member.
        """
        try:
            return next(
                (member for member in cls if member.name.lower() == value.lower())
            )
        except StopIteration:
            raise ValueError(f"Unknown severity '{value}'.")


@dataclass
class Report:
    """
    A report holding a severity, a title and message content.
    Attachments can optionally be added to the report using the provided
    convenience methods.
    """

    severity: ReportSeverity
    title: str
    content: Optional[str]
    attachments: list[str] = field(default_factory=list, init=False)
    created_at: dt.datetime = field(init=False)
    device_id: str = field(init=False)

    def __post_init__(self):
        self.created_at = dt.datetime.now()
        self.device_id = config.section("general")["device"]

    def __str__(self) -> str:
        return f"'[{self.severity.name}] {self.title}'"

    def attach_logs(self, root: Optional[str] = None) -> "Report":
        """
        Attach the program log files to the report.
        """
        if not root:
            root = "."

        self.attachments.extend(
            [file for file in os.listdir(root) if LOGGING_FILE_NAME in file]
        )
        return self

    def attach_files(self, files: list[str]) -> "Report":
        """
        Attach files to the report.

        Args:
            files (list[str]): List of file paths to attach.
        """
        self.attachments.extend(files)
        return self


@dataclass
class EmployeeReport(Report):
    """
    A report targetting a specific employee. The name and firstname can
    be missing, typically when reporting an error where this information
    is unknown. If this report has been created after an employee error
    occurred, the error ID can be specified.
    """

    employee_id: str
    name: Optional[str] = None
    firstname: Optional[str] = None
    error_id: Optional[int] = None


class ReportingService(ABC):
    """
    A generic reporting service interface.
    """

    def __init__(self) -> None:
        """
        Initialize a reporting service.
        """
        self._available_flag = Event()

    @property
    def available(self) -> bool:
        """
        Availability status of the service. An unavailable service can
        still be used, the behavior is implementation dependant though.
        It may wakeup a sleeping service or just fail.

        Returns:
            bool: Service availability status.
        """
        return self._available_flag.is_set()

    def check_rules(self, report: Report) -> bool:
        """
        Check whether this report can be sent according to configured
        reporting rules.

        Args:
            report (Report): Report to check.

        Returns:
            bool: `True` if the report fulfills the rules.
        """
        rules = config.section("report.general")

        # Check the minimal report severity
        min_severity = rules["report_severity"]
        min_severity = ReportSeverity.parse(min_severity)

        if report.severity < min_severity:
            return False

        # Check the employee error ID
        if isinstance(report, EmployeeReport):
            min_error_level = rules["employee_error_level"]
            if report.error_id is not None and report.error_id < min_error_level:
                return False

        return True

    def send_report(self, report: Report, bypass: bool = False):
        """
        Submit a report to be sent by the service.

        Args:
            report (Report): Report to send.
            bypass (bool): `True` to ignore the rules check. By default,
                `check_rules()` is called to verify if the report can
                be sent.
        """
        if bypass or self.check_rules(report):
            self._internal_send(report)

    @abstractmethod
    def _internal_send(self, report: Report):
        """
        Internal implementation of the `send_report()` method.
        """
        pass

    def close(self):
        """
        Terminate the service.
        """
        self._available_flag.clear()

    ### Context manager ###

    def __enter__(self) -> "ReportingService":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        try:
            self.close()
        except Exception as close_ex:
            if exc_val:
                # If there was an exception in the context block,
                # chain the close error to it
                raise exc_val from close_ex
            # No prior exception: just raise the close failure
            raise close_ex
        return False  # Propagate any exception from the context block
