@echo off
chcp 65001 >nul 2>&1
title Project Scraper GUI v1.0
python "%~dp0gui.py"
if errorlevel 1 pause
