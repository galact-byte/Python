"""等保文档迁移工具 启动器"""

import subprocess
import sys
import webbrowser
import time
import os


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


def start_app(dev_mode: bool = False):
    app_path = os.path.join(os.path.dirname(__file__), "app.py")
    env = os.environ.copy()
    env["DENGBAO_DEV_MODE"] = "1" if dev_mode else "0"

    print("\n启动中...")
    print("=" * 40)
    print(f"  模式: {'开发模式（自动重载）' if dev_mode else '稳定模式'}")

    # 用 subprocess 启动 Flask（不替换当前进程）
    proc = subprocess.Popen(
        [sys.executable, app_path],
        stdout=None if dev_mode else subprocess.PIPE,
        stderr=None if dev_mode else subprocess.PIPE,
        env=env,
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
        if dev_mode:
            proc.wait()
            stdout_data, stderr_data = None, None
        else:
            stdout_data, stderr_data = proc.communicate()
        if proc.returncode and not dev_mode:
            print("\n[X] Flask 启动失败，退出码:", proc.returncode)
            if stdout_data:
                print("\n--- stdout ---")
                print(stdout_data.decode("utf-8", errors="replace") if isinstance(stdout_data, bytes) else stdout_data)
            if stderr_data:
                print("\n--- stderr ---")
                print(stderr_data.decode("utf-8", errors="replace") if isinstance(stderr_data, bytes) else stderr_data)
            sys.exit(proc.returncode)
    except KeyboardInterrupt:
        proc.terminate()
        print("\n已停止")


def main():
    dev_mode = "--dev" in sys.argv
    print("=" * 40)
    print(f"  等保文档迁移工具 {'开发模式' if dev_mode else '稳定模式'}")
    print("=" * 40)
    check_python()
    check_dependencies()
    start_app(dev_mode=dev_mode)


if __name__ == "__main__":
    main()
