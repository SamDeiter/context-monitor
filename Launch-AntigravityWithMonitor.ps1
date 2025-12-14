# Launch Antigravity + Context Monitor
# Starts the IDE and the token tracker widget together

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$monitorPath = Join-Path $scriptDir "context_monitor.py"
$antigravityPath = "$env:LOCALAPPDATA\Programs\Antigravity\bin\antigravity.cmd"

# 1. Start Context Monitor (Background)
Write-Host "Starting Context Monitor..." -ForegroundColor Cyan
if (Get-Command "pythonw" -ErrorAction SilentlyContinue) {
    Start-Process pythonw -ArgumentList """$monitorPath"""
} else {
    Start-Process python -ArgumentList """$monitorPath""" -WindowStyle Hidden
}

# 2. Start Antigravity
if (Test-Path $antigravityPath) {
    Write-Host "Starting Antigravity..." -ForegroundColor Green
    Start-Process $antigravityPath
} else {
    Write-Host "Warning: Antigravity executable not found at expected path: $antigravityPath" -ForegroundColor Yellow
    Write-Host "Please launch Antigravity manually." -ForegroundColor Gray
}

# Close this launcher window after a brief pause
Start-Sleep -Seconds 2
