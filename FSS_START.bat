@echo off
title Full Send Systems - Live Bridge
color 0A

echo.
echo  =====================================================
echo   FULL SEND SYSTEMS  -  Live Bridge Launcher
echo   Version B 1.20
echo  =====================================================
echo.

REM ── Go to the folder this BAT lives in ───────────────
cd /d "%~dp0"

REM ── Check Python ─────────────────────────────────────
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

REM ── Install/update required packages ─────────────────
echo  Installing dependencies...
python -m pip install websockets --quiet --upgrade
python -m pip install irsdk --quiet --upgrade
echo  [OK] Dependencies ready.
echo.

echo  =====================================================
echo   Starting FSS Bridge...
echo   Chrome will open automatically.
echo.
echo   - iRacing must be running for LIVE mode
echo   - Close this window to stop the bridge
echo  =====================================================
echo.

REM ── Launch bridge ────────────────────────────────────
python fss_bridge.py

echo.
echo  Bridge stopped.
pause
