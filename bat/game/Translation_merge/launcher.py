#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动器 - 自动检查依赖并启动主程序
"""

import sys
import subprocess
import importlib.util

def check_package(package_name):
    """检查包是否已安装"""
    spec = importlib.util.find_spec(package_name)
    return spec is not None

def install_package(package_name):
    """安装包"""
    print(f"正在安装 {package_name}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

def main():
    print("=" * 50)
    print("  游戏翻译工作流工具 v2.0")
    print("=" * 50)
    print()
    
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ 错误: 需要 Python 3.8 或更高版本")
        print(f"   当前版本: Python {sys.version}")
        input("按Enter键退出...")
        sys.exit(1)
    
    print(f"✅ Python版本: {sys.version.split()[0]}")
    
    # 检查依赖
    packages = {
        'PyQt6': 'PyQt6',
        'requests': 'requests'
    }
    
    print("\n检查依赖包...")
    for display_name, package_name in packages.items():
        if not check_package(package_name):
            print(f"⚠️  {display_name} 未安装")
            try:
                install_package(package_name)
                print(f"✅ {display_name} 安装成功")
            except Exception as e:
                print(f"❌ {display_name} 安装失败: {e}")
                input("按Enter键退出...")
                sys.exit(1)
        else:
            print(f"✅ {display_name} 已安装")
    
    # 启动主程序
    print("\n正在启动程序...")
    print("=" * 50)
    print()
    
    try:
        import translation_gui
        translation_gui.main()
    except Exception as e:
        print(f"\n❌ 程序运行失败: {e}")
        import traceback
        traceback.print_exc()
        input("\n按Enter键退出...")
        sys.exit(1)

if __name__ == "__main__":
    main()
