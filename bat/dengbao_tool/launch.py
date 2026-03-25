"""等保文档迁移工具 启动器"""

import subprocess
import sys
import threading
import webbrowser
import time


def run(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def check_python():
    ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"[OK] Python {ver}")
    if sys.version_info < (3, 8):
        print("[X] Python 3.8+")
        sys.exit(1)


def check_dependencies():
    print("\n检查依赖...")
    packages = {
        "flask": "flask",
        "docx": "python-docx",
        "lxml": "lxml",
    }
    for import_name, install_name in packages.items():
        try:
            __import__(import_name)
            print(f"  [OK] {import_name}")
        except ImportError:
            print(f"  [..] {import_name} 安装中...")
            run(f"{sys.executable} -m pip install {install_name} -q")
            try:
                __import__(import_name)
                print(f"  [OK] {import_name}")
            except ImportError:
                print(f"  [X] {import_name} 失败，请手动: pip install {install_name}")
                sys.exit(1)


def start_app():
    import os
    app_path = os.path.join(os.path.dirname(__file__), "app.py")

    print("\n启动中...")
    print("=" * 40)

    # 用 subprocess 启动 Flask（不替换当前进程）
    proc = subprocess.Popen(
        [sys.executable, app_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # 等 Flask 就绪后打开浏览器
    import urllib.request
    for _ in range(30):
        time.sleep(0.5)
        try:
            urllib.request.urlopen("http://localhost:5000", timeout=1)
            break
        except Exception:
            pass

    print("  http://localhost:5000")
    print("  按 Ctrl+C 停止")
    print("=" * 40)
    webbrowser.open("http://localhost:5000")

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print("\n已停止")


def main():
    print("=" * 40)
    print("  等保文档迁移工具 v2.1")
    print("=" * 40)
    check_python()
    check_dependencies()
    start_app()


if __name__ == "__main__":
    main()
