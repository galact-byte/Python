#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).parent
VENV_DIR = ROOT_DIR / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
API_KEY_FILE = ROOT_DIR / "api_key.json"
PDF_DIR = ROOT_DIR / "pdfs"
PACKAGES = ["pymupdf", "dashscope", "openpyxl"]
MIRROR_URL = "https://mirrors.aliyun.com/pypi/simple/"


def color(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def info(text: str) -> None:
    print(color("96", text))


def ok(text: str) -> None:
    print(color("92", f"[OK] {text}"))


def warn(text: str) -> None:
    print(color("93", f"[!] {text}"))


def fail(text: str) -> None:
    print(color("91", f"[ERROR] {text}"))


def print_header(title: str) -> None:
    line = "=" * 52
    print()
    print(color("93", line))
    print(color("93", f"  {title}"))
    print(color("93", line))
    print()


def run_command(args, check=True):
    return subprocess.run(args, check=check)


def current_python_ok() -> None:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok(f"Python 已找到: {version}")
    if sys.version_info < (3, 8):
        fail("需要 Python 3.8 及以上版本")
        sys.exit(1)


def ensure_venv() -> None:
    if VENV_PYTHON.exists():
        ok("已检测到独立运行环境 .venv")
        return
    info("首次使用，正在创建独立运行环境...")
    run_command([sys.executable, "-m", "venv", str(VENV_DIR)])
    ok("独立运行环境已创建")


def ensure_dependencies() -> None:
    ensure_venv()
    info("正在检查并安装依赖包...")
    run_command([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"], check=False)
    run_command(
        [str(VENV_PYTHON), "-m", "pip", "install", "-i", MIRROR_URL, *PACKAGES]
    )
    ok("依赖安装完成")


def load_api_key() -> str:
    if not API_KEY_FILE.exists():
        fail("未找到 api_key.json")
        print("请确认该文件与程序放在同一目录。")
        sys.exit(1)

    with open(API_KEY_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    api_key = data.get("DASHSCOPE_API_KEY", "").strip()
    if not api_key or api_key.startswith("sk-xxx"):
        fail("请先在 api_key.json 中填写有效的阿里百炼 API Key")
        print("获取地址: https://dashscope.console.aliyun.com/")
        sys.exit(1)
    ok("API Key 已就绪")
    return api_key


def ensure_pdf_dir() -> None:
    PDF_DIR.mkdir(exist_ok=True)
    if any(PDF_DIR.glob("*.pdf")):
        ok("已检测到待处理 PDF")
        return
    warn("pdfs 文件夹里还没有 PDF 文件")
    print(f"请把 PDF 放进: {PDF_DIR}")
    sys.exit(0)


def run_main() -> None:
    load_api_key()
    ensure_pdf_dir()
    info("开始处理 PDF，请稍候...")
    run_command([str(VENV_PYTHON), str(ROOT_DIR / "main.py")])
    print()
    ok("处理完成，结果已保存到 output 文件夹")


def command_install() -> None:
    print_header("BidMiner Setup")
    current_python_ok()
    ensure_dependencies()
    print()
    print("接下来请按下面顺序操作：")
    print("1. 打开 api_key.json，填入你的阿里百炼 API Key")
    print("2. 把 PDF 文件放进 pdfs 文件夹")
    print("3. 双击 run.bat 开始提取")


def command_run() -> None:
    print_header("BidMiner PDF Extractor")
    current_python_ok()
    ensure_dependencies()
    run_main()


def parse_args():
    parser = argparse.ArgumentParser(description="BidMiner 启动器")
    parser.add_argument("command", choices=["install", "run"])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if args.command == "install":
            command_install()
        else:
            command_run()
    except subprocess.CalledProcessError:
        print()
        fail("执行失败，请把本窗口截图发给技术支持")
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        warn("已手动停止")
        sys.exit(1)


if __name__ == "__main__":
    main()
