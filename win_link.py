"""在「启动」文件夹创建/删除 .lnk（纯 ctypes COM，不依赖 pywin32）。

任务管理器 →「启动」标签能看到、能启用/禁用。
"""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

ole32 = ctypes.WinDLL("ole32")
shell32 = ctypes.WinDLL("shell32")

CLSCTX_INPROC_SERVER = 1
S_OK = 0


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8),
    ]


CLSID_ShellLink = GUID(0x00021401, 0x0000, 0x0000,
                       (ctypes.c_ubyte * 8)(0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46))
IID_IShellLinkW = GUID(0x000214F9, 0x0000, 0x0000,
                       (ctypes.c_ubyte * 8)(0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46))
IID_IPersistFile = GUID(0x0000010B, 0x0000, 0x0000,
                        (ctypes.c_ubyte * 8)(0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46))

ole32.CoInitialize.argtypes = [ctypes.c_void_p]
ole32.CoCreateInstance.argtypes = [
    ctypes.POINTER(GUID), ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]

HRESULT = ctypes.c_long
WSTR = wintypes.LPCWSTR


def startup_dir() -> str:
    return os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")


def shortcut_path() -> str:
    return os.path.join(startup_dir(), "BatteryTray.lnk")


def is_enabled() -> bool:
    return os.path.exists(shortcut_path())


def _target_and_args() -> tuple[str, str, str]:
    if getattr(sys, "frozen", False):
        exe = sys.executable
        return exe, "", os.path.dirname(exe)
    exe = sys.executable
    script = os.path.abspath(sys.argv[0])
    return exe, f'"{script}"', os.path.dirname(script)


def enable() -> bool:
    """创建启动文件夹快捷方式；成功返回 True。"""
    path = shortcut_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        return True

    ole32.CoInitialize(None)
    link = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(ctypes.byref(CLSID_ShellLink), None,
                                CLSCTX_INPROC_SERVER,
                                ctypes.byref(IID_IShellLinkW), ctypes.byref(link))
    if hr != S_OK or not link:
        return False
    try:
        vtable = ctypes.cast(link, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents

        target, args, workdir = _target_and_args()

        set_path = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, WSTR)(vtable[20])
        set_args = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, WSTR)(vtable[11])
        set_workdir = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, WSTR)(vtable[9])
        set_desc = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, WSTR)(vtable[7])
        set_icon = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, WSTR, ctypes.c_int)(vtable[17])

        set_path(link, target)
        if args:
            set_args(link, args)
        set_workdir(link, workdir)
        set_desc(link, "外设电量托盘")
        set_icon(link, target, 0)

        persist = ctypes.c_void_p()
        query = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(GUID),
                                   ctypes.POINTER(ctypes.c_void_p))(vtable[0])
        if query(link, ctypes.byref(IID_IPersistFile), ctypes.byref(persist)) != S_OK:
            return False
        pv = ctypes.cast(persist, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        save = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, WSTR, wintypes.BOOL)(pv[6])
        save(persist, path, True)
        return os.path.exists(path)
    finally:
        release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(
            ctypes.cast(link, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents[2])
        release(link)


def disable() -> bool:
    path = shortcut_path()
    try:
        if os.path.exists(path):
            os.remove(path)
        return True
    except OSError:
        return False
