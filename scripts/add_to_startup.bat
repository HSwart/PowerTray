@echo off
REM Power BI Tray Widget - Add to Windows Startup
REM This script creates a shortcut in the Windows Startup folder

set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..
set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_NAME=PowerBI Tray Widget.lnk
set VBS_PATH=%SCRIPT_DIR%pbi_tray_silent.vbs

echo ============================================================
echo Power BI Tray Widget - Startup Configuration
echo ============================================================
echo.
echo This will add the Power BI Tray Widget to Windows startup.
echo.
echo Script location: %VBS_PATH%
echo Startup folder: %STARTUP_FOLDER%
echo.

REM Create a temporary VBScript to create the shortcut
set TEMP_VBS=%TEMP%\create_shortcut.vbs

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP_VBS%"
echo sLinkFile = "%STARTUP_FOLDER%\%SHORTCUT_NAME%" >> "%TEMP_VBS%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%TEMP_VBS%"
echo oLink.TargetPath = "%VBS_PATH%" >> "%TEMP_VBS%"
echo oLink.WorkingDirectory = "%PROJECT_DIR%" >> "%TEMP_VBS%"
echo oLink.Description = "Power BI Semantic Model Refresh Status Widget" >> "%TEMP_VBS%"
echo oLink.Save >> "%TEMP_VBS%"

cscript //nologo "%TEMP_VBS%"
del "%TEMP_VBS%"

if exist "%STARTUP_FOLDER%\%SHORTCUT_NAME%" (
    echo.
    echo SUCCESS: Shortcut created in Startup folder!
    echo The widget will now start automatically when you log in.
    echo.
    echo To remove from startup, delete this file:
    echo   %STARTUP_FOLDER%\%SHORTCUT_NAME%
) else (
    echo.
    echo ERROR: Failed to create shortcut.
)

echo.
pause
