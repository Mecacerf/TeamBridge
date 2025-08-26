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
from enum import IntEnum, auto
from dataclasses import dataclass, field
import datetime as dt
from typing import Optional
import os

# Internal libraries
from bootstrap import LOG_FILE_NAME
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
    convenienvce methods.
    """

    severity: ReportSeverity
    title: str
    content: str
    attachments: list[str] = field(default_factory=list, init=False)
    created_at: dt.datetime = field(init=False)
    device_id: str = field(init=False)

    def __post_init__(self):
        self.created_at = dt.datetime.now()
        self.device_id = config.section("general")["device"]

    def attach_logs(self) -> "Report":
        """
        Attach the program log files to the report.
        """
        self.attachments.extend(
            [file for file in os.listdir(".") if LOG_FILE_NAME in file]
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
    is unknown.
    """

    employee_id: str
    name: Optional[str] = None
    firstname: Optional[str] = None


class Reporter(ABC):
    """
    Generic reporter class.
    """

    def check_rules(self, report: Report) -> bool:
        """
        Check whether this report can be sent according to configured
        reporting rules.
        """
        # Check the minimal report severity
        min_severity = config.section("report.general")["report_severity"]
        min_severity = ReportSeverity.parse(min_severity)

        return report.severity >= min_severity

    @abstractmethod
    def report(self, report: Report):
        """
        Perform a report.

        Args:
            report (Report): Object holding the pieces of information
                to be reported.
        """
        pass
