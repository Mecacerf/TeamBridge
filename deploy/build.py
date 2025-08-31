#!/usr/bin/env python3
"""
File: build.py
Author: Bastian Cerf
Date: 31/08/2025
Description:
    TeamBridge building script. It setups a virtual environment, install
    required dependencies and launch PyInstaller using the specification
    file according to the OS in use.

Usage:
    python build.py

Company: Mecacerf SA
Website: http://mecacerf.ch
Contact: info@mecacerf.ch
"""

# Standard libraries
import os
import sys
import subprocess
import venv
import shutil
from pathlib import Path


def run(cmd, **kwargs):
    """Run a command and stream its output, exit on error."""
    print(f"\n>>> Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=True, **kwargs)
    return result


def ensure_venv(venv_dir: Path):
    """Create venv if not exists, return Python executable inside venv."""
    if not venv_dir.exists():
        print(f"Creating virtual environment in {venv_dir}...")
        venv.EnvBuilder(with_pip=True).create(venv_dir)

    if os.name == "nt":
        python_exe = venv_dir / "Scripts" / "python.exe"
    else:
        python_exe = venv_dir / "bin" / "python"

    if not python_exe.exists():
        raise FileNotFoundError(f"Could not find venv Python at {python_exe}.")

    return str(python_exe)


def main():
    # Move to root directory
    root_dir = Path(__file__).resolve().parent.parent
    os.chdir(root_dir)

    venv_dir = root_dir / ".venv"
    python_exe = ensure_venv(venv_dir)

    # Upgrade pip
    run([python_exe, "-m", "pip", "install", "--upgrade", "pip"])

    # Install requirements
    run([python_exe, "-m", "pip", "install", "-U", "-r", "requirements.txt"])

    # Choose spec file depending on OS
    if sys.platform == "win32":
        spec_file = "deploy/TeamBridge.exe.spec"
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}.")

    dist_dir = "deploy/dist"
    build_dir = "deploy/build"

    # Run PyInstaller inside venv
    run(
        [
            python_exe,
            "-m",
            "PyInstaller",
            spec_file,
            "--clean",  # Do not reuse previous build files
            f"--workpath={build_dir}",
            f"--distpath={dist_dir}",
        ]
    )

    print("\n✅ Build finished successfully.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
