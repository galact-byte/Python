#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频 BGM 配乐合成工具 —— 启动器（环境检查 + 引导）"""

import os
import shutil
import sys


def check_python():
    ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"[OK] Python 版本: {ver}")
    if sys.version_info < (3, 7):
        print("[X] 需要 Python 3.7+，请升级后重试")
        sys.exit(1)


def find_tool(name):
    p = shutil.which(name)
    if p:
        return p
    for c in (rf"D:\Software\ffmpeg\bin\{name}.exe",
              rf"C:\ffmpeg\bin\{name}.exe",
              rf"C:\Program Files\ffmpeg\bin\{name}.exe"):
        if os.path.isfile(c):
            return c
    return None


def check_ffmpeg():
    print("\n检查 ffmpeg / ffprobe ...")
    ok = True
    for t in ("ffmpeg", "ffprobe"):
        p = find_tool(t)
        if p:
            print(f"  [OK] {t}: {p}")
        else:
            print(f"  [X] 未找到 {t}")
            ok = False
    if not ok:
        print("\n  请安装 ffmpeg 并加入 PATH（或放到 D:\\Software\\ffmpeg\\bin），")
        print("  下载: https://www.gyan.dev/ffmpeg/builds/ (Windows)")
        sys.exit(1)


def start_app():
    print("\n正在启动工具...")
    print("=" * 56)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import bgm_tool
    bgm_tool.interactive()


def main():
    print("=" * 56)
    print("  视频 BGM 配乐合成工具  v1.0")
    print("=" * 56)
    print()
    check_python()
    check_ffmpeg()
    try:
        start_app()
    except KeyboardInterrupt:
        print("\n已退出。")


if __name__ == "__main__":
    main()
