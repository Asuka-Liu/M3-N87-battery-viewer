"""Win32 托盘：单个图标（双电芯电池造型，两根竖条=鼠标/键盘电量）。

- 右键图标：打开/前置面板（通过 state.ui_queue 通知 Tk 主线程）
- 左键图标：立刻刷新
- 悬停：鼠标 M3：86% | 键盘 N87：72%（更新时间）
- SetTimer 驱动刷新，空闲时没有轮询/ sleep 循环
"""
from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes

import config
import devices
import dpi
from state import AppState, DeviceInfo

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

WM_APP = 0x8000
WM_TRAY = WM_APP + 1
WM_REFRESH_DONE = WM_APP + 2
WM_SHOW_PANEL = WM_APP + 3
WM_SET_INTERVAL = WM_APP + 4
WM_REFRESH_NOW = WM_APP + 5

WM_TIMER = 0x0113
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x01, 0x02, 0x04, 0x10
NIIF_WARNING = 0x02
TIMER_ID = 1

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT), ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int), ("hInstance", ctypes.c_void_p),
        ("hIcon", ctypes.c_void_p), ("hCursor", ctypes.c_void_p),
        ("hbrBackground", ctypes.c_void_p), ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", ctypes.c_void_p),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("hWnd", ctypes.c_void_p),
        ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT), ("hIcon", ctypes.c_void_p),
        ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD), ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD), ("guidItem", wintypes.BYTE * 16),
        ("hBalloonIcon", ctypes.c_void_p),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD), ("hbmMask", ctypes.c_void_p),
        ("hbmColor", ctypes.c_void_p),
    ]


user32.RegisterClassExW.restype = wintypes.WORD
user32.CreateWindowExW.restype = ctypes.c_void_p
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM]
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), ctypes.c_void_p,
                               wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                wintypes.WPARAM, wintypes.LPARAM]
user32.SetTimer.restype = ctypes.c_size_t
user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
user32.CreateIconIndirect.restype = ctypes.c_void_p
user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
user32.DestroyIcon.argtypes = [ctypes.c_void_p]
user32.FindWindowW.restype = ctypes.c_void_p
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = ctypes.c_void_p
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]

shell32.Shell_NotifyIconW.restype = wintypes.BOOL
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]

gdi32.CreateDIBSection.restype = ctypes.c_void_p
gdi32.CreateDIBSection.argtypes = [ctypes.c_void_p, ctypes.POINTER(BITMAPINFO),
                                   wintypes.UINT, ctypes.POINTER(ctypes.c_void_p),
                                   ctypes.c_void_p, wintypes.DWORD]
gdi32.CreateBitmap.restype = ctypes.c_void_p
gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.UINT,
                               wintypes.UINT, ctypes.c_void_p]
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]

COLOR_HIGH = (60, 200, 95)
COLOR_MID = (230, 184, 0)
COLOR_LOW = (229, 72, 77)
COLOR_NONE = (110, 110, 110)
SHELL = (238, 238, 238)
INSIDE = (28, 29, 31)


def level_color(level):
    if level is None:
        return COLOR_NONE
    if level >= 60:
        return COLOR_HIGH
    if level >= 30:
        return COLOR_MID
    return COLOR_LOW


def render_pixels(mouse: int | None, keyboard: int | None, size: int = 32) -> bytes:
    """两个同心圆环：外环=鼠标、内环=键盘，顺时针弧长=电量，4x 超采样抗锯齿。"""
    import math

    scale = 4 if size <= 64 else 2
    W = size * scale
    half = W / 2.0
    outer_r, outer_half = 0.355 * W, 0.047 * W
    inner_r, inner_half = 0.172 * W, 0.040 * W

    acc = [[0.0, 0.0, 0.0, 0.0] for _ in range(size * size)]

    for y in range(W):
        dy = y + 0.5 - half
        for x in range(W):
            dx = x + 0.5 - half
            r = math.hypot(dx, dy)
            ring = None
            if abs(r - outer_r) <= outer_half:
                ring = (mouse, outer_r)
            elif abs(r - inner_r) <= inner_half:
                ring = (keyboard, inner_r)
            if ring is None:
                continue
            level = ring[0]
            if level is None:
                cr, cg, cb, ca = 200, 200, 200, 45
            else:
                ang = math.degrees(math.atan2(dx, -dy)) % 360.0
                if ang <= level * 3.6:
                    cr, cg, cb = level_color(level)
                    ca = 255
                else:
                    cr, cg, cb, ca = 200, 200, 200, 45
            idx = (y // scale) * size + (x // scale)
            a = acc[idx]
            a[0] += cr * ca / 255.0
            a[1] += cg * ca / 255.0
            a[2] += cb * ca / 255.0
            a[3] += ca

    out = bytearray(size * size * 4)
    total = float(scale * scale)
    for i in range(size * size):
        ar, ag, ab, aa = acc[i]
        if aa > 0:
            af = aa / 255.0
            out[i * 4 + 0] = min(255, int(ab / af))
            out[i * 4 + 1] = min(255, int(ag / af))
            out[i * 4 + 2] = min(255, int(ar / af))
            out[i * 4 + 3] = min(255, int(aa / total))
    return bytes(out)


def make_icon(mouse: int | None, keyboard: int | None, size: int = 32):
    info = BITMAPINFO()
    info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.bmiHeader.biWidth = size
    info.bmiHeader.biHeight = -size
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    info.bmiHeader.biCompression = 0

    bits = ctypes.c_void_p()
    hbm = gdi32.CreateDIBSection(None, ctypes.byref(info), 0, ctypes.byref(bits), None, 0)
    if not hbm:
        return None

    data = render_pixels(mouse, keyboard, size)

    mask_stride = ((size + 31) // 32) * 4
    mask = bytearray(mask_stride * size)
    for y in range(size):
        for x in range(size):
            if data[(y * size + x) * 4 + 3] < 128:
                mask[(size - 1 - y) * mask_stride + (x // 8)] |= 0x80 >> (x % 8)
    mask_buf = (ctypes.c_ubyte * len(mask)).from_buffer_copy(bytes(mask))

    ctypes.memmove(bits, data, len(data))
    hbm_mask = gdi32.CreateBitmap(size, size, 1, 1, mask_buf)
    ii = ICONINFO()
    ii.fIcon = True
    ii.hbmMask = hbm_mask
    ii.hbmColor = hbm
    hicon = user32.CreateIconIndirect(ctypes.byref(ii))
    gdi32.DeleteObject(hbm_mask)
    gdi32.DeleteObject(hbm)
    return hicon


class TrayApp:
    def __init__(self, state: AppState):
        self.state = state
        self.hwnd = None
        self.icon = None
        self.icon_size = 32
        self.icon_key = "init"
        self._low_notified = {"mouse": False, "keyboard": False}
        self._wndproc_ref = WNDPROC(self._wndproc)
        self._ready = threading.Event()

    # ---------- 图标/提示 ----------
    def _tip(self) -> str:
        mouse, keyboard, _ = self.state.snapshot()
        m = f"{config.DEVICE_MOUSE_NAME}：{mouse.battery}%" if mouse.battery is not None \
            else f"{config.DEVICE_MOUSE_NAME}：--"
        k = f"{config.DEVICE_KEYBOARD_NAME}：{keyboard.battery}%" if keyboard.battery is not None \
            else f"{config.DEVICE_KEYBOARD_NAME}：--"
        when = mouse.updated or keyboard.updated or "未读取"
        return f"{m} | {k}（{when}）"

    def _nid(self, flags: int) -> NOTIFYICONDATAW:
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = config.ICON_ID
        nid.uFlags = flags
        return nid

    def _add_icon(self) -> None:
        nid = self._nid(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self.icon
        nid.szTip = self._tip()[:127]
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def _notify(self, title: str, text: str) -> None:
        nid = self._nid(NIF_INFO)
        nid.szInfoTitle = title[:63]
        nid.szInfo = text[:255]
        nid.dwInfoFlags = NIIF_WARNING
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def _check_low(self, key: str, name: str, level: int | None) -> None:
        if level is None:
            return
        if level < config.LOW_BATTERY_THRESHOLD:
            if not self._low_notified.get(key):
                self._low_notified[key] = True
                self._notify("电量不足", f"{name} 电量仅剩 {level}%，请充电")
        else:
            self._low_notified[key] = False

    def _apply_state(self) -> None:
        mouse, keyboard, _ = self.state.snapshot()
        key = (mouse.battery, keyboard.battery)
        if key != self.icon_key:
            new_icon = make_icon(mouse.battery, keyboard.battery, self.icon_size)
            old = self.icon
            self.icon = new_icon
            self.icon_key = key
            if old:
                user32.DestroyIcon(old)
            nid = self._nid(NIF_ICON | NIF_TIP)
            nid.hIcon = new_icon
            nid.szTip = self._tip()[:127]
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
        else:
            nid = self._nid(NIF_TIP)
            nid.szTip = self._tip()[:127]
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

        self._check_low("mouse", config.DEVICE_MOUSE_NAME, mouse.battery)
        self._check_low("keyboard", config.DEVICE_KEYBOARD_NAME, keyboard.battery)

    # ---------- 读取 ----------
    def request_refresh(self) -> None:
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_REFRESH_NOW, 0, 0)

    def set_interval(self, seconds: int) -> None:
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_SET_INTERVAL, seconds, 0)

    def quit(self) -> None:
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)

    def _read_worker(self) -> None:
        if not self.state.try_begin_read():
            return
        try:
            now = time.strftime("%H:%M:%S")
            mouse_b = devices.read_mouse()
            keyboard_b = devices.read_keyboard()
            if config.DEBUG:
                print(f"[read] mouse={mouse_b} keyboard={keyboard_b}", flush=True)
            self.state.set_result(
                DeviceInfo(battery=mouse_b, updated=now,
                           error="" if mouse_b is not None else "读取失败"),
                DeviceInfo(battery=keyboard_b, updated=now,
                           error="" if keyboard_b is not None else "读取失败"),
            )
            user32.PostMessageW(self.hwnd, WM_REFRESH_DONE, 0, 0)
            self.state.push("refresh")
        finally:
            self.state.end_read()

    # ---------- 消息 ----------
    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAY:
                if lparam == WM_LBUTTONUP:
                    self.request_refresh()
                elif lparam == WM_RBUTTONUP:
                    self.state.push("show_panel")
                return 0
            if msg == WM_TIMER and wparam == TIMER_ID:
                self.request_refresh()
                return 0
            if msg == WM_REFRESH_NOW:
                threading.Thread(target=self._read_worker, daemon=True).start()
                return 0
            if msg == WM_REFRESH_DONE:
                self._apply_state()
                return 0
            if msg == WM_SET_INTERVAL:
                user32.KillTimer(hwnd, TIMER_ID)
                user32.SetTimer(hwnd, TIMER_ID, int(wparam) * 1000, None)
                return 0
            if msg == WM_SHOW_PANEL:
                self.state.push("show_panel")
                return 0
            if msg == WM_CLOSE:
                self.state.push("quit")
                self._cleanup()
                return 0
            if msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
        except Exception:
            pass
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _cleanup(self) -> None:
        user32.KillTimer(self.hwnd, TIMER_ID)
        nid = self._nid(0)
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        if self.icon:
            user32.DestroyIcon(self.icon)
            self.icon = None
        user32.DestroyWindow(self.hwnd)

    # ---------- 生命周期 ----------
    def _run(self) -> None:
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = config.WINDOW_CLASS
        if not user32.RegisterClassExW(ctypes.byref(wc)):
            if ctypes.get_last_error() != 1410:
                return
        self.hwnd = user32.CreateWindowExW(
            0, config.WINDOW_CLASS, config.APP_TITLE, 0,
            0, 0, 0, 0, None, None, kernel32.GetModuleHandleW(None), None)
        if not self.hwnd:
            return

        self.icon_size = dpi.small_icon_size()
        self.icon = make_icon(None, None, self.icon_size)
        self._add_icon()
        user32.SetTimer(self.hwnd, TIMER_ID, self.state.get_interval() * 1000, None)
        self._ready.set()
        user32.PostMessageW(self.hwnd, WM_REFRESH_NOW, 0, 0)

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()
        self._ready.wait(3)
