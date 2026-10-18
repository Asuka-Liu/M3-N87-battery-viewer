"""入口：单实例、控制台、托盘常驻；tkinter 面板按需加载。"""
from __future__ import annotations

import argparse
import ctypes
import sys
import tkinter as tk

import config
import dpi
from state import AppState
from tray import TrayApp, WM_SHOW_PANEL, user32

ERROR_ALREADY_EXISTS = 183
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateMutexW.restype = ctypes.c_void_p
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
kernel32.GetConsoleWindow.restype = ctypes.c_void_p
kernel32.AllocConsole.restype = ctypes.c_bool


def parse_args():
    ap = argparse.ArgumentParser(description="外设电量托盘")
    ap.add_argument("--debug", action="store_true", help="分配控制台并输出调试信息")
    ap.add_argument("--debug-ui", action="store_true", help="启动时打开调试窗口")
    ap.add_argument("--panel", action="store_true", help="启动时直接显示面板")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    config.DEBUG = bool(args.debug)
    dpi.enable()

    # 打包为 --noconsole：只有 --debug 时才分配控制台
    if args.debug and not kernel32.GetConsoleWindow():
        if kernel32.AllocConsole():
            sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
            sys.stderr = sys.stdout
            print("[main] console attached", flush=True)

    hmutex = kernel32.CreateMutexW(None, False, config.MUTEX_NAME)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        hwnd = user32.FindWindowW(config.WINDOW_CLASS, None)
        if hwnd:
            user32.PostMessageW(hwnd, WM_SHOW_PANEL, 0, 0)
        return 0

    interval = config.POLL_SECONDS
    if config.DEBUG:
        print(f"[main] interval={interval}s debug=True", flush=True)

    state = AppState(interval)
    tray = TrayApp(state)
    tray.start()

    root = None
    panel = None
    debug_windows = []

    def open_debug():
        from debug_ui import DebugWindow
        if debug_windows:
            try:
                win = debug_windows[0]
                win.deiconify()
                win.lift()
                win.focus_force()
                return
            except Exception:
                debug_windows.clear()
        debug_windows.append(DebugWindow(root))

    def on_exit():
        if root is not None:
            root.quit()

    def ensure_ui(show: bool):
        nonlocal root, panel
        if root is None:
            from panel import Panel
            root = tk.Tk()
            panel = Panel(root, state, tray, on_exit, open_debug)
        if show:
            panel.show()
        return panel

    def run_ui() -> None:
        try:
            root.mainloop()
        finally:
            tray.quit()
            try:
                root.destroy()
            except Exception:
                pass

    if args.panel or args.debug_ui:
        ensure_ui(show=True)
        if args.debug_ui:
            root.after(200, open_debug)
        run_ui()
        return 0

    # 托盘先跑起来；面板在第一次右键时才创建（空闲内存更低）
    while True:
        msg = state.ui_queue.get()
        if msg == "quit":
            tray.quit()
            return 0
        if msg == "show_panel":
            ensure_ui(show=True)
            break

    run_ui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
