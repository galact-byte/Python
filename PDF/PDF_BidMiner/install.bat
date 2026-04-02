@echo off
chcp 65001 >nul 2>&1
title BidMiner Setup
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
  echo Python not found.
  echo Please install Python 3.11 and check "Add Python to PATH".
  pause
  exit /b 1
)
python "%~dp0launcher.py" install
pause
