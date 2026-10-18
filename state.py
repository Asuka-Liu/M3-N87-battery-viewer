"""进程内共享状态：后台读取线程、托盘线程、Tk 主线程都通过它交换数据。"""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, replace


@dataclass
class DeviceInfo:
    battery: int | None = None
    updated: str = ""
    error: str = ""


class AppState:
    def __init__(self, interval: int):
        self.lock = threading.Lock()
        self.mouse = DeviceInfo()
        self.keyboard = DeviceInfo()
        self.interval = interval
        self.reading = False
        self.ui_queue: queue.Queue = queue.Queue()

    def snapshot(self):
        with self.lock:
            return (replace(self.mouse), replace(self.keyboard), self.interval)

    def set_result(self, mouse: DeviceInfo, keyboard: DeviceInfo) -> None:
        with self.lock:
            self.mouse = mouse
            self.keyboard = keyboard

    def set_interval(self, seconds: int) -> None:
        with self.lock:
            self.interval = seconds

    def get_interval(self) -> int:
        with self.lock:
            return self.interval

    def try_begin_read(self) -> bool:
        with self.lock:
            if self.reading:
                return False
            self.reading = True
            return True

    def end_read(self) -> None:
        with self.lock:
            self.reading = False

    def push(self, message) -> None:
        self.ui_queue.put(message)
