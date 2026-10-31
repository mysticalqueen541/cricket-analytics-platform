@echo off
setlocal
cd /d "%~dp0"
echo Creating the local Python environment...
if not exist .venv (
    py -3.12 -m venv .venv
    if errorlevel 1 (
        echo Python 3.12 was not found. Install Python 3.12 from python.org, then run this file again.
        pause
        exit /b 1
    )
)
echo Installing project dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed. Check the error above.
    pause
    exit /b 1
)
echo.
echo Installation complete. Double-click run_windows.bat to start the app.
pause
