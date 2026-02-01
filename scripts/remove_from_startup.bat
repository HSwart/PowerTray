@echo off
REM Power BI Tray Widget - Remove from Windows Startup

set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_NAME=PowerBI Tray Widget.lnk

echo ============================================================
echo Power BI Tray Widget - Remove from Startup
echo ============================================================
echo.

if exist "%STARTUP_FOLDER%\%SHORTCUT_NAME%" (
    del "%STARTUP_FOLDER%\%SHORTCUT_NAME%"
    echo SUCCESS: Removed from Windows startup.
) else (
    echo Widget was not configured to run at startup.
)

echo.
pause
