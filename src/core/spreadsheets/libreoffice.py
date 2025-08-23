#!/usr/bin/env python3
"""
File: libreoffice.py
Author: Bastian Cerf
Date: 18/05/2025
Description:
    This module provides functionality to load, evaluate and save a
    spreadsheet file using LibreOffice calc in headless mode.

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

# Internal libraries
from local_config import LocalConfig

logger = logging.getLogger(__name__)

# Cache folder to put evaluated spreadsheet files
LIBREOFFICE_CACHE_FOLDER = ".tmp_calc"
# LibreOffice subprocess timeout [s] to prevent indefinite blocking
LIBREOFFICE_TIMEOUT = 15.0

# Get application configuration
_config = LocalConfig()

# Libre office program path
_libreoffice_path = None


def search_libreoffice() -> Optional[str]:
    """
    Attempts to find the LibreOffice installation path across Windows
    and Linux.
    Returns the path to `soffice` if found, otherwise `None`.

    Warning/TODO: the Linux implementation is not tested yet.

    Returns:
        Optional[str]: LibreOffice program path if found or `None`.
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


# Get LibreOffice path from the configuration
_libreoffice_path = _config.section("dependencies").get("libreoffice")

if not _libreoffice_path:
    logger.info("Scanning the filesystem to search a LibreOffice installation...")
    _libreoffice_path = search_libreoffice()
    if _libreoffice_path:
        logger.info(f"LibreOffice installation found under '{_libreoffice_path}'.")
        _config.persist("dependencies", "libreoffice", _libreoffice_path)

if not _libreoffice_path:
    raise FileNotFoundError(
        "LibreOffice is not installed on this computer. It is required to "
        "run this application. You can get it from "
        "https://us.libreoffice.org/download/libreoffice-stable/."
    )
else:
    # Check the installation is still available
    path = pathlib.Path(_libreoffice_path)
    if not path.exists():
        raise FileNotFoundError(
            f"No LibreOffice installation found under '{_libreoffice_path}'. "
            "The program may have been uninstalled. You can manually remove "
            f"the value for the key 'libreoffice' in '{_config.config_path}' "
            "and restart the application to perform a new system scan."
        )

    logger.info(f"Using LibreOffice installation under '{_libreoffice_path}'.")


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
