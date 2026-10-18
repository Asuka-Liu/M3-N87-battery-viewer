"""Windows HID 访问层：只用 ctypes 调 setupapi.dll / hid.dll / kernel32.dll。

不依赖 hidapi / pywin32。读取厂商 feature report 只需要：
  SetupDiGetClassDevsW -> SetupDiEnumDeviceInterfaces -> CreateFileW
  -> HidD_GetPreparsedData / HidP_GetCaps -> HidD_GetFeature / HidD_SetFeature
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x01
FILE_SHARE_WRITE = 0x02
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
HIDP_STATUS_SUCCESS = 0x00110000


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD), ("Reserved", ctypes.c_void_p),
    ]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", wintypes.ULONG), ("VendorID", wintypes.USHORT),
        ("ProductID", wintypes.USHORT), ("VersionNumber", wintypes.USHORT),
    ]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wintypes.USHORT), ("UsagePage", wintypes.USHORT),
        ("InputReportByteLength", wintypes.USHORT),
        ("OutputReportByteLength", wintypes.USHORT),
        ("FeatureReportByteLength", wintypes.USHORT),
        ("Reserved", wintypes.USHORT * 17),
        ("NumberLinkCollectionNodes", wintypes.USHORT),
        ("NumberInputButtonCaps", wintypes.USHORT),
        ("NumberInputValueCaps", wintypes.USHORT),
        ("NumberInputDataIndices", wintypes.USHORT),
        ("NumberOutputButtonCaps", wintypes.USHORT),
        ("NumberOutputValueCaps", wintypes.USHORT),
        ("NumberOutputDataIndices", wintypes.USHORT),
        ("NumberFeatureButtonCaps", wintypes.USHORT),
        ("NumberFeatureValueCaps", wintypes.USHORT),
        ("NumberFeatureDataIndices", wintypes.USHORT),
    ]


# {4D1E55B2-F16F-11CF-88CB-001111000030}
HID_GUID = GUID(0x4D1E55B2, 0xF16F, 0x11CF,
                (ctypes.c_ubyte * 8)(0x88, 0xCB, 0x00, 0x11, 0x11, 0x00, 0x00, 0x30))

setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [
    ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID),
    wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
    ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

hid.HidD_GetAttributes.restype = wintypes.BOOL
hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetPreparsedData.restype = wintypes.BOOL
hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_FreePreparsedData.restype = wintypes.BOOL
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidP_GetCaps.restype = ctypes.c_long
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidD_GetFeature.restype = wintypes.BOOL
hid.HidD_GetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]
hid.HidD_SetFeature.restype = wintypes.BOOL
hid.HidD_SetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]


class HidError(OSError):
    pass


@dataclass
class HidInterface:
    path: str
    vendor_id: int
    product_id: int
    usage_page: int
    usage: int
    feature_len: int
    input_len: int
    output_len: int


def _open(path: str, access: int):
    h = kernel32.CreateFileW(path, access, FILE_SHARE_READ | FILE_SHARE_WRITE,
                             None, OPEN_EXISTING, 0, None)
    if h == INVALID_HANDLE_VALUE:
        return None
    return h


def _caps(handle):
    pp = ctypes.c_void_p()
    if not hid.HidD_GetPreparsedData(handle, ctypes.byref(pp)):
        return None
    try:
        caps = HIDP_CAPS()
        return caps if hid.HidP_GetCaps(pp, ctypes.byref(caps)) == HIDP_STATUS_SUCCESS else None
    finally:
        hid.HidD_FreePreparsedData(pp)


def enumerate_hid() -> list[HidInterface]:
    """枚举当前在线的所有 HID 接口。"""
    out: list[HidInterface] = []
    devs = setupapi.SetupDiGetClassDevsW(ctypes.byref(HID_GUID), None, None,
                                         DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if not devs or devs == INVALID_HANDLE_VALUE:
        return out
    try:
        index = 0
        while True:
            iface = SP_DEVICE_INTERFACE_DATA()
            iface.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            if not setupapi.SetupDiEnumDeviceInterfaces(
                    devs, None, ctypes.byref(HID_GUID), index, ctypes.byref(iface)):
                break
            index += 1
            need = wintypes.DWORD(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(
                devs, ctypes.byref(iface), None, 0, ctypes.byref(need), None)
            if not need.value:
                continue
            buf = ctypes.create_string_buffer(need.value)
            ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = 8
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(
                    devs, ctypes.byref(iface), buf, need.value, None, None):
                continue
            path = ctypes.cast(ctypes.addressof(buf) + 4, ctypes.c_wchar_p).value or ""
            if not path:
                continue
            h = _open(path, 0)
            if not h:
                continue
            try:
                attrs = HIDD_ATTRIBUTES()
                attrs.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
                if not hid.HidD_GetAttributes(h, ctypes.byref(attrs)):
                    continue
                caps = _caps(h)
                out.append(HidInterface(
                    path=path,
                    vendor_id=attrs.VendorID,
                    product_id=attrs.ProductID,
                    usage_page=caps.UsagePage if caps else 0,
                    usage=caps.Usage if caps else 0,
                    feature_len=caps.FeatureReportByteLength if caps else 0,
                    input_len=caps.InputReportByteLength if caps else 0,
                    output_len=caps.OutputReportByteLength if caps else 0,
                ))
            finally:
                kernel32.CloseHandle(h)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(devs)
    return out


def find_interface(vid: int, pid: int, hint: str) -> HidInterface | None:
    for it in enumerate_hid():
        if it.vendor_id == vid and it.product_id == pid and hint.lower() in it.path.lower():
            return it
    return None


class HidDevice:
    """一个打开的 HID 句柄，只做 feature report 读写。"""

    def __init__(self, path: str):
        self.handle = _open(path, GENERIC_READ | GENERIC_WRITE)
        if not self.handle:
            self.handle = _open(path, 0)
        if not self.handle:
            raise HidError(f"无法打开设备 (err={ctypes.get_last_error()})")

    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def get_feature(self, report_id: int, length: int) -> bytes:
        buf = ctypes.create_string_buffer(length)
        buf[0] = bytes([report_id & 0xFF])
        if not hid.HidD_GetFeature(self.handle, buf, length):
            raise HidError(f"读 feature 0x{report_id:02X} 失败")
        return buf.raw

    def set_feature(self, data: bytes) -> None:
        buf = ctypes.create_string_buffer(bytes(data), len(data))
        if not hid.HidD_SetFeature(self.handle, buf, len(data)):
            raise HidError("写 feature 失败")
