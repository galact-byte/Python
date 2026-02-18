@chcp 65001 >nul 2>&1
@echo off
title 视频质量检测工具 v3.0

echo ==================================================
echo   视频质量检测工具 v3.0  (Video2X AI 超分修复)
echo ==================================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 Python，请先安装 Python 3
    echo    https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do echo ✅ Python版本: %%i

echo.
echo 检查依赖包...

:: 检查 PyQt6
python -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo ❌ PyQt6 未安装，正在安装...
    pip install PyQt6 -q
) else (
    echo ✅ PyQt6 已安装
)

:: 检查 opencv-python
python -c "import cv2" >nul 2>&1
if errorlevel 1 (
    echo ❌ opencv-python 未安装，正在安装...
    pip install opencv-python -q
) else (
    echo ✅ opencv-python 已安装
)

:: 检查 Video2X（AI修复功能）
if exist "D:\Software\Video2X Qt6\video2x.exe" (
    echo ✅ Video2X 已检测到
) else (
    where video2x >nul 2>&1
    if errorlevel 1 (
        echo ⚠️  Video2X 未检测到（AI修复功能不可用，可在程序内设置路径）
    ) else (
        echo ✅ Video2X 已检测到
    )
)

echo.
echo 正在启动程序...
echo ==================================================
python "%~dp0video_inspector.py"
if errorlevel 1 (
    echo.
    echo 程序异常退出，请检查错误信息。
    pause
)
