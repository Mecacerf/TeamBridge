#!/usr/bin/env python3
"""
File: email_reporter_test.py
Author: Bastian Cerf
Date: 31/08/2025
Description:
    Unit tests for the email reporter module.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import pytest
from typing import cast
import time
from email.message import EmailMessage

# Internal libraries
from common.reporter import ReportSeverity, Report, EmployeeReport
from common.email_reporter import EmailBuilder, EmailReporter
from threading import Event


TEST_SENDER = "sender@test.com"
TEST_RECIPIENT = "recipient@test.com"


########################################################################
#                          Email builder test                          #
########################################################################


def assert_email_contains(email: EmailMessage, value: str | None):
    """Check if given email contains the value somewhere."""
    if email.is_multipart():
        parts = [part.get_content() for part in email.iter_parts()]
    else:
        parts = [email.get_content()]

    if value is not None:
        assert any(value in part for part in parts if isinstance(part, str))


def create_attachments(tmp_path, files: list[str]) -> list[str]:
    """Create stub attachment files in a temporary folder. Returns paths list."""
    attachments = []
    for file in files:
        file = tmp_path / file
        file.touch()
        attachments.append(str(file.resolve()))
    return attachments


def test_build_simple_email(tmp_path):
    """Build a simple email message and check it holds expected information."""
    attachments = create_attachments(tmp_path, ["test.txt", "foobar.log"])

    report = Report(ReportSeverity.WARNING, "Test report", "Test content").attach_files(
        attachments
    )

    email = EmailBuilder().build(report, TEST_SENDER, TEST_RECIPIENT)

    assert_email_contains(email, report.title)
    assert_email_contains(email, report.severity.name)
    assert_email_contains(email, report.device_id)
    assert_email_contains(email, report.created_at.strftime("%H:%M"))
    assert_email_contains(email, report.created_at.strftime("%d.%m.%Y"))
    assert_email_contains(email, report.machine_name)
    assert_email_contains(email, report.machine_os)
    assert_email_contains(email, report.content)
    for attachment in report.attachments:
        assert_email_contains(email, attachment)


def test_build_employee_email(tmp_path):
    """Build an employee report email and check it holds employee information."""
    attachments = create_attachments(tmp_path, ["foobar.log"])

    report = cast(
        EmployeeReport,
        EmployeeReport(
            ReportSeverity.INFO,
            "Employee report",
            None,
            employee_id="666",
            firstname="Jean",
            name="Paul",
            error_id=129,
        ).attach_files(attachments),
    )

    email = EmailBuilder().build(report, TEST_SENDER, TEST_RECIPIENT)

    assert_email_contains(email, report.employee_id)
    assert_email_contains(email, report.firstname)
    assert_email_contains(email, report.name)
    assert_email_contains(email, str(report.error_id))


########################################################################
#                   Email reporting service test                       #
########################################################################


class SMTPServerMock:
    """Reproduce used methods of the SMTP server interface."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def starttls(self):
        pass

    def login(self, user: str, password: str):
        self.user = user
        self.password = password

    def send_message(self, email: EmailMessage):
        self.email = email


@pytest.fixture
def reporter(monkeypatch):
    """Get an EmailReporter service instance that logins with a server mock."""
    with EmailReporter(
        "smtp.server.com",
        557,
        TEST_SENDER,
        "password",
        TEST_RECIPIENT,
        EmailBuilder(),
    ) as reporter:
        monkeypatch.setattr(reporter, "_login", lambda *args: SMTPServerMock())
        yield reporter


def test_send_email_report(monkeypatch, reporter: EmailReporter):
    """Send a report through the service and intercept sent message."""
    builder = EmailBuilder()
    report = Report(ReportSeverity.CRITICAL, "Report title", "Report content")
    prediction = builder.build(report, TEST_SENDER, TEST_RECIPIENT)

    server = SMTPServerMock()

    def login_mock():
        return server

    monkeypatch.setattr(reporter, "_login", login_mock)

    reporter.send_report(report, bypass=True)
    reporter.close()  # Join the service thread

    assert hasattr(server, "email")
    assert str(prediction) == str(server.email)
    assert report.is_sent()


def test_availability_flag_set(monkeypatch, reporter: EmailReporter):
    """Check the service gets available after a report was sent successfully."""
    # Increase check speed
    reporter.CHECK_AVAILABILITY_TIMEOUT = 0.1
    event = Event()

    def login_success():
        event.set()
        return SMTPServerMock()

    monkeypatch.setattr(reporter, "_login", login_success)

    # Send a report to update the flag
    reporter.send_report(
        Report(ReportSeverity.CRITICAL, "Report title", "Report content"), bypass=True
    )

    # Wait enough time to ensure the service updated the flag
    assert event.wait(1.0)
    time.sleep(0.5)
    assert reporter.available


def test_availability_flag_clear(monkeypatch, reporter: EmailReporter):
    """Check the service gets available automatically and gets unavailable
    after a report failed to be sent."""
    # Increase check speed
    reporter.CHECK_AVAILABILITY_TIMEOUT = 0.1
    event = Event()

    timeout = time.time() + 0.5
    while not reporter.available and time.time() < timeout:
        pass
    assert reporter.available

    def login_fails():
        event.set()
        raise OSError("Stub OS error")

    monkeypatch.setattr(reporter, "_login", login_fails)

    # Send a report to update the flag
    reporter.send_report(
        Report(ReportSeverity.CRITICAL, "Report title", "Report content"), bypass=True
    )

    assert event.wait(1.0)
    time.sleep(0.5)
    assert not reporter.available
    event.clear()
