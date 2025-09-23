@echo off
chcp 65001 >nul
setlocal

rem 切换到工作盘符并进入工作目录
d:
cd "当前工具的目录"

rem 激活 conda 环境
call conda activate tender

rem 运行 Python 脚本
python main.py

rem 保持窗口开启，查看可能的错误信息
pause

endlocal