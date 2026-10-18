"""DPI 感知与缩放工具。"""
from __future__ import annotations

import ctypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

try:
    shcore = ctypes.WinDLL("shcore", use_last_error=True)
except OSError:
    shcore = None

user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
user32.GetDpiForWindow.argtypes = [ctypes.c_void_p]
user32.GetDpiForWindow.restype = ctypes.c_uint
user32.GetDpiForSystem.restype = ctypes.c_uint
user32.GetSystemMetricsForDpi.argtypes = [ctypes.c_int, ctypes.c_uint]
user32.GetSystemMetricsForDpi.restype = ctypes.c_int

SM_CXSMICON = 49
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)


def enable() -> None:
    """Per-Monitor V2，失败则逐级降级。"""
    try:
        if user32.SetProcessDpiAwarenessContext(
                DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
            return
    except Exception:
        pass
    if shcore is not None:
        try:
            shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE
            return
        except Exception:
            pass
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


def dpi_for(hwnd=None) -> int:
    try:
        if hwnd:
            dpi = user32.GetDpiForWindow(hwnd)
            if dpi:
                return int(dpi)
        return int(user32.GetDpiForSystem()) or 96
    except Exception:
        return 96


def scale_for(hwnd=None) -> float:
    return dpi_for(hwnd) / 96.0


def small_icon_size() -> int:
    dpi = dpi_for(None)
    try:
        size = user32.GetSystemMetricsForDpi(SM_CXSMICON, dpi)
        if size > 0:
            return int(size)
    except Exception:
        pass
    return 16
