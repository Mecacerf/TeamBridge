#!/usr/bin/env python3

# Standard libraries
import pytest
import datetime as dt

# Internal libraries
from common.reporter import (
    ReportSeverity,
    Report,
    EmployeeReport,
    ReportingService,
    config as reporter_config,
)
from bootstrap import LOGGING_FILE_NAME
from local_config import LocalConfig

config = LocalConfig()

########################################################################
#                    Reporting severity enum test                      #
########################################################################


def test_parse_severity():
    assert ReportSeverity.parse("crITicAl") is ReportSeverity.CRITICAL


def test_parse_unknown():
    with pytest.raises(ValueError):
        ReportSeverity.parse("Incorrect")


########################################################################
#                         Report building test                         #
########################################################################


def test_build_simple_report():
    report = Report(ReportSeverity.WARNING, "Test report", "Report content")
    report.attach_files(["example.png", "subprocess.log"])

    assert report.title == "Test report"
    assert report.severity == ReportSeverity.WARNING
    assert report.device_id == config.section("general")["device"]
    assert dt.datetime.now() - report.created_at < dt.timedelta(minutes=1)
    assert report.content == "Report content"
    assert set(["example.png", "subprocess.log"]) == set(report.attachments)
    assert not report.is_sent()


@pytest.fixture
def tmp_log(tmp_path):
    file = tmp_path / LOGGING_FILE_NAME
    file.touch()  # create the empty file
    yield tmp_path


def test_build_report_attach_logs(tmp_log):
    report = Report(ReportSeverity.INFO, "Logs", None)

    report.attach_logs(tmp_log)
    assert LOGGING_FILE_NAME in report.attachments


def test_build_employee_report():
    report = EmployeeReport(
        ReportSeverity.WARNING, "Employee report", None, "666", "Luc", "Arnold", 100
    )

    assert report.employee_id == "666"
    assert report.error_id == 100
    assert report.name == "Luc"
    assert report.firstname == "Arnold"


########################################################################
#                        Reporting service test                        #
########################################################################


class SimpleImpl(ReportingService):
    """Empty reporting service implementation"""

    def _internal_send(self, report: Report):
        pass


def mock_section(_):
    return {
        "report_severity": "error",
        "employee_error_level": 100,
        "device": "test-device",
    }


def test_rules_severity(monkeypatch):
    monkeypatch.setattr(reporter_config, "section", mock_section)

    with SimpleImpl() as reporter:
        report = Report(ReportSeverity.ERROR, "", None)
        assert reporter.check_rules(report)
        report = Report(ReportSeverity.WARNING, "", None)
        assert not reporter.check_rules(report)


def test_rules_error_id(monkeypatch):
    monkeypatch.setattr(reporter_config, "section", mock_section)

    with SimpleImpl() as reporter:
        report = EmployeeReport(ReportSeverity.ERROR, "", None, "666", error_id=100)
        assert reporter.check_rules(report)
        report = EmployeeReport(ReportSeverity.ERROR, "", None, "666", error_id=99)
        assert not reporter.check_rules(report)
