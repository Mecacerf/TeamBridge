#!/usr/bin/env python3
"""
File: qr_scanner_test.py
Author: Bastian Cerf
Date: 06/03/2025
Description:
    Unit test / integration test of the barcode scanner module.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import pytest
from pytest import FixtureRequest
import cv2
import pyvirtualcam
import threading
import pathlib
import time
from typing import Generator

# Internal libraries
from platform_io.barcode_scanner import BarcodeScanner

########################################################################
#                           Tests constants                            #
########################################################################

# Virtual camera id. If more than one camera is connected, ensure this is the
# id of the virtual camera created by OBS Studio.
VIRTUAL_CAM_IDX = 0
# Regular expression to use to identify employee's id
EMPLOYEE_REGEX = r"teambridge@(\w+)"
# Group to extract ID
EMPLOYEE_REGEX_GROUP = 1

########################################################################
#                               Fixtures                               #
########################################################################


@pytest.fixture(
    params=[
        ("tests/assets/qrscan-000.mp4", None),  # '000' doesn't match regular expression
        ("tests/assets/qrscan-teambridge@543.mp4", "543"),  # Shall identify id '543'
    ]
)
def open_virtual_device(request: FixtureRequest) -> Generator[str, None, None]:
    """
    Create, open the virtual camera and play a file given as parameter.

    Yields:
        str: the ID that shall be found in the playing video
    """
    # Read the file path and the expected id in the video
    video_path = request.param[0]
    expected_id = request.param[1]
    # Ensure the path exists
    assert pathlib.Path(video_path).exists()

    # Create a running flag for the video feeder thread
    run_feeder = threading.Event()
    # Create a running status for the video feeder thread
    status_feeder = threading.Event()

    # Video player task
    def video_player_task():
        """
        Read the given capture and play the frames in a
        virtual camera device. This function uses pyvirtualcam
        and require OBS studio to be installed on the system.
        """
        # Open the video file
        capture = cv2.VideoCapture(video_path)
        # Assert that the capture is opened
        assert capture.isOpened()

        # Get video properties
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(capture.get(cv2.CAP_PROP_FPS))
        print(
            f"Going to play {video_path} with dimension {width}x{height}px at {fps} fps."
        )

        # Create and open the virtual camera
        with pyvirtualcam.Camera(width, height, fps=fps) as cam:
            # Run while feeder flag is set
            while run_feeder.is_set():
                # Read the next frame
                ret, frame = capture.read()
                # Check status flag
                if ret:
                    # Frame successfully readen
                    # Convert BGR to RGB
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    # Send the frame to the virtual camera
                    cam.send(frame)  # type: ignore
                    # Synchronize with given fps value
                    cam.sleep_until_next_frame()
                    # Set the running status, first frame has been sent
                    status_feeder.set()
                else:
                    # The read failed
                    # Restart video while the capture is open
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        # Release the capture
        capture.release()

    # Run the video player task in a background thread
    video_task = threading.Thread(target=video_player_task, name="VirtualCam-Feeder")
    # Set the running flag and start the thread
    run_feeder.set()
    video_task.start()

    # Wait for the feeder to be started, expected in 5 seconds.
    if not status_feeder.wait(timeout=5):
        assert False
    # Run the test
    yield expected_id

    # Once test done, reset the flag and join the thread
    run_feeder.clear()
    video_task.join()
    # Add a little delay before starting next virtual camera, usually not required
    time.sleep(0.1)


@pytest.fixture
def prepare_scanner(
    open_virtual_device: str,
) -> Generator[tuple[BarcodeScanner, str], None, None]:
    """
    Open a virtual camera device then create, open and yields a barcode scanner.

    Yields:
        BarcodeScanner: the opened scanner
        str: expected ID in the video
    """
    # Create and open the scanner
    scanner = BarcodeScanner()
    scanner.configure(
        debug_mode=True, regex=EMPLOYEE_REGEX, extract_group=EMPLOYEE_REGEX_GROUP
    )
    scanner.open(cam_idx=VIRTUAL_CAM_IDX, scan_rate=5)
    # Run the test
    yield scanner, open_virtual_device
    # Close the scanner, wait for the scanning thread to finish
    scanner.close(join=True)


################################################
#                    Tests                     #
################################################


def test_multiple_open(prepare_scanner: tuple[BarcodeScanner, str]):
    """
    Try to reopen an already opened scanner and verify it throws an exception.
    """
    # Retrieve scanner and expected ID
    scanner, _ = prepare_scanner
    # Reopen
    with pytest.raises(RuntimeError):
        # An exception is raised because the scanner is already running
        scanner.open()


def test_clear_scanner(prepare_scanner: tuple[BarcodeScanner, str]):
    """
    Wait for an id to be scanned and clear the scanner.
    """
    scanner, _ = prepare_scanner
    # Wait for an id to be scanned
    timeout = time.time() + 10.0
    while not scanner.available() and timeout > time.time():
        time.sleep(0.1)
    # Check if an element is available
    if scanner.available():
        # Clear and assert no element is available
        scanner.clear()
        assert not scanner.available()
        # ID retrieval should raise an error
        with pytest.raises(KeyError):
            scanner.read_next()


def test_scan_id(prepare_scanner: tuple[BarcodeScanner, str]):
    """
    The test will open a virtual camera (OBS studio required) and plays a test video
    containing a QR code. It is then checked if the QR code is correctly scanned
    and added to the output list.
    """
    # Retrieve scanner and expected ID
    scanner, expected_id = prepare_scanner
    # Wait for an id to be scanned
    timeout = time.time() + 10.0
    while not scanner.available() and timeout > time.time():
        time.sleep(0.1)
    # Assert the expected id has been scanned
    if expected_id:
        assert scanner.available()
        scanned_id = scanner.read_next()
    else:
        assert not scanner.available()
        scanned_id = None
    print(f"Scanned ID='{scanned_id}', expected ID='{expected_id}'.")
    assert scanned_id == expected_id
