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
config = LocalConfig()

# Cache folder to put evaluated spreadsheet files
LIBREOFFICE_CACHE_FOLDER = ".tmp_calc"
# LibreOffice subprocess timeout [s] to prevent indefinite blocking
LIBREOFFICE_TIMEOUT = 10.0

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
_libreoffice_path = config.section("dependencies").get("libreoffice")

if not _libreoffice_path:
    logger.info("Scanning the filesystem to search a LibreOffice installation...")
    _libreoffice_path = search_libreoffice()
    if _libreoffice_path:
        logger.info(f"LibreOffice installation found under '{_libreoffice_path}'.")
        config.persist("dependencies", "libreoffice", _libreoffice_path)

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
            f"the value for the key 'libreoffice' in '{config.config_path}' "
            "and restart the application to perform a new system scan."
        )

    logger.info(f"Using LibreOffice installation under '{_libreoffice_path}'.")


def evaluate_calc(file_path: pathlib.Path, allow_retry: bool = True) -> None:
    """
    Evaluate a spreadsheet file using LibreOffice Calc in headless mode.
    The file is re-saved (evaluated) to ensure formulas are calculated.

    Args:
        file_path: Path to the spreadsheet file.
        allow_retry: If True, retry once on timeout.

    Raises:
        RuntimeError: LibreOffice not found or failed execution.
        FileNotFoundError: Input file does not exist, or output not produced.
        TimeoutError: Conversion timed out after one retry.
    """
    if _libreoffice_path is None:
        raise RuntimeError("No LibreOffice installation found in the filesystem.")

    if not file_path.exists():
        raise FileNotFoundError(f"'{file_path}' does not exist.")

    tmp_file = pathlib.Path(LIBREOFFICE_CACHE_FOLDER) / file_path.name
    tmp_file.unlink(missing_ok=True)
    os.makedirs(LIBREOFFICE_CACHE_FOLDER, exist_ok=True)

    # Create and execute the LibreOffice command to evaluate and save a
    # spreadsheet document. The evaluated copy of the original document is
    # placed in the cache folder, instead of directly replacing the original
    # one. This way the original document doesn't get corrupted if an error
    # occurs. The replacement (file move) is done only on success.
    # https://help.libreoffice.org/latest/km/text/shared/guide/start_parameters.html
    command = [
        _libreoffice_path,
        "--headless",
        "--norestore",
        "--nolockcheck",
        "--convert-to",
        "xlsx",
        "--outdir",
        str(LIBREOFFICE_CACHE_FOLDER),
        str(file_path.resolve()),
    ]

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            timeout=LIBREOFFICE_TIMEOUT,
        )

    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"LibreOffice failed with return code {e.returncode}.\n"
            f"command: {command}\n"
            f"stdout: {e.stdout.decode(errors='ignore')}\n"
            f"stderr: {e.stderr.decode(errors='ignore')}"
        ) from e

    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode(errors="ignore") if e.stdout else "unavailable"
        stderr = e.stderr.decode(errors="ignore") if e.stderr else "unavailable"

        if allow_retry:
            logger.warning(
                f"LibreOffice evaluation timed out, retrying once...\n"
                f"command: {command}\n"
                f"stdout: {stdout}\n"
                f"stderr: {stderr}"
            )
            return evaluate_calc(file_path, allow_retry=False)

        # No retry left, raise with logs
        raise TimeoutError(
            f"LibreOffice evaluation timed out.\n"
            f"command: {command}\n"
            f"stdout: {stdout}\n"
            f"stderr: {stderr}"
        ) from e

    # Verify that LibreOffice actually produced the evaluated file
    if not tmp_file.exists():
        raise FileNotFoundError(
            f"LibreOffice did not produce the expected output file.\n"
            f"command: {command}\n"
            f"stdout: {result.stdout.decode(errors='ignore')}\n"
            f"stderr: {result.stderr.decode(errors='ignore')}"
        )

    # Replace original file with evaluated one
    os.replace(tmp_file, file_path)
