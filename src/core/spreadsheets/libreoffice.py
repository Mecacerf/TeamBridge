#!/usr/bin/env python3
"""
File: libreoffice.py
Author: Bastian Cerf
Date: 18/05/2025
Description:
    This module provides functionality to load, evaluate and save a
    spreadsheet file using LibreOffice calc in headless mode.

    TODO:
        The automatic detection of LibreOffice in the filesystem
        should ideally occur once during program installation, rather
        than at every startup. The detected path could then be stored
        in the configuration file once this feature is implemented.

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import logging
import subprocess
import platform
import pathlib
import shutil
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Libre office program name
LIBEOFFICE_PROGRAM = "soffice"
# Cache folder to put evaluated spreadsheet files
LIBREOFFICE_CACHE_FOLDER = ".tmp_calc"
# LibreOffice subprocess timeout [s] to prevent indefinite blocking
LIBREOFFICE_TIMEOUT = 10.0

# Libre office program path
_libreoffice_path = None


def find_libreoffice() -> Optional[str]:
    """
    Attempts to find the LibreOffice installation path across Windows
    and Linux.
    Returns the path to soffice if found, otherwise None.

    Warning: the Linux implementation is not tested yet.

    Returns:
        Optional[str]: LibreOffice program path is found or None.
    """
    system = platform.system()

    # Windows: Check registry first, then common paths
    if system == "Windows":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\LibreOffice\\UNO\\InstallPath"
            ) as key:
                path, _ = winreg.QueryValueEx(key, "")
                exe_path = os.path.join(path, "soffice.exe")
                if os.path.exists(exe_path):
                    return exe_path
        except FileNotFoundError:
            pass  # Registry key not found

        # Fallback: Check default installation directories
        common_paths = [
            "C:\\Program Files\\LibreOffice\\program\\soffice.exe",
            "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe",
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path

    # Linux: Use `shutil.which()` to check system paths
    elif system == "Linux":
        linux_path = shutil.which("soffice")
        if linux_path:
            return linux_path

        # Fallback: Common installation directories
        common_paths = [
            "/usr/bin/soffice",
            "/usr/local/bin/soffice",
            "/opt/libreoffice/program/soffice",
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path

    # LibreOffice not found
    return None


# Automatically search for LibreOffice in the filesystem on module initialization
_libreoffice_path = find_libreoffice()

if _libreoffice_path:
    logger.info(f"'{LIBEOFFICE_PROGRAM}' program found under '{_libreoffice_path}'.")
else:
    logger.warning(f"'{LIBEOFFICE_PROGRAM}' not automatically found.")


def configure(libreoffice_path: str):
    """
    Manually configure the LibreOffice program path.

    Args:
        libreoffice_path (str): Path to the LibreOffice executable.
    """
    global _libreoffice_path
    _libreoffice_path = libreoffice_path
    logger.info(
        f"Manually configured Libreoffice program path to '{_libreoffice_path}'."
    )


def evaluate_calc(file_path: pathlib.Path):
    """
    Evaluate a spreadsheet file using LibreOffice calc in headless mode.

    Args:
        file_path (str): Path to the spreadsheet file

    Raises:
        RuntimeError: No LibreOffice installation found.
        FileExistsError: A previous evaluation didn't finish properly and
            a file is still existing in the temporary folder.
        RuntimeError: The LibreOffice execution returned an error.
        TimeoutError: The LibreOffice execution timed out.
        FileNotFoundError: LibreOffice didn't produce the expected output.
    """
    if _libreoffice_path is None:
        raise RuntimeError("No LibreOffice installation found in the filesystem.")

    tmp_file = pathlib.Path(LIBREOFFICE_CACHE_FOLDER) / file_path.name
    if tmp_file.exists():
        raise FileExistsError(
            f"The temporary file '{tmp_file}' already exists. A "
            "previous evaluation may have failed."
        )

    os.makedirs(LIBREOFFICE_CACHE_FOLDER, exist_ok=True)

    # Create and execute the LibreOffice command to evaluate and save a
    # spreadsheet document. The evaluated copy of the original document is
    # placed in the cache folder, instead of directly replacing the original
    # one. This way the original document doesn't get corrupted if an error
    # occurs. The replacement (file move) is done only on success.
    # https://help.libreoffice.org/latest/km/text/shared/guide/start_parameters.html
    command = [
        _libreoffice_path,  # LibreOffice executable path
        "--headless",
        "--norestore",
        "--nolockcheck",
        "--convert-to",
        "xlsx",  # Convert to XLSX format
        "--outdir",
        str(LIBREOFFICE_CACHE_FOLDER),  # Output to the temp folder
        str(file_path.resolve()),  # Path to the input spreadsheet
    ]

    # Run the command as a subprocess
    try:
        result = subprocess.run(
            command,
            check=True,  # Raise CalledProcessError if returncode != 0
            capture_output=True,  # Capture stdout and stderr
            timeout=LIBREOFFICE_TIMEOUT,  # Prevent indefinite hangs
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"LibreOffice subprocess failed with return code {e.returncode}.\n"
            f"command: {command}\n"
            f"stdout: {e.stdout.decode(errors='ignore')}\n"
            f"stderr: {e.stderr.decode(errors='ignore')}"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise TimeoutError("LibreOffice evaluation timed out.") from e

    # Check that the evaluated file was actually produced
    if not tmp_file.exists():
        raise FileNotFoundError(
            f"LibreOffice did not produce the expected output file.\n"
            f"command: {command}\n"
            f"stdout: {result.stdout.decode(errors='ignore')}\n"
            f"stderr: {result.stderr.decode(errors='ignore')}"
        )

    # Evaluation succeeded without any error: replace original file with
    # evaluated one
    os.replace(tmp_file, file_path)
