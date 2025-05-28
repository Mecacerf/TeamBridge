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
import pathlib
import shutil
import os
import datetime as dt

# Internal libraries
from tests.test_constants import *

########################################################################
#                          Assets arrangement                          #
########################################################################

@pytest.fixture
def arrange_assets():
    """
    This pytest fixture prepares the test assets. It removes any existing old
    test asset folders and creates a new one.
    """
    assets_src = pathlib.Path(TEST_ASSETS_SRC_FOLDER)
    assets_dst = pathlib.Path(TEST_ASSETS_DST_FOLDER)
    
    if not assets_src.exists():
        raise FileNotFoundError(f"Test assets folder not found at '{assets_src.resolve()}'.")
    
    if assets_dst.exists():
        def remove_readonly(func, path, exc_info):
            """
            Changes the file attribute and retries deletion if permission is denied.
            """
            os.chmod(path, 0o777) # Grant full permissions
            func(path) # Retry the function
        # Remove old test assets folder
        shutil.rmtree(assets_dst, onexc=remove_readonly)

    shutil.copytree(assets_src, assets_dst)



# @pytest.fixture
# def teambridge_model(arrange_spreadsheet_time_tracker) -> Generator[TeamBridgeScheduler, None, None]:
#     """
#     Create a configured teambridge model instance.
#     """
#     # Create the model using a SpreadsheetTimeTracker
#     repository = SpreadsheetsRepository(SAMPLES_TEST_FOLDER)
#     time_tracker_provider=lambda date, code: SpreadsheetTimeTracker(repository=repository, employee_id=code, date=date)
#     model = TeamBridgeScheduler(time_tracker_provider=time_tracker_provider)
#     # Yield and close automatically
#     yield model
#     model.close()

# @pytest.fixture
# def teambridge_viewmodel(teambridge_model, monkeypatch) -> Generator[TeamBridgeViewModel, None, None]:
#     """
#     Create a configured teambridge viewmodel instance.
#     """
#     # Create a barcode scanner
#     scanner = BarcodeScanner()
#     def void(**kwargs): pass
#     monkeypatch.setattr(scanner, "close", void)
#     # Create a viewmodel
#     viewmodel = TeamBridgeViewModel(teambridge_model, 
#                                     scanner=scanner, 
#                                     cam_idx=0,
#                                     scan_rate=10,
#                                     debug_mode=True)
#     # Yield and close automatically
#     # The scanner is also given in order to use monkeypatch to mock its functionalities
#     yield (viewmodel, scanner)
#     viewmodel.close()
