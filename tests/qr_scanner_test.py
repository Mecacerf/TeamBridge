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
import numpy as np
from qr_scanner import QRScanner

################################################
#               Tests constants                #
################################################

# Passphrase encoded in the video used to identify the virtual device
VIRTUAL_DEVICE_PASS_ID = "COUCOUCOUCO"
# Number of video devices that will be tried during identification phase
MAX_VIDEO_DEVICE_ID = 5

PX = [134, 100, 6]

################################################
#                  Fixtures                    #
################################################

@pytest.fixture(params=[
    ("samples/qrscan-000.mp4", '000')
])
def open_virtual_device(request):
    """
    Create, open the virtual camera and play the file given as parameter. 
    """
    # Read the file path and the expected id in the video
    video_path = request.param[0]
    expected_video_id = request.param[1]
    # Ensure the path exists
    assert pathlib.Path(video_path).exists()

    # Create a run flag to request start/stop of the video thread
    feeder_run = threading.Event()
    # Create a working flag to know when the feeder thread is feeding the video
    feeder_working = threading.Event()
    # Create a state flag to tell the feeder that it can start playing the video capture
    feeder_play_video = threading.Event()

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
            # During the time the feeder flag is not set, send a test
            # frame that will allow to identify the virtual device
            # Create the encoding frame
            frame = np.zeros((cam.height, cam.width, 3), np.uint8)
            # Encode the passphrase in the R component of the first pixels
            # for i, char in enumerate(VIRTUAL_DEVICE_PASS_ID):
            #     # Encode as a byte
            #     frame[0, i, 0] = ord(char)
            

            passphrase = "".join(chr(frame[0, i, 0]) for i in range(len(VIRTUAL_DEVICE_PASS_ID)))
            print(f"Start id phase run={feeder_run.is_set()} video={feeder_play_video.is_set()}, passphrase={passphrase} px={[frame[0, i, 0] for i in range(len(VIRTUAL_DEVICE_PASS_ID))]}")
            
            # Feed the virtual camera with this frame until the state changes
            while feeder_run.is_set() and not feeder_play_video.is_set():
                frame = np.zeros((cam.height, cam.width, 3), np.uint8)
                frame[:, :] = [255, 0 ,0]
                # Send the frame
                cam.send(frame)
                cv2.imshow("identification", frame)
                # Set the working flag
                feeder_working.set()
                # Sleep until next frame
                cam.sleep_until_next_frame()

            print("Start video phase")

            # Check that the capture is opened and that the feeder must run
            while feeder_run.is_set() and capture.isOpened():
                # Read the next frame
                ret, frame = capture.read()
                # Check status flag
                if ret:
                    # Frame successfully readen
                    # Convert BGR to RGB
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    # Send the frame to the virtual camera
                    cam.send(frame)
                    # Ensure the working flag is set
                    feeder_working.set()
                    # Synchronize with given fps value
                    cam.sleep_until_next_frame()
                else:
                    # The read failed
                    # Restart video while the capture is open
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        # Reset the working flag
        feeder_working.clear()
        print("Thread terminated")
                    
    # Run the video player task in a new thread
    video_task = threading.Thread(target=video_player_task, name="VirtualCam-Feeder")
    # Set the feeder run flag
    feeder_run.set()
    # Start the thread
    video_task.start()

    # Yield the work to next fixture
    yield (feeder_working, feeder_play_video, expected_video_id)

    # Once test done, reset the flag and join the thread        
    feeder_run.clear()
    video_task.join()
    # End message
    print("Virtual camera terminated.")

@pytest.fixture
def prepare_video_device(open_virtual_device):
    """
    """
    # Get the tuple parameters
    feeder_working, feeder_play_video, expected_video_id = open_virtual_device

    # Wait until the feeder thread is working, the virtual camera might not be found otherwise
    assert feeder_working.wait(timeout=1.0)
    import time
    time.sleep(1)

    print("Search virtual device")
    # Search the virtual device index
    cam_idx = -1
    for index in range(MAX_VIDEO_DEVICE_ID + 1):
        # Open the capture
        cap = cv2.VideoCapture(index=index)
        print(f"Try video capture {index} opened: {cap.isOpened()}")
        # Check if opened
        t = time.time() +3
        while cap.isOpened() and time.time() < t:
            # Grab a frame
            ret, frame = cap.read()
            # Check that read succeeded
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Try to decode the passphrase
                passphrase = "".join(chr(frame[0, i, 0]) for i in range(len(VIRTUAL_DEVICE_PASS_ID)))
                print(f"Decoded '{passphrase}' from capture {index}. px={[frame[0, i, 0] for i in range(len(VIRTUAL_DEVICE_PASS_ID))]}")
                cv2.imshow("actual", frame)
                cv2.waitKey(delay=20)
                # Check passphrase
                if passphrase == VIRTUAL_DEVICE_PASS_ID:
                    # Save the index and leave
                    cam_idx = index
                    break

    # Assert the the camera index has been found
    assert cam_idx >= 0

    # Set the play video flag to change state
    feeder_play_video.set()

    # Run the actual test
    yield (expected_video_id, cam_idx)


################################################
#                    Tests                     #
################################################

def test_run(prepare_video_device):
    """
    """
    import time

    # Create and open the scanner
    scanner = QRScanner()
    scanner.open(cam_idx=prepare_video_device[1], scan_rate=5, debug_window=True)
    
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
    assert ids[0] == prepare_video_device[0]
