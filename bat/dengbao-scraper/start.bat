@echo off
chcp 65001 >nul 2>&1
title Dengbao Scraper v1.0
python "%~dp0scraper.py" %*
if errorlevel 1 pause
