@echo off
title Game Translation Tool

python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed!
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

pip install -q PyQt6 requests

python translation_gui.py

if errorlevel 1 (
    pause
)
