#!/usr/bin/env python3
"""
File: spreadsheets_repository.py
Author: Bastian Cerf
Date: 19/03/2025
Description:
    Manages access to the spreadsheet files repository in a thread-safe
    manner. Typically, one instance of the `SheetsRepoAccessor` class is
    created per remote repository and injected into any component that
    requires access to the spreadsheet files.

    It operates on any directory available in the local file system,
    including network-mounted drives. To improve reliability, it includes
    a simple retry mechanism to handle temporary unavailability (e.g.,
    due to NAS devices entering sleep mode), and uses locking mechanisms
    to prevent simultaneous access to the same files.

    It is the responsibility of the user to ensure the file has been
    acquired before saving it or releasing it. Calling these functions
    without having acquiring the file before may cause unexpected behaviors.

    If an error happens during acquired spreadsheet file operations, it
    is normal and intended to not release it. The file will stay unusable
    until someone manually remove the lock file from the remote repository,
    assuming the errors have been manually solved.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import logging
import os
import pathlib
import shutil
import time
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Default local test repository
SHEETS_LOCAL_REPO = "samples"

# Temporary local and remote cache folders used to store files in use
SHEETS_LOCAL_CACHE = ".local_cache"
SHEETS_REMOTE_CACHE = ".remote_cache"

# Retry delay and timeout for remote repository access
REPOSITORY_DELAY = 1.0
REPOSITORY_TIMEOUT = 20.0

# Retry delay and timeout for copying/saving a file in the repository
SAVE_FILE_DELAY = 0.5
SAVE_FILE_TIMEOUT = 3.0

# Retry delay and timeout for file access on the remote repository
FILE_LOCK_DELAY = 0.5
FILE_LOCK_TIMEOUT = 5.0

# Pattern to list spreadsheet files
SPREADSHEETS_FILE_PATTERN = "*.xlsx"
# Regular expression to extract the employee ID from the file name
ID_FROM_FILE_NAME_REGEX = r"^(\d{3})[-_,:;]"
# The extension is added as a suffix to the file name
LOCK_FILE_EXTENSION = ".lock"


class SheetsRepoAccessor:
    """
    Manages access to the spreadsheet files repository in a thread-safe
    manner. Typically, one instance of the `SheetsRepoAccessor` class is
    created per remote repository and injected into any component that
    requires access to the spreadsheet files.
    """

    def __init__(
        self, remote_repository: Optional[str] = None, local_cache: Optional[str] = None
    ):
        """
        Initialize the spreadsheets repository accessor.

        Args:
            remote_repository (Optional[str]): Absolute or relative path
                to the remote spreadsheet files repository. Defaults to
                the local test repository.
            local_cache (Optional[str]): Optionally change the default
                local cache folder.

        Raises:
            TimeoutError: Raised if the remote repository cannot be
                accessed.
        """
        self._remote_repository = SHEETS_LOCAL_REPO
        if remote_repository:
            self._remote_repository = remote_repository

        self._local_cache = SHEETS_LOCAL_CACHE
        if local_cache:
            self._local_cache = local_cache

        # Check that the system has access to the remote repository
        self.__acquire_repository_path()

    @property
    def remote_repository(self) -> str:
        """
        Returns:
            str: Remote repository path.
        """
        return self._remote_repository

    def check_repo_available(self) -> bool:
        """
        Returns:
            bool: `True` if the remote repository is available.
        """
        try:
            self.__acquire_repository_path()
            return True
        except TimeoutError:
            return False

    def acquire_spreadsheet_file(
        self, employee_id: str, readonly: bool = False
    ) -> pathlib.Path:
        """
        Acquire the employee's spreadsheet file from the remote repository.

        This function performs the following steps (readonly is `False`):
        - Acquire the path to the remote repository
        - Ensure the employee's spreadsheet file exists
        - Acquire a lock on the remote file to prevent concurrent access
        - Create a local cache directory if it doesn't already exist
        - Copy the remote file in the local cache
        - Return a `Path` object pointing to the cached file

        This function performs the following steps (readonly is `True`):
        - Ensure the employee's spreadsheet file exists
        - Create a local cache directory if it doesn't already exist
        - Check the file doesn't already exist in the local cache, which
            would mean it is already open
        - Copy the remote file in the local cache
        - Return a `Path` object pointing to the cached file

        A read-only path must never be saved. However it must be released.

        This function always returns a valid path or raises an exception
        on failure.

        Args:
            employee_id (str): Employee's unique identifier.
            readonly (bool): `True` to acquire in read-only mode (no lock
                file created on remote repository).

        Returns:
            pathlib.Path: Path to the local cached spreadsheet file.

        Raises:
            TimeoutError: If accessing the remote repository or acquiring
                the file lock times out.
            FileNotFoundError: If no spreadsheet file exists for the given
                employee's id.
            FileExistsError: The file is already opened in read-only mode.
            OSError: For general operating system-related errors
                (e.g., I/O issues).
        """
        start = time.time()

        repo_path = self.__acquire_repository_path()

        # Search the employee's file in the remote files repository
        matches = [
            file
            for file in repo_path.glob(SPREADSHEETS_FILE_PATTERN)
            if file.is_file() and file.name.startswith(employee_id)
        ]

        if len(matches) == 0:
            raise FileNotFoundError(
                f"The spreadsheet file for employee '{employee_id}' doesn't exist."
            )
        elif len(matches) > 1:
            raise FileNotFoundError(
                f"There is more than one file for employee '{employee_id}'."
            )

        repo_file = matches[0]

        lock_file_path = str(repo_file.resolve()) + LOCK_FILE_EXTENSION
        if not readonly:
            self.__acquire_file_lock(lock_file_path)

        # Make sure the local cache exists
        os.makedirs(self._local_cache, exist_ok=True)

        if readonly:
            # If the file is opened in read-only mode, add a prefix to make the
            # difference with read/write files.
            local_file = pathlib.Path(self._local_cache) / (
                "readonly_" + repo_file.name
            )

            # Unlike read/write files, the lock doesn't protect a read-only
            # file to be opened multiple times by the same program instance.
            # A check is required to catch programming errors.
            if local_file.exists():
                raise FileExistsError(
                    f"'{repo_file.name}' is already open "
                    f"('{local_file.name}' exists in local cache)."
                )
        else:
            # When opening in read/write mode, the lock file in the remote
            # repository protects the file from being opened multiple times.
            # The file may already exist in the local cache if a previous
            # operation failed and the lock file wasn't deleted, which is
            # intended. If the lock file has been acquired, that means a user
            # manually solved the issue and deleted the lock file. It is now
            # legal to overwrite an old file in the local cache.
            local_file = pathlib.Path(self._local_cache) / repo_file.name

        oserror = None
        timeout = time.time() + SAVE_FILE_TIMEOUT
        while time.time() < timeout:
            try:
                shutil.copy2(repo_file, local_file)

                elapsed = (time.time() - start) * 1000.0
                logger.debug(
                    f"Acquired '{repo_file}' in local cache as '{local_file}' "
                    f"(read-only={readonly}) in {elapsed:.0f}ms."
                )
                return local_file

            except OSError as e:
                oserror = e
                time.sleep(SAVE_FILE_DELAY)

        try:
            # Failed to acquire, try to release the lock
            if not readonly:
                self.__release_file_lock(lock_file_path)
                logger.debug(f"Released '{lock_file_path}' after acquisition failed.")
        except TimeoutError:
            pass

        elapsed = (time.time() - start) * 1000.0
        raise TimeoutError(
            f"Unable to acquire '{repo_file}' after {elapsed:.0f}ms."
        ) from oserror

    def save_spreadsheet_file(self, local_file: pathlib.Path):
        """
        Save the spreadsheet file to the remote repository. This operation
        must be performed only after acquiring exclusive access to the file.

        The saving process follows these steps:
        - Acquire the path to the remote repository
        - Ensure the remote cache directory exists
        - Copy the spreadsheet file from the local cache to the remote cache
        - Atomically move the file from the remote cache to the main
        repository, replacing the previous versio

        The intermediate copy to the remote cache ensures that, in case
        of failure during the file transfer, the existing file in the
        repository remains intact. The final replacement is performed
        using an atomic `os.replace()` call.

        Args:
            local_file (pathlib.Path): Path to the spreadsheet file in
                the local cache.

        Raises:
            TimeoutError: If accessing the remote repository or saving
                the file times out.
            FileNotFoundError: If the specified local file does not exist.
            OSError: For general I/O or file system-related issues.
        """
        start = time.time()

        repo_path = self.__acquire_repository_path()
        remote_cache_path = repo_path / SHEETS_REMOTE_CACHE
        # Make sure the remote cache exists
        remote_cache_path.mkdir(parents=True, exist_ok=True)

        repo_cache_file = remote_cache_path / local_file.name
        repo_file = repo_path / local_file.name

        oserror = None
        timeout = time.time() + SAVE_FILE_TIMEOUT
        while time.time() < timeout:
            try:
                # Step 1: Copy from local cache to remote cache
                shutil.copy2(local_file, repo_cache_file)
                # Step 2: Atomically move to final repository location
                os.replace(repo_cache_file, repo_file)

                elapsed = (time.time() - start) * 1000.0
                logger.debug(f"Saved '{repo_file}' in {elapsed:.0f}ms.")
                return
            except OSError as e:
                oserror = e
                time.sleep(SAVE_FILE_DELAY)
            finally:
                # Always attempt to clean up intermediate file
                try:
                    if repo_cache_file.exists():
                        repo_cache_file.unlink()
                except Exception:
                    pass  # Best effort cleanup; ignore any errors

        elapsed = (time.time() - start) * 1000.0
        raise TimeoutError(
            f"Unable to save '{repo_file}' after {elapsed:.0f}ms."
        ) from oserror

    def release_spreadsheet_file(
        self, local_file: pathlib.Path, readonly: bool = False
    ):
        """
        Release the employee's spreadsheet file, allowing other processes
        to access it again.

        The releasing process follows these steps (not read-only):
        - Acquire the path to the remote repository
        - Delete the spreadsheet file from the local cache
        - Delete the lock file in the repository

        If read-only is set:
        - Delete the spreadsheet file from the local cache

        Note: Not setting the read-only flag for a file acquired in read-
        only mode is not critical, however setting it for a read/write
        file won't delete the lock file on the remote, which is critical.

        Args:
            local_file (pathlib.Path): Path to the spreadsheet file in
                the local cache.
            readonly (bool): `True` if the file was acquired in read-only
                mode.

        Raises:
            TimeoutError: Raised if the remote folder cannot be accessed
                after the specified retries.
            TimeoutError: If the lock file could not be removed within
                the timeout.
            OSError: For general I/O or file system-related issues.
        """
        if not readonly:
            repo_path = self.__acquire_repository_path()
            repo_file = repo_path / local_file.name
            self.__release_file_lock(str(repo_file.resolve()) + LOCK_FILE_EXTENSION)
            logger.debug(f"Released '{repo_file}'.")

        local_file.unlink()

    def list_employee_ids(self) -> list[str]:
        """
        List all registered employees from the remote repository.

        Returns:
            list[str]: A list of all employee IDs extracted from
                spreadsheet filenames.

        Raises:
            TimeoutError: Raised if the remote folder cannot be accessed
                after the specified retries.
        """
        repo_path = self.__acquire_repository_path()

        return [
            match.group(1)
            for file in repo_path.glob(SPREADSHEETS_FILE_PATTERN)
            if file.is_file()
            and (match := re.match(ID_FROM_FILE_NAME_REGEX, file.name))
        ]

    def __acquire_file_lock(self, lock_path: str):
        """
        Internal use only.
        Attempt to acquire the file lock by creating the lock file.

        This function retries for a defined timeout period to create the
        file, which may be temporarily inaccessible if currently used by
        another process.

        Args:
            lock_path (str): File lock path.

        Raises:
            TimeoutError: If the lock file could not be acquired within
                the timeout.
            OSError: For general I/O or file system-related issues.
        """
        # Lock file creation flags
        # https://docs.python.org/3/library/os.html
        # https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/open-wopen
        # These flags are available on Windows and Unix
        flags = (
            os.O_CREAT  # Creates a file as temporary
            | os.O_EXCL  # Returns an error value if the file already exists
            | os.O_WRONLY
        )  # Opens a file for writing only
        # Using os.O_EXCL allows to check if the file exists and create it if
        # not, in one operation. It seems like it is the best way to implement
        # such mechanism in a platform independent way, even though the operation
        # atomicity may depend on different factors such as the filesystem in use.

        timeout = time.time() + FILE_LOCK_TIMEOUT
        while time.time() < timeout:
            try:
                # Try to create the lock file and return on success
                fd = os.open(lock_path, flags)
                os.close(fd)
                return
            except FileExistsError:
                time.sleep(FILE_LOCK_DELAY)

        raise TimeoutError(
            f"Cannot acquire file lock '{lock_path}' after {FILE_LOCK_TIMEOUT} seconds."
        )

    def __release_file_lock(self, lock_path: str):
        """
        Internal use only.
        Attempt to release the file lock by deleting the lock file.

        This function retries for a defined timeout period to remove the
        file, which may be temporarily inaccessible (e.g., due to OS or
        network delays).

        Args:
            lock_path (str): Path to the lock file.

        Raises:
            TimeoutError: If the lock file could not be removed within
                the timeout.
        """
        timeout = time.time() + FILE_LOCK_TIMEOUT
        oserror = None

        while time.time() < timeout:
            try:
                pathlib.Path(lock_path).unlink(missing_ok=True)
                return  # Lock successfully released
            except OSError as e:
                # Likely permission error, file in use, etc.
                oserror = e
                time.sleep(FILE_LOCK_DELAY)

        raise TimeoutError(
            f"Cannot release file lock '{lock_path}' after {FILE_LOCK_TIMEOUT} seconds."
        ) from oserror

    def __acquire_repository_path(self) -> pathlib.Path:
        """
        Internal use only.
        Acquire the path to the remote spreadsheet files folder.
        Implements a simple retry mechanism if the path is unavailable.
        A dummy file is written up to RETRY_NUMBER times to attempt
        waking up a potentially sleeping drive.

        Returns:
            pathlib.Path: The path to the remote repository.

        Raises:
            TimeoutError: Raised if the remote folder cannot be accessed
                after the specified retries.
        """
        repo_path = pathlib.Path(self._remote_repository)
        dummy_file = repo_path / "remote_wakeup.txt"

        attempts = 0
        oserror = None
        timeout = time.time() + REPOSITORY_TIMEOUT

        while time.time() < timeout:
            # Return the repository Path as soon as it gets available
            if repo_path.exists():
                return repo_path

            # Otherwise try to write a dummy file to wakeup the sleeping drive
            try:
                attempts += 1
                with open(dummy_file, "w") as file:
                    file.write("Wakeup attempt.")
            except OSError as e:
                oserror = e
                # Only sleep on exception, if the operation succeeded the path should exist
                time.sleep(REPOSITORY_DELAY)

        raise TimeoutError(
            f"Failed to access '{repo_path}' after {attempts} attempts."
        ) from oserror
