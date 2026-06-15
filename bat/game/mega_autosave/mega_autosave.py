"""Mega 网盘自动保存助手

监控 Windows 原生「另存为」对话框，弹出后自动点击 [保存(S)] 按钮。
用跨进程的 BM_CLICK 直接点按钮，不抢前台焦点，可以一边浏览网页一边自动保存。
"""

import sys
import time


def ensure_deps():
    """确保 pywin32 已安装。"""
    try:
        import win32gui  # noqa: F401
    except ImportError:
        print("[..] 缺少 pywin32，正在自动安装...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "pywin32", "-q"])
        try:
            import win32gui  # noqa: F401
        except ImportError:
            print("[X] pywin32 安装失败，请手动执行: pip install pywin32")
            sys.exit(1)
    print("[OK] 依赖就绪")


ensure_deps()

import win32con
import win32gui

DIALOG_CLASS = "#32770"          # Windows 通用对话框窗口类
SAVE_DIALOG_TITLE = "另存为"      # 只认这个标题，避免误点「确认另存为」等弹窗
SAVE_BUTTON_PREFIX = "保存"       # 保存按钮文本以「保存」开头（保存(S)）
# —— 节奏参数（按需调整）——
# 浏览器弹「另存为」时文件名是瞬间填好的，所以等待可以很短。
# 越短 = 弹窗在前台停留越短 = 对你正常操作的干扰越小（只闪一下）。
POLL_INTERVAL = 0.1              # 轮询间隔（秒），越小反应越快
SETTLE_DELAY = 0.12             # 弹窗出现后等一下再点，给文件名一点点缓冲
COOLDOWN = 0.4                  # 每次点完的冷却时间，避免连点下一个


def find_save_dialog():
    """找到当前可见的「另存为」对话框句柄，没有则返回 None。"""
    matches = []

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        if win32gui.GetClassName(hwnd) != DIALOG_CLASS:
            return
        # 标题必须完全等于「另存为」，不匹配「确认另存为」之类的二次确认框
        if win32gui.GetWindowText(hwnd) == SAVE_DIALOG_TITLE:
            matches.append(hwnd)

    win32gui.EnumWindows(callback, None)
    return matches[0] if matches else None


def find_save_button(dialog_hwnd):
    """在对话框里找到「保存」按钮句柄，没有则返回 None。"""
    found = []

    def callback(hwnd, _):
        if win32gui.GetClassName(hwnd) != "Button":
            return
        text = win32gui.GetWindowText(hwnd).replace("&", "")
        if text.startswith(SAVE_BUTTON_PREFIX):
            found.append(hwnd)

    win32gui.EnumChildWindows(dialog_hwnd, callback, None)
    return found[0] if found else None


def click(hwnd):
    """向按钮发送点击消息（跨进程有效，无需前台焦点）。"""
    win32gui.SendMessage(hwnd, win32con.BM_CLICK, 0, 0)


def main():
    print("=" * 52)
    print("  Mega 自动保存助手")
    print("=" * 52)
    print('  检测到「另存为」弹窗会自动点击 [保存]')
    print("  无需切前台，可继续浏览网页")
    print("  停止：按 Ctrl+C 或直接关闭本窗口")
    print("=" * 52)
    print("  监控中...\n")

    count = 0
    try:
        while True:
            dialog = find_save_dialog()
            if dialog:
                # 先稳一下，等弹窗完全渲染好（文件名填好）再点，避免点太快
                time.sleep(SETTLE_DELAY)
                # 确认弹窗还在（没被手动关掉）
                if not (win32gui.IsWindow(dialog) and find_save_dialog() == dialog):
                    continue
                button = find_save_button(dialog)
                if button:
                    click(button)
                    count += 1
                    print(f"  [{count:>4}] 已保存   {time.strftime('%H:%M:%S')}")
                    # 等待这个弹窗关闭，避免对同一个窗口重复点击
                    while win32gui.IsWindow(dialog) and find_save_dialog() == dialog:
                        time.sleep(0.1)
                    # 冷却，避免连点下一个
                    time.sleep(COOLDOWN)
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print(f"\n  已停止，本次共自动保存 {count} 个文件。")


if __name__ == "__main__":
    main()
