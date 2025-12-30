# Get the directory where this script is located
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "context_monitor.pyw"

# Launch the context monitor with the full path
Start-Process pythonw -ArgumentList "`"$pythonScript`"" -WindowStyle Hidden
