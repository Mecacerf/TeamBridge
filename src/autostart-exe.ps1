# File: autostart-exe.ps1
# Author: Bastian Cerf
# Date: 23/03/2025
# Description: 
#     Automatically run the TeamBridge application from generated executable.
#     Allow to specify program arguments.
#
# Company: Mecacerf SA
# Website: http://mecacerf.ch
# Contact: info@mecacerf.ch

# Assume the executable is in the same directory
Set-Location -Path (Get-Item $PSScriptRoot)

# Run TeamBridge
.\TeamBridge.exe --repository assets/ --fullscreen --dark --sleep-timeout 80 --sleep-brightness 0 --work-brightness 100
pause
