@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File Launch-Monitor.ps1
exit
