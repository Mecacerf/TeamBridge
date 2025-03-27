# -*- mode: python ; coding: utf-8 -*-

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
# Copy autostart script to dist folder
import shutil, pathlib, os
shutil.copy("src/autostart-exe.ps1", "deploy/dist/autostart-exe.ps1")
# Copy test samples to dist folder for demonstration purpose
os.makedirs("deploy/dist/samples/", exist_ok=True)
for sample in pathlib.Path("samples/").glob("*.xlsx"):
    shutil.copy(sample, pathlib.Path("deploy/dist/samples/") / sample.name)
