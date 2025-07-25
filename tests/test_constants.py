#!/usr/bin/env python3
"""
File: test_constants.py
Author: Bastian Cerf
Date: 18/05/2025
Description:
    Declaration of general test constants.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

from pathlib import Path

# Test employee identifiers
TEST_EMPLOYEE_ID = "777"
TEST_EMPLOYEE_NAME = "Cerf"
TEST_EMPLOYEE_FIRSTNAME = "Meca"
# Spreadsheet file under test
TEST_SPREADSHEET_FILE = f"{TEST_EMPLOYEE_ID}-unit-test.xlsx"

# Error employee identifier
TEST_ERROR_EMPLOYEE_ID = "222"
TEST_ERROR_EMPLOYEE_YEAR = 2025

# Wrong version employee identifier
TEST_WRONG_VERSION_ID = "333"
TEST_WRONG_VERSION_YEAR = 2025

# Tests assets source folder
TEST_ASSETS_SRC_FOLDER = "tests/assets/"
# Tests assets destination folder
TEST_ASSETS_DST_FOLDER = ".test-cache/assets/"

# Test sheets repository folder
TEST_REPOSITORY_ROOT = str(Path(TEST_ASSETS_DST_FOLDER) / "repository")

# Errors identifiers and descriptions table
TEST_ERRORS_TABLE = {
    0: "",
    10: "temps de travail sans pause dépassé",
    20: "horaire bloc non respecté",
    30: "passage à minuit",
    100: "incohérence chronologie",
    110: "timbrage manquant",
    120: "saisie incorrecte",
}
