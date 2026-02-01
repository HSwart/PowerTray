' Power BI Tray Widget - Silent Launcher
' This script runs the Python app without showing a console window

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the directory where this script is located (scripts folder)
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Get the project root directory (parent of scripts folder)
projectDir = fso.GetParentFolderName(scriptDir)

' Path to the Python executable in the virtual environment
pythonExe = projectDir & "\.venv\Scripts\pythonw.exe"

' Check if virtual environment exists
If Not fso.FileExists(pythonExe) Then
    MsgBox "Virtual environment not found. Please run setup first." & vbCrLf & _
           "Expected: " & pythonExe, vbExclamation, "Power BI Tray Widget"
    WScript.Quit 1
End If

' Run the Python package silently (pythonw.exe doesn't show console)
' Using -m pbi_tray to run the refactored package structure
WshShell.CurrentDirectory = projectDir
WshShell.Run """" & pythonExe & """ -m pbi_tray", 0, False
