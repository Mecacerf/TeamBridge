# File: autostart-script.ps1
# Author: Bastian Cerf
# Date: 23/03/2025
# Description: 
#     Automatically create and activate the python virtual environment, 
#     install program dependencies and start the teambridge application.
#
# Company: Mecacerf SA
# Website: http://mecacerf.ch
# Contact: info@mecacerf.ch

# Move to the script parent folder
Set-Location -Path (Get-Item $PSScriptRoot).Parent.FullName

# Virtual environment path
$venvDir = ".venv"

# Check if the virtual environment exists
if(!(Test-Path $venvDir))
{
    Write-Output "Virtual environment not found. Creating one..."
    python -m venv $venvDir
}

# Activate the virtual environment
$venvActivate = ".\$venvDir\Scripts\Activate.ps1"
if(Test-Path $venvActivate) 
{
    Write-Output "Activating virtual environment..."
    & $venvActivate

    # Install last pip version
    python -m pip install --upgrade pip

    # Install dependencies
    pip install -r requirements.txt

    # Run teambridge
    python src\main.py --fullscreen --repository assets/

    # Pause to allow the user to consult the logs
    pause

    # Deactivate the virtual environment
    deactivate
}
else 
{
    Write-Error "Failed to find activation script!"
}
