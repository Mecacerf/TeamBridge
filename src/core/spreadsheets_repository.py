#!/usr/bin/env python3
"""
File: spreadsheets_repository.py
Author: Bastian Cerf
Date: 19/03/2025
Description: 
    Manage access to spreadsheet files repository.    

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Import logging and get the module logger
import logging
LOGGER = logging.getLogger(__name__)

# Libraries for files access
import os
import pathlib
import shutil
# Threading for locking mechanism
import threading
# Time for sleep
import time

################################################
#               Configuration                  #
################################################

# Temporary folder in which opened spreadsheets are placed
SPREADSHEETS_CACHE_FOLDER = ".local_cache/"
# Temporary folder on remote in which saved files are copied
REMOTE_CACHE_FOLDER = ".remote_cache/"
# Dummy file to create and write when trying to wakeup the NAS
DUMMY_FILE_NAME = ".remote_wakeup.txt"
# Delay between accesses retries
RETRY_ACCESS_DELAY = 5.0 # [s]
# Number of retries
RETRY_NUMBER = 3

class SpreadsheetsRepository:
    """
    Typically unique class shared among the spreadsheet time trackers to read and write files
    on a remote repository mounted on a disk drive.
    Thread-safe.
    """

    def __init__(self, repository_path: str, local_cache: str=None):
        """
        Create a repository accesser.

        Parameters:
            repository_path: path to files folder
            local_cache: local folder to cache opened files
        """
        # Create the lock object that will prevent multiple simultaneous file accesses
        self._lock = threading.Lock()
        # Save the database path
        self._repository_path = repository_path
        # Save the local cache path
        self._local_cache = SPREADSHEETS_CACHE_FOLDER
        if local_cache:
            self._local_cache = local_cache
        # Log activity
        LOGGER.info(f"The spreadsheets database is located under '{self._repository_path}'.")

    def acquire_employee_file(self, employee_id: str) -> pathlib.Path | None:
        """
        Search and acquire the employee's file and copy it in local cache.

        Returns:
            pathlib.Path: local employee's file path or None if not found
        Raise:
            RuntimeError: employee's file is already opened
            OSError: error related to file access
            TimeoutError: failed to access database folder after timeout
        """
        # Acquire lock
        with self._lock:
            # Check that the local cache doesn't already contain the file, that would mean the
            # file is already in use.
            if any(file.name.startswith(employee_id) for file in pathlib.Path(self._local_cache).glob("*.xlsx")):
                raise RuntimeError(f"The employee's file with id={employee_id} is already in use.")
            # Acquire the database files folder
            folder = self.__acquire_repository_path()
            # Search the employee's file based on given id by iterating on all spreadsheet files
            for remote_file in folder.glob("*.xlsx"):
                # Check that this is a file and its name starts with correct id
                if remote_file.is_file() and remote_file.name.startswith(employee_id):
                    # Employee's file is found
                    # Ensure local cache folder exists
                    os.makedirs(self._local_cache, exist_ok=True)
                    # Copy file to local cache, keeping metadata
                    local_file = pathlib.Path(self._local_cache) / remote_file.name
                    shutil.copy2(remote_file, local_file)
                    # Log activity
                    LOGGER.info(f"Successfully acquired '{remote_file}' as '{local_file}'.")
                    # Return local file path
                    return local_file
            # Employee's file not found
            return None

    def save_employee_file(self, path: pathlib.Path) -> None:
        """
        Save the employee's file.

        Parameters:
            path: path to local employee's file that was previously acquired
        Raise:
            FileNotFoundError: no file exists for given path
            FileExistsError: the remote database cache already contain the file
            OSError: a problem occurred related to OS operations
            TimeoutError: failed to access folder after timeout
        """
        # Check path exists
        if not path.exists():
            raise FileNotFoundError(f"Cannot find file '{path}' in local cache. Unable to save.")
        # Acquire lock
        with self._lock:
            # Acquire database folder
            folder = self.__acquire_repository_path()
            # Get remote cache folder and ensure the file doesn't already exist, which would mean
            # a previous operation failed.
            remote_cache_file = folder / REMOTE_CACHE_FOLDER / path.name
            if remote_cache_file.exists():
                raise FileExistsError(f"The employee's file '{remote_cache_file}' exists in remote cache folder," 
                                      "which may indicate that a previous operation failed. Saving aborted.")
            # Ensure remote cache folder exists
            os.makedirs(folder / REMOTE_CACHE_FOLDER, exist_ok=True)
            # Get actual remote file
            remote_file = folder / path.name
            # Copy the file to remote cache folder using copy2 from shutil (keep metadata)
            shutil.copy2(path, remote_cache_file)
            # Replace old file on remote, cached file is moved so it won't exist after the replace
            os.replace(remote_cache_file, remote_file)
            # Log activity
            LOGGER.info(f"Successfully saved '{path}' under '{remote_file}'.")

    def close_employee_file(self, path: pathlib.Path):
        """
        Close an employee's file. It will release the file lock. 
        Save the file before closing it.

        Parameters:
            path: path to local employee's file that was previously acquired
        Raise:
            FileNotFoundError: no file exists for given path
            FileExistsError: the remote database cache already contain the file
            OSError: a problem occurred related to OS operations
            TimeoutError: failed to access folder after timeout
        """
        # Check path exists
        if not path.exists():
            raise FileNotFoundError(f"Cannot find file '{path}' in local cache. Unable to close.")
        # Acquire lock
        with self._lock:
            # Remove file from local cache
            path.unlink()
            # Log activity
            LOGGER.info(f"Removed local file '{path}'.")

    def __acquire_repository_path(self) -> pathlib.Path:
        """
        Try to acquire the path to employees files folder.

        Returns:
            pathlib.Path: path to files folder
        Raise:
            TimeoutError: failed to access folder after timeout
        """
        # Get path to employees data files, it might be on a NAS
        folder = pathlib.Path(self._repository_path)
        # Get dummy file path
        dummy_file = folder / DUMMY_FILE_NAME
        # Number of access attempts
        attempts = 0
        # While the folder doesn't exist, try to open and write a simple file
        # It might wakeup the sleeping NAS
        while not folder.exists():
            try:
                # Open and write a dummy file
                with open(dummy_file, 'w') as file:
                    file.write("Wakeup attempt.")
            # Catch potential errors
            except (OSError, FileNotFoundError) as e:
                # Retry mechanism
                attempts += 1
                if attempts >= RETRY_NUMBER:
                    raise TimeoutError(f"Cannot access '{folder}' after {RETRY_NUMBER} attempts.")
                # Log activity
                LOGGER.warning(f"Cannot access files database (attempt #{attempts}).")
                LOGGER.warning(e)
                # Wait until next attempt
                time.sleep(RETRY_ACCESS_DELAY)

        # Return the existing folder
        return folder
