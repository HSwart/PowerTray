# Power BI Tray Monitor - Setup Script
# Run this script to set up the application automatically

param(
    [switch]$SkipStartup,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Power BI Tray Monitor - Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python installation
Write-Host "[1/5] Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 9)) {
            Write-Host "  ERROR: Python 3.9+ required. Found: $pythonVersion" -ForegroundColor Red
            Write-Host "  Download from: https://www.python.org/downloads/" -ForegroundColor Gray
            exit 1
        }
        Write-Host "  Found: $pythonVersion" -ForegroundColor Green
    }
} catch {
    Write-Host "  ERROR: Python not found. Please install Python 3.9+" -ForegroundColor Red
    Write-Host "  Download from: https://www.python.org/downloads/" -ForegroundColor Gray
    exit 1
}

# Create virtual environment
Write-Host ""
Write-Host "[2/5] Setting up virtual environment..." -ForegroundColor Yellow
$venvPath = Join-Path $scriptPath ".venv"

if ((Test-Path $venvPath) -and -not $Force) {
    Write-Host "  Virtual environment already exists." -ForegroundColor Green
    Write-Host "  Use -Force to recreate it." -ForegroundColor Gray
} else {
    if (Test-Path $venvPath) {
        Write-Host "  Removing existing virtual environment..." -ForegroundColor Gray
        Remove-Item -Recurse -Force $venvPath
    }
    Write-Host "  Creating virtual environment..." -ForegroundColor Gray
    python -m venv $venvPath
    Write-Host "  Virtual environment created." -ForegroundColor Green
}

# Activate and install dependencies
Write-Host ""
Write-Host "[3/5] Installing dependencies..." -ForegroundColor Yellow
$pipPath = Join-Path $venvPath "Scripts\pip.exe"
$requirementsPath = Join-Path $scriptPath "requirements.txt"

& $pipPath install --upgrade pip --quiet
& $pipPath install -r $requirementsPath --quiet

Write-Host "  Dependencies installed:" -ForegroundColor Green
Write-Host "    - pystray (system tray)" -ForegroundColor Gray
Write-Host "    - pillow (icon generation)" -ForegroundColor Gray
Write-Host "    - msal (Microsoft authentication)" -ForegroundColor Gray
Write-Host "    - requests (API calls)" -ForegroundColor Gray
Write-Host "    - customtkinter (UI)" -ForegroundColor Gray
Write-Host "    - winotify (notifications)" -ForegroundColor Gray

# Check for settings.json
Write-Host ""
Write-Host "[4/5] Checking configuration..." -ForegroundColor Yellow
$settingsPath = Join-Path $scriptPath "settings.json"

if (Test-Path $settingsPath) {
    Write-Host "  Found existing settings.json" -ForegroundColor Green
    
    # Read and display current config
    $settings = Get-Content $settingsPath | ConvertFrom-Json
    if ($settings.workspace_id -and $settings.dataset_id) {
        Write-Host "  Workspace ID: $($settings.workspace_id.Substring(0, 8))..." -ForegroundColor Gray
        Write-Host "  Dataset ID: $($settings.dataset_id.Substring(0, 8))..." -ForegroundColor Gray
    } else {
        Write-Host "  WARNING: workspace_id or dataset_id not configured!" -ForegroundColor Yellow
        Write-Host "  Edit settings.json or use Settings from the tray menu." -ForegroundColor Yellow
    }
} else {
    Write-Host "  No settings.json found." -ForegroundColor Yellow
    Write-Host "  You'll need to configure your workspace and dataset IDs." -ForegroundColor Yellow
    Write-Host "  Use Settings from the tray menu after first run." -ForegroundColor Yellow
}

# Add to startup (optional)
Write-Host ""
Write-Host "[5/5] Windows Startup..." -ForegroundColor Yellow

if (-not $SkipStartup) {
    $response = Read-Host "  Add to Windows startup? (Y/n)"
    if ($response -eq "" -or $response.ToLower() -eq "y") {
        & (Join-Path $scriptPath "scripts\add_to_startup.bat") | Out-Null
        Write-Host "  Added to Windows startup." -ForegroundColor Green
    } else {
        Write-Host "  Skipped. Run scripts\add_to_startup.bat later if needed." -ForegroundColor Gray
    }
} else {
    Write-Host "  Skipped (use -SkipStartup was specified)." -ForegroundColor Gray
}

# Done!
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start the application:" -ForegroundColor Cyan
Write-Host "  - Double-click 'scripts\pbi_tray_silent.vbs'" -ForegroundColor White
Write-Host "  - Or run: python -m pbi_tray" -ForegroundColor White
Write-Host ""
Write-Host "First run will open a browser for Microsoft sign-in." -ForegroundColor Yellow
Write-Host ""

# Ask to launch now
$launch = Read-Host "Launch Power BI Tray now? (Y/n)"
if ($launch -eq "" -or $launch.ToLower() -eq "y") {
    Write-Host ""
    Write-Host "Starting Power BI Tray..." -ForegroundColor Cyan
    $pythonPath = Join-Path $venvPath "Scripts\python.exe"
    Start-Process -FilePath $pythonPath -ArgumentList "-m", "pbi_tray" -WorkingDirectory $scriptPath
    Write-Host "Application started! Look for the icon in your system tray." -ForegroundColor Green
}

Write-Host ""
