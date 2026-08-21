@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE="
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%~dp0venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%~dp0env\Scripts\python.exe" set "PYTHON_EXE=%~dp0env\Scripts\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"

echo Starting hot_list debug server from: %CD%
echo Python: %PYTHON_EXE%
"%PYTHON_EXE%" "%~dp0main.py" debug
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" echo Server exited with error code %EXIT_CODE%.
exit /b %EXIT_CODE%
