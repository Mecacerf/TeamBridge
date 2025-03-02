#!/usr/bin/env python3
"""
File: qr_scanner_test.py
Author: Bastian Cerf
Date: 06/03/2025
Description: 
    Unit test / integration test of the QR scanner module.
    The test will open a virtual camera (OBS studio required) and plays a test video
    containing a QR code. It is then checked if the QR code is correctly scanned
    and added to the output list.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

import pytest
import cv2
import pyvirtualcam
import threading
import pathlib
from qr_scanner import QRScanner

################################################
#               Tests constants                #
################################################

################################################
#                  Fixtures                    #
################################################

@pytest.fixture(params=[
    ("samples/qrscan-000.mp4", '000')
])
def open_virtual_device(request):
    """
    Create, open the virtual camera and play a file given as parameter. 
    """
    # Read the file path and the expected id in the video
    video_path = request.param[0]
    expected_id = request.param[1]
    # Ensure the path exists
    assert pathlib.Path(video_path).exists()

    # Create a running flag for the video feeder thread
    run_feeder = threading.Event()

    # Video player task
    def video_player_task():
        """
        Read the given capture and play the frames in a
        virtual camera device. This function uses pyvirtualcam 
        and require OBS studio to be installed on the system.
        """
        # Open the video file
        capture = cv2.VideoCapture(video_path)
        
        # Get video properties
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(capture.get(cv2.CAP_PROP_FPS))

        # Create and open the virtual camera
        with pyvirtualcam.Camera(width, height, fps=fps) as cam:
            # Check that the capture is opened and that the feeder must run
            while capture.isOpened() and run_feeder.is_set():
                # Read the next frame
                ret, frame = capture.read()
                # Check status flag
                if ret:
                    # Frame successfully readen
                    # Convert BGR to RGB
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    # Send the frame to the virtual camera
                    cam.send(frame)
                    # Synchronize with given fps value
                    cam.sleep_until_next_frame()
                else:
                    # The read failed
                    # Restart video while the capture is open
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    
    # Run the video player task in a subprocess
    video_task = threading.Thread(target=video_player_task, name="VirtualCam-Feeder")
    # Set the running flag and start the thread
    run_feeder.set()
    video_task.start()

    print(f"Going to play {video_path}.")

    # Run the actual test
    yield expected_id

    # Once test done, reset the flag and join the thread        
    run_feeder.clear()
    video_task.join()
    # End message
    print("Virtual camera terminated.")

################################################
#                    Tests                     #
################################################

def test_run(open_virtual_device):
    """
    """
    import time

    # Create and open the scanner
    scanner = QRScanner()
    scanner.open(cam_idx=0, scan_rate=5, debug_window=True)
    
    # Hold a list of scanned id(s)
    ids = []
    # Wait with a timeout until the flag is set and read the scanned id
    timeout = time.time() + 10.0
    while time.time() < timeout and not ids:
        # Check the flag
        while scanner.available():
            # Read the scanned id and append it in the list
            ids.append(scanner.get_next())
        # Otherwise just wait a little before polling again
        time.sleep(0.1)

    # Close the scanner
    scanner.close()

    # Check only the id '000' has been scanned
    assert len(ids) == 1
    assert ids[0] == open_virtual_device
