#!/usr/bin/env python3
"""
File: email_reporter.py
Author: Bastian Cerf
Date: 12/08/2025
Description:
    Report application events by sending emails.

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

# Internal libraries
from common.reporter import Reporter, Report, EmployeeReport
from local_config import LocalConfig
import threading

logger = logging.getLogger(__name__)
config = LocalConfig()


class EmailBuilder:
    """
    Generate ready to send email messages from program reports.
    """

    def build(self, report: Report) -> EmailMessage:
        """
        Build an email message from the given report.

        Args:
            report (Report): Input report.

        Returns:
            EmailMessage: Formatted message.
        """
        email = EmailMessage()
        email["Subject"] = f"[{report.severity.name}] {report.title}"

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
            Timestamp: {report.created_at:%Y-%m-%d %H:%M:%S}
            Device ID: {report.device_id}

            ────────── Details ──────────
            {report.content.strip()}

            """
        )

        # Add employee context if available
        if isinstance(report, EmployeeReport):
            body += textwrap.dedent(
                f"""\
                ────────── Employee ──────────
                Employee ID: {report.employee_id}
                Name: {report.firstname or ''} {report.name or ''}

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

            ─────────────────────────────────────────
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
                    if os.path.exists(file):
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


class EmailSyncReporter(Reporter):
    """
    Implementation of the `Reporter` abstract class that sends the
    reports by email. This is a synchronous version, meaning the when
    the `report()` method returns the email has been sent.
    """

    def __init__(self, builder: Optional[EmailBuilder] = None):
        """
        Create an email reporter. Optionally specify a custom builder.

        Args:
            builder (Optional[EmailBuilder]): Optionally specify a
                custom email builder.
        """
        self._builder = EmailBuilder()  # Use default builder
        if builder:
            self._builder = builder

        # Gather email parameters
        email_conf = config.section("report.email")
        self._sender = email_conf["sender_address"]
        self._password = email_conf["sender_password"]
        self._recipient = email_conf["recipient_address"]
        self._smtp_server = email_conf["smtp_server"]
        self._smtp_port = email_conf["smtp_port"]

    def report(self, report: Report):
        """
        Build an email report and send it.

        Args:
            report (Report): Report to send.

        Raises:
            Exception: Any exception that may occur during message
                building or sending.
        """
        email = self._builder.build(report)
        email["From"] = self._sender
        email["To"] = self._recipient

        # Sending the email
        with smtplib.SMTP(self._smtp_server, self._smtp_port) as server:
            server.starttls()  # Secure the connection
            server.login(self._sender, self._password)
            server.send_message(email)

        logger.debug(f"Successfully sent email for {report}.")


class EmailAsyncReporter(EmailSyncReporter):
    """
    Same as `EmailSyncReporter` but the `report()` method is asynchronous.
    When called, an internal thread is started to carry the building and
    sending process. If an error occurs, it is logged but there is no
    way for the task that posted the report to know it.
    """

    def report(self, report: Report):
        """
        Build and send a report in an asynchronous task.
        """
        threading.Thread(
            target=self._async_report,
            args=(report,),
            name="AsyncEmailTask",
            daemon=True,
        ).start()

    def _async_report(self, report: Report):
        try:
            super().report(report)
        except Exception as ex:
            logger.error(f"An exception occurred sending an email report: {ex}.")
            logger.error(f"Unsent report content: {report}.")
