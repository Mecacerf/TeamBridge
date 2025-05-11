# -*- mode: python ; coding: utf-8 -*-

# Start by cleaning last build
import shutil, pathlib, os

# Remove with privileges
def remove_readonly(func, path, exc_info):
    """Changes the file attribute and retries deletion if permission is denied."""
    os.chmod(path, 0o777) # Grant full permissions
    func(path) # Retry the function

# Check if output folder already exists and remove it if it does
output = pathlib.Path("deploy/dist/")
if output.exists():
    shutil.rmtree(output, onexc=remove_readonly)

# PyInstaller
from PyInstaller.utils.hooks import collect_dynamic_libs
# Auto-collect all DLLs from pyzbar that may not be correctly detected by PyInstaller.
# See https://pypi.org/project/pyzbar/ Windows error message if an issue persists.
binaries = collect_dynamic_libs('pyzbar')

a = Analysis(
    ['..\\src\\main.py'],
    pathex=[],
    binaries=binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TeamBridge.exe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

print("Executable generation finished, copy utility files...")
# Copy program assets to dist folder  
shutil.copytree("assets/", "deploy/dist/assets/")
# Copy samples to dist folder to allow to run in test mode
shutil.copytree("samples/", "deploy/dist/samples/")
# Copy autostart executable utility script
shutil.copy("deploy/autostart-exe.ps1", "deploy/dist/autostart-exe.ps1")
