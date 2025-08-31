# -*- mode: python ; coding: utf-8 -*-

import logging

logger = logging.getLogger(__name__)

########################################################################
#                           Clean last build                           #
########################################################################

import shutil, pathlib, os
from PyInstaller.utils.hooks import collect_dynamic_libs


def remove_readonly(func, path, exc_info):
    """Changes the file attribute and retries deletion if permission is denied."""
    os.chmod(path, 0o777)  # Grant full permissions
    func(path)


output = pathlib.Path("deploy\\dist\\")
if output.exists():
    shutil.rmtree(output, onexc=remove_readonly)

########################################################################
#                 Generate Windows file version info                   #
########################################################################

import subprocess

# get short commit hash
commit = (
    subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
)

COMPANY_NAME = "Mecacerf SA"
FILE_DESCRIPTION = f"TeamBridge Timestamping Application"
FILE_VERSION = f"dev #{commit}"  # Technical version
PRODUCT_NAME = "TeamBridge"
PRODUCT_VERSION = f"dev #{commit}"  # Marketing version
LEGAL_COPYRIGHT = "Not yet defined"
INTERNAL_FILENAME = "TeamBridge"
ORIGINAL_FILENAME = "TeamBridge.exe"

template = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', '{COMPANY_NAME}'),
          StringStruct('FileDescription', '{FILE_DESCRIPTION}'),
          StringStruct('FileVersion', '{FILE_VERSION}'),
          StringStruct('InternalName', '{INTERNAL_FILENAME}'),
          StringStruct('OriginalFilename', '{ORIGINAL_FILENAME}'),
          StringStruct('ProductName', '{PRODUCT_NAME}'),
          StringStruct('ProductVersion', '{PRODUCT_VERSION}'),
          StringStruct('LegalCopyright', '{LEGAL_COPYRIGHT}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""

file_version_info = f"deploy\\file_version_info.txt"
with open(file_version_info, "w", encoding="utf-8") as f:
    f.write(template)
    logger.info(f"File version info written under '{file_version_info}'.")

########################################################################
#                            Analysis step                             #
########################################################################

# Collect extra DLLs needed by pyzbar
# See https://pypi.org/project/pyzbar/ section "Windows error message"
# if an issue persists.
binaries = collect_dynamic_libs("pyzbar")

a = Analysis(
    ["..\\src\\main.py"],
    pathex=[os.path.abspath("src")],
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

########################################################################
#                         Executable build step                        #
########################################################################

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # <-- important, binaries handled in COLLECT
    name="TeamBridge",
    icon="..\\assets\\images\\company_logo_small.ico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # <-- disable UPX (avoid AV false positives)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=("..\\" + file_version_info),
)

########################################################################
#                  Collect step (final folder layout)                  #
########################################################################

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="",  # exe in root folder
)

########################################################################
#                            Post-build step                           #
########################################################################

# Copy extra assets
logger.info("Copying assets...")
shutil.copytree("assets\\", "deploy\\dist\\assets\\")
logger.info("Copying samples...")
shutil.copytree("samples\\", "deploy\\dist\\samples\\")
