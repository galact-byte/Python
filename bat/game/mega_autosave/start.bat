@echo off
chcp 65001 >nul 2>&1
title Mega AutoSave
python "%~dp0mega_autosave.py"
if errorlevel 1 pause
