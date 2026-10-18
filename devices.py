"""两个设备的电量读取逻辑（与 UI 完全解耦）。"""
from __future__ import annotations

import time

import config
from hid_api import HidDevice, HidError, find_interface


def read_mouse() -> int | None:
    """M3 2.4G 接收器：feature 0x51，opcode 0x06，电量在回复 [10]。"""
    it = find_interface(config.MOUSE_VID, config.MOUSE_PID, config.MOUSE_IFACE_HINT)
    if it is None:
        return None

    try:
        with HidDevice(it.path) as dev:
            # 先用 opcode 0x03（bond info，无需 ACK）刷新缓冲区，
            # 避免读到上一次 0x06 的陈旧回复。
            try:
                dev.set_feature(bytes([config.MOUSE_FEATURE_RID, config.MOUSE_OPCODE_BOND]
                                      + [0x00] * 19))
                time.sleep(0.03)
                dev.get_feature(config.MOUSE_FEATURE_RID, config.MOUSE_FEATURE_LEN)
            except HidError:
                pass

            dev.set_feature(bytes([config.MOUSE_FEATURE_RID, config.MOUSE_OPCODE_BATTERY]
                                  + [0x00] * 19))

            deadline = time.monotonic() + config.MOUSE_REPLY_TIMEOUT
            while time.monotonic() < deadline:
                try:
                    raw = dev.get_feature(config.MOUSE_FEATURE_RID, config.MOUSE_FEATURE_LEN)
                except HidError:
                    time.sleep(0.02)
                    continue
                body = raw[1:]
                if (len(body) > config.MOUSE_BATTERY_OFFSET
                        and body[0] == config.MOUSE_OPCODE_BATTERY
                        and body[1] == 0x01):
                    level = body[config.MOUSE_BATTERY_OFFSET]
                    if 0 <= level <= 100:
                        return level
                time.sleep(0.02)
    except (HidError, OSError):
        return None
    return None


def read_keyboard() -> int | None:
    """N87 接收器：feature 0xF7 状态，电量在回复 [1]。"""
    it = find_interface(config.KB_VID, config.KB_PID, config.KB_IFACE_HINT)
    if it is None:
        return None

    try:
        with HidDevice(it.path) as dev:
            dev.set_feature(bytes([config.KB_FEATURE_RID, config.KB_OPCODE_STATUS]
                                  + [0x00] * 63))
            time.sleep(config.KB_REPLY_WAIT)
            for _ in range(3):
                try:
                    raw = dev.get_feature(config.KB_FEATURE_RID, config.KB_FEATURE_LEN)
                except HidError:
                    time.sleep(0.05)
                    continue
                body = raw[1:]
                if len(body) > config.KB_ONLINE_OFFSET:
                    level = body[config.KB_BATTERY_OFFSET]
                    if 0 <= level <= 100:
                        return level
                time.sleep(0.05)
    except (HidError, OSError):
        return None
    return None


if __name__ == "__main__":
    print("mouse   :", read_mouse())
    print("keyboard:", read_keyboard())
