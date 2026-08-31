@echo off
setlocal
cd /d "%~dp0"
title KIWOOM MOCK AUTO TRADER

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment was not found.
    echo Open this file from the Kiwoom project folder.
    pause
    exit /b 1
)

echo Starting Kiwoom MOCK auto-trading dashboard...
echo Close this window with Ctrl+C to stop monitoring safely.
".venv\Scripts\python.exe" -m app.main auto-trade-dashboard --loop-seconds 60 --confirm AUTO-MOCK-ORDER

echo.
echo Monitoring stopped. No additional order was sent by this batch file.
pause
