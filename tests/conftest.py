#!/usr/bin/env python3
"""
File: conftest.py
Author: Bastian Cerf
Date: 13/04/2025
Description:
    Declaration of shared fixtures across unit test modules.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import pytest
from pytest import MonkeyPatch
import pathlib
import shutil
import os
from typing import Any, Generator

# Internal libraries
from tests.test_constants import *
from core.time_tracker_factory import TimeTrackerFactory
from core.spreadsheets.sheet_time_tracker_factory import SheetTimeTrackerFactory
from model.teambridge_scheduler import TeamBridgeScheduler
from viewmodel.teambridge_viewmodel import TeamBridgeViewModel
from platform_io.barcode_scanner import BarcodeScanner

########################################################################
#                          Assets arrangement                          #
########################################################################


@pytest.fixture
def arrange_assets():
    """
    This pytest fixture prepares the test assets. It removes any existing 
    old test asset folders and creates a new one.
    """
    assets_src = pathlib.Path(TEST_ASSETS_SRC_FOLDER)
    assets_dst = pathlib.Path(TEST_ASSETS_DST_FOLDER)

    if not assets_src.exists():
        raise FileNotFoundError(
            f"Test assets folder not found at '{assets_src.resolve()}'."
        )

    if assets_dst.exists():

        def remove_readonly(func, path, exc_info): # type: ignore
            """
            Changes the file attribute and retries deletion if permission is denied.
            """
            os.chmod(path, 0o777)  # type: ignore # Grant full permissions
            func(path)  # Retry the function

        # Remove old test assets folder
        shutil.rmtree(assets_dst, onexc=remove_readonly) # type: ignore

    shutil.copytree(assets_src, assets_dst)


@pytest.fixture
def factory(arrange_assets: None) -> TimeTrackerFactory:
    """
    Get a `TimeTrackerFactory` instance for the test.
    """
    return SheetTimeTrackerFactory(repository_path=TEST_REPOSITORY_ROOT)

@pytest.fixture
def scheduler(factory: TimeTrackerFactory) -> Generator[TeamBridgeScheduler, None, None]:
    """
    Get a configured model scheduler.
    """
    with TeamBridgeScheduler(tracker_factory=factory) as scheduler:
        yield scheduler

@pytest.fixture
def viewmodel(scheduler: TeamBridgeScheduler, monkeypatch: MonkeyPatch) -> TeamBridgeViewModel:
    """
    Get a configured view model.
    """
    # Create a barcode scanner mock
    scanner = BarcodeScanner()

    def void(**kwargs: dict[Any, Any]): 
        """Mock the scanner close function"""
        pass
    monkeypatch.setattr(scanner, "close", void)

    return TeamBridgeViewModel(model=scheduler,
                               scanner=scanner,
                               cam_idx=0,
                               scan_rate=10,
                               debug_mode=True)
