@echo off
:: Power BI Tray Monitor - Quick Setup
:: Double-click this file to run setup

echo.
echo ========================================
echo   Power BI Tray Monitor - Setup
echo ========================================
echo.
echo This will set up the application for you.
echo.

:: Check if PowerShell is available
where powershell >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: PowerShell not found.
    echo Please run setup.ps1 manually.
    pause
    exit /b 1
)

:: Run the PowerShell setup script
powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"

pause
