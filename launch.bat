@echo off
cd /d "%~dp0"
echo Launching Context Compass...
node_modules\electron\dist\electron.exe .
if errorlevel 1 (
    echo Electron exited with error code %errorlevel%
    pause
)
