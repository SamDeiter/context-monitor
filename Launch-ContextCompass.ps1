# Context Compass Launcher
# Launches the widget in Chrome/Edge app mode (minimal window chrome)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$htmlPath = "file:///$($scriptDir -replace '\\', '/')/index.html"

# Try Chrome first, then Edge
$chromePaths = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles (x86)\Google\Chrome\Application\chrome.exe",
    "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
)

$edgePaths = @(
    "$env:ProgramFiles (x86)\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
)

$browser = $null

# Check for Chrome
foreach ($path in $chromePaths) {
    if (Test-Path $path) {
        $browser = $path
        break
    }
}

# Fall back to Edge
if (-not $browser) {
    foreach ($path in $edgePaths) {
        if (Test-Path $path) {
            $browser = $path
            break
        }
    }
}

if ($browser) {
    Write-Host "Launching Context Compass..." -ForegroundColor Cyan
    Write-Host "Browser: $browser" -ForegroundColor Gray
    
    # Launch in app mode with specific window size
    $args = @(
        "--app=$htmlPath",
        "--window-size=320,450",
        "--window-position=100,100",
        "--disable-extensions",
        "--new-window"
    )
    
    Start-Process $browser -ArgumentList $args
    Write-Host "Session Fuel is now running!" -ForegroundColor Green
    Write-Host "Tip: You can manually set it to 'Always on Top' using a tool like PowerToys" -ForegroundColor Yellow
} else {
    Write-Host "Error: Neither Chrome nor Edge was found." -ForegroundColor Red
    Write-Host "Please install Chrome or Edge to use this launcher." -ForegroundColor Red
    pause
}
