# Context Monitor Launcher
# Launches the Python desktop widget

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $scriptDir "context_monitor.py"

Write-Host "Launching Context Monitor..." -ForegroundColor Cyan

# Check if python is available
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    # Run with pythonw (no console window) if available, otherwise python
    if (Get-Command "pythonw" -ErrorAction SilentlyContinue) {
        Start-Process pythonw -ArgumentList """$scriptPath"""
    } else {
        Start-Process python -ArgumentList """$scriptPath"""
    }
    Write-Host "Context Monitor is running!" -ForegroundColor Green
} else {
    Write-Host "Error: Python not found." -ForegroundColor Red
    Write-Host "Please ensure Python is installed and in your PATH." -ForegroundColor Red
    pause
}
