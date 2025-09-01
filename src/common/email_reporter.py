#!/usr/bin/env python3
"""
File: email_reporter.py
Author: Bastian Cerf
Date: 12/08/2025
Description:
    Report application events by emails.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import logging
import smtplib
from email.message import EmailMessage
import zipfile
import os
import io
import textwrap
from typing import Optional
from threading import Thread
from queue import Queue, ShutDown, Empty

# Internal libraries
from common.reporter import ReportingService, Report, EmployeeReport

logger = logging.getLogger(__name__)


class EmailBuilder:
    """
    Generate ready to send email messages from program reports.
    """

    def build(self, report: Report, sender: str, recipient: str) -> EmailMessage:
        """
        Build an email message from the given report.

        Args:
            report (Report): Input report.
            sender (str): Sender email address.
            recipient (str): Recipient email address.

        Returns:
            EmailMessage: Formatted message.
        """
        email = EmailMessage()
        email["Subject"] = f"[{report.severity.name}] {report.title}"
        email["From"] = sender
        email["To"] = recipient

        # Add plain text body
        self._plain_content(report, email)

        # Adds the attachments if any
        if report.attachments:
            self._attach_files(report.attachments, email)

        return email

    def _plain_content(self, report: Report, email: EmailMessage):
        """
        Set the message content with a plain text format, that is
        supported by all email clients.
        """
        # Body template
        body = textwrap.dedent(
            f"""\
                ────────── Summary ──────────
                Severity: {report.severity.name}
                Title: {report.title}
                Created: {report.created_at:%d.%m.%Y at %H:%M:%S}
                Device ID: {report.device_id}

            """
        )

        if report.content:
            body += textwrap.dedent(
                """\
                    ────────── Details ──────────
                """
            )
            body += report.content
            body += "\n\n"

        # Add employee context if available
        if isinstance(report, EmployeeReport):
            body += textwrap.dedent(
                f"""\
                    ────────── Employee ──────────
                    Employee ID: {report.employee_id}
                    Name: {report.firstname or '?'} {report.name or '?'}
                    {f"Error ID: {report.error_id}\n" if report.error_id else ""} 
                """
            )

        # Add attachments list if present
        if report.attachments:
            body += "────────── Attachments ──────────\n"
            for f in report.attachments:
                body += f"- {f}\n"

        # Footer
        body += textwrap.dedent(
            """\
                
                ────────────────────────────────────────
                This message was generated automatically.
            """
        )

        email.set_content(body)
        return email

    def _attach_files(self, files: list[str], email: EmailMessage):
        """
        Add the listed files as attachments to the email. If there are
        more than one file, they are bundled in a unique zip file.

        Note this method is not designed to support large files.
        """
        if len(files) > 1:
            # Create in-memory zip
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file in files:
                    zipf.write(file, arcname=os.path.basename(file))
            buffer.seek(0)

            email.add_attachment(
                buffer.read(),
                maintype="application",
                subtype="zip",
                filename="attachments.zip",
            )

        else:
            # Single file, just attach it
            filename = files[0]
            subtype = filename.split(".")[-1]
            with open(filename, "rb") as f:
                email.add_attachment(
                    f.read(),
                    maintype="application",
                    subtype=subtype,
                    filename=os.path.basename(filename),
                )


class EmailReporter(ReportingService):
    """
    Implementation of the `ReportingService` interface that sends the
    reports by email.
    """

    CHECK_AVAILABILITY_TIMEOUT = 15.0

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        sender: str,
        password: str,
        recipient: str,
        builder: Optional[EmailBuilder] = None,
    ):
        """
        Create an email reporter. Optionally specify a custom builder.

        Args:
            smtp_server (str): SMTP server to use for email sending.
            smtp_port (int): SMTP server port.
            sender (str): Sender email address.
            password (str): Sender password.
            recipient (str): Recipient email address.
            builder (Optional[EmailBuilder]): Optionally specify a
                custom email builder.
        """
        super().__init__()

        self._builder = EmailBuilder()  # Use default builder
        if builder:
            self._builder = builder

        # Gather email parameters
        self._sender = sender
        self._password = password
        self._recipient = recipient
        self._smtp_server = smtp_server
        self._smtp_port = smtp_port

        # Setup the report sending queue
        self._send_queue = Queue()

        # Start the service task
        self._task = Thread(
            target=self.__reporter_task, name="EmailReporterTask", daemon=False
        )
        self._task.start()

    def __reporter_task(self):
        """
        Internal service task.
        """
        try:
            # Initial service availability check
            self.__check_availability()

            while True:
                try:
                    # Block until a report is available
                    report = self._send_queue.get(
                        block=True, timeout=self.CHECK_AVAILABILITY_TIMEOUT
                    )
                    self.__process_report(report)

                except Empty:
                    if self._available_flag.is_set():
                        continue
                    # Re-check service availability
                    self.__check_availability()

        except ShutDown:
            logger.info("Email reporting service task finished.")
        except Exception:
            logger.exception(f"Email reporting task finished with exception.")

        self._available_flag.clear()  # Obviously unavailable after task stop

    def __check_availability(self):
        """
        Check if the SMTP server is reachable and set the availability
        flag accordingly.
        """
        try:
            with self._login():
                self._available_flag.set()
                logger.info("SMTP server is now available.")
        except OSError:
            pass

    def __process_report(self, report: Report):
        """
        Build an email message from the report and try to send it.
        """
        email = self._builder.build(report, self._sender, self._recipient)

        try:
            # Sending the email
            with self._login() as server:
                server.send_message(email)

            self._available_flag.set()
            logger.info(f"Successfully sent email report {report!s}.")

        except OSError as ex:
            self._available_flag.clear()
            logger.error(f"An exception occurred sending report {report!s}: {ex}")

    def _login(self) -> smtplib.SMTP:
        """
        Start a TLS connection to the SMTP server and tries to login with
        configured identifiers.

        Returns:
            smtplib.SMTP: SMTP connection instance.

        Raises:
            SMTPHeloError
            SMTPAuthenticationError
            SMTPNotSupportedError
            SMTPException
        """
        server = smtplib.SMTP(self._smtp_server, self._smtp_port)
        server.starttls()  # Secured connection with TLS
        server.login(self._sender, self._password)
        return server

    def close(self):
        super().close()
        # Shutdown the queue, blocking put() calls and raising ShutDown
        # when empty. Join the thread (wait until all reports are sent).
        self._send_queue.shutdown(immediate=False)
        self._task.join(timeout=10.0)  # Safe timeout

    def _internal_send(self, report: Report):
        try:
            # Put pending report in the send queue
            self._send_queue.put(report)
        except ShutDown:
            logger.error(f"Cannot send report {report!s}, the service has been closed.")
