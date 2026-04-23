@echo off
title Full Send Systems - Live Bridge
color 0A

echo.
echo  =====================================================
echo   FULL SEND SYSTEMS  -  Live Bridge Launcher
echo   Version B 1.10
echo  =====================================================
echo.

REM ── Check Python is installed ─────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found on this PC.
    echo.
    echo  Please install Python 3.10 or newer from:
    echo  https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: Tick "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

echo  [OK] Python found.

REM ── Install/update required packages ──────────────────
echo  Installing dependencies (this may take a moment)...
python -m pip install websockets --quiet --upgrade
python -m pip install irsdk --quiet --upgrade

echo  [OK] Dependencies ready.
echo.
echo  =====================================================
echo   Starting FSS Bridge...
echo   Chrome will open automatically.
echo.
echo   - iRacing must be running for LIVE mode
echo   - Without iRacing: DEMO mode activates automatically
echo   - Close this window to stop the bridge
echo  =====================================================
echo.

REM ── Launch bridge ─────────────────────────────────────
python fss_bridge.py

echo.
echo  Bridge stopped.
pause
