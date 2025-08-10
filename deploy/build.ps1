# File: build.ps1
# Author: Bastian Cerf
# Date: 26/03/2025
# Description: 
#     Automatically create and activate the python virtual environment, 
#     install program dependencies and build the TeamBridge application 
#     using PyInstaller.
#
# Company: Mecacerf SA
# Website: http://mecacerf.ch
# Contact: info@mecacerf.ch

# Move to the script parent folder
Set-Location -Path (Get-Item $PSScriptRoot).Parent.FullName

# Virtual environment path
$venvDir = ".venv"

# Check if the virtual environment exists
if (!(Test-Path $venvDir)) {
    Write-Output "Virtual environment not found. Creating one..."
    python -m venv $venvDir
}

# Activate the virtual environment
$venvActivate = ".\$venvDir\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    Write-Output "Activating virtual environment..."
    & $venvActivate

    # Install last pip version
    python -m pip install --upgrade pip

    # Install dependencies
    pip install -U -r requirements.txt

    # Build teambridge from the spec file
    pyinstaller deploy\\TeamBridge.exe.spec --clean --workpath deploy\\build --distpath deploy\\dist

    # Deactivate the virtual environment
    deactivate
}
else {
    Write-Error "Failed to find activation script!"
}

# Pause to allow the user to consult the logs
pause
