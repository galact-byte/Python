#!/bin/bash

echo "========================================"
echo "  游戏翻译工作流工具 v2.0"
echo "========================================"
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到Python3，请先安装Python 3.8或更高版本"
    exit 1
fi

echo "[信息] 检查依赖包..."

# 检查PyQt6
if ! python3 -c "import PyQt6" 2>/dev/null; then
    echo "[警告] 未安装PyQt6，正在安装..."
    pip3 install PyQt6
fi

# 检查requests
if ! python3 -c "import requests" 2>/dev/null; then
    echo "[警告] 未安装requests，正在安装..."
    pip3 install requests
fi

echo ""
echo "[信息] 启动程序..."
python3 translation_gui.py

if [ $? -ne 0 ]; then
    echo ""
    echo "[错误] 程序运行失败"
    read -p "按Enter键退出..."
fi
