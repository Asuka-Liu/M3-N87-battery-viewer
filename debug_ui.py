"""完整调试版：枚举 HID、转储 Feature、探测 Report ID、试发命令、手动标定。

只在用户从面板点「调试」或启动参数 --debug-ui 时创建。
"""
from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk

import config
import dpi
import hid_api

BG = "#1e1f22"
CARD = "#2b2d31"
FG = "#f2f3f5"
MUTED = "#9aa0a6"


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def calibration_path() -> str:
    return os.path.join(app_dir(), "calibration.json")


class DebugWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        dpi_px = dpi.dpi_for(master.winfo_id())
        self.scale = dpi_px / 96.0
        try:
            master.tk.call("tk", "scaling", dpi_px / 72.0)
        except Exception:
            pass
        self.title("HID 调试 / 标定")
        self.configure(bg=BG)
        self.geometry(f"{int(980 * self.scale)}x{int(680 * self.scale)}")
        self.interfaces = []

        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=10, pady=8)
        for text, cmd in (
            ("刷新列表", self.refresh),
            ("转储 Feature", self.dump_feature),
            ("探测 Report ID", self.probe_report_ids),
        ):
            ttk.Button(top, text=text, command=cmd).pack(side="left", padx=4)
        self.info = tk.Label(top, text="", bg=BG, fg=MUTED,
                             font=("Microsoft YaHei UI", 9))
        self.info.pack(side="left", padx=10)

        cols = ("vidpid", "usage", "lens", "path")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        try:
            ttk.Style(self).configure("Treeview", rowheight=int(20 * self.scale))
        except Exception:
            pass
        for c, w in zip(cols, (110, 120, 150, 580)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=int(w * self.scale), anchor="w")
        self.tree.pack(fill="x", padx=10)

        send = tk.LabelFrame(self, text="试发命令", bg=BG, fg=FG,
                             font=("Microsoft YaHei UI", 9))
        send.pack(fill="x", padx=10, pady=8)
        tk.Label(send, text="Report ID", bg=BG, fg=MUTED).pack(side="left", padx=(8, 2))
        self.rid = tk.Entry(send, width=6)
        self.rid.insert(0, "51")
        self.rid.pack(side="left")
        tk.Label(send, text="类型", bg=BG, fg=MUTED).pack(side="left", padx=(10, 2))
        self.kind = ttk.Combobox(send, width=8, state="readonly",
                                 values=["feature", "output"])
        self.kind.set("feature")
        self.kind.pack(side="left")
        tk.Label(send, text="数据(hex)", bg=BG, fg=MUTED).pack(side="left", padx=(10, 2))
        self.payload = tk.Entry(send, width=46)
        self.payload.insert(0, "06")
        self.payload.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(send, text="发送并读回复", command=self.send_command).pack(side="left", padx=6)

        cal = tk.LabelFrame(self, text="手动标定（保存到 calibration.json，下次启动生效）",
                            bg=BG, fg=FG, font=("Microsoft YaHei UI", 9))
        cal.pack(fill="x", padx=10)
        self.cal_entries = {}
        fields = [("设备", "mouse", 8), ("VID", "248A", 7), ("PID", "FF30", 7),
                  ("接口", "MI_01", 8), ("RID", "51", 5), ("opcode", "06", 6),
                  ("offset", "10", 5)]
        for label, default, width in fields:
            tk.Label(cal, text=label, bg=BG, fg=MUTED).pack(side="left", padx=(8, 2))
            e = tk.Entry(cal, width=width)
            e.insert(0, default)
            e.pack(side="left")
            self.cal_entries[label] = e
        ttk.Button(cal, text="保存标定", command=self.save_calibration).pack(side="left", padx=8)

        self.text = tk.Text(self, height=14, bg="#111214", fg="#d7dae0",
                            insertbackground=FG, font=("Consolas", 9))
        self.text.pack(fill="both", expand=True, padx=10, pady=8)

        self.refresh()

    # ---------- 列表 ----------
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        try:
            self.interfaces = hid_api.enumerate_hid()
        except Exception as e:
            self.log(f"枚举失败: {e}")
            return
        for i, it in enumerate(self.interfaces):
            self.tree.insert("", "end", iid=str(i), values=(
                f"{it.vendor_id:04X}:{it.product_id:04X}",
                f"0x{it.usage_page:04X}:0x{it.usage:04X}",
                f"F{it.feature_len}/I{it.input_len}/O{it.output_len}",
                it.path,
            ))
        self.info.configure(text=f"共 {len(self.interfaces)} 个接口")

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            self.log("请先在列表里选中一个接口")
            return None
        return self.interfaces[int(sel[0])]

    def log(self, text: str):
        self.text.insert("end", text + "\n")
        self.text.see("end")

    # ---------- 功能 ----------
    def dump_feature(self):
        it = self._selected()
        if not it:
            return
        if it.feature_len <= 0:
            self.log(f"{it.vendor_id:04X}:{it.product_id:04X} 没有 feature report")
            return
        self.log(f"== 转储 {it.vendor_id:04X}:{it.product_id:04X} feature (len={it.feature_len}) ==")
        try:
            with hid_api.HidDevice(it.path) as dev:
                for rid in list(range(0, 9)) + [0x51, 0x52, 0x53]:
                    try:
                        data = dev.get_feature(rid, it.feature_len)
                        self.log(f"  id=0x{rid:02X} OK  " + " ".join(f"{b:02X}" for b in data[:32]))
                    except Exception as e:
                        self.log(f"  id=0x{rid:02X} FAIL {e}")
        except Exception as e:
            self.log(f"  打开失败: {e}")

    def probe_report_ids(self):
        it = self._selected()
        if not it:
            return
        if it.output_len <= 0:
            self.log("该接口没有 output report")
            return
        if not messagebox.askyesno("确认", "会向该接口发送 0x00–0x20 的零报文，可能改变设备状态。继续？"):
            return
        self.log(f"== 探测 output report id (len={it.output_len}) ==")
        try:
            with hid_api.HidDevice(it.path) as dev:
                for rid in range(0x21):
                    payload = bytes([rid] + [0x00] * (it.output_len - 1))
                    try:
                        dev.write_output(payload)
                        self.log(f"  id=0x{rid:02X} 接受")
                    except Exception:
                        pass
        except Exception as e:
            self.log(f"  打开失败: {e}")

    def send_command(self):
        it = self._selected()
        if not it:
            return
        try:
            rid = int(self.rid.get(), 16)
            payload = bytes.fromhex(self.payload.get().replace(" ", ""))
        except ValueError:
            self.log("Report ID 或数据不是合法 hex")
            return
        kind = self.kind.get()
        self.log(f"== 发送 {kind} rid=0x{rid:02X} data={payload.hex(' ')} ==")
        try:
            with hid_api.HidDevice(it.path) as dev:
                if kind == "feature":
                    length = max(it.feature_len, len(payload) + 1)
                    body = bytes([rid]) + payload + bytes(length - 1 - len(payload))
                    dev.set_feature(body)
                    self.log("  已写入 feature")
                    try:
                        reply = dev.get_feature(rid, length)
                        self.log("  reply: " + " ".join(f"{b:02X}" for b in reply))
                    except Exception as e:
                        self.log(f"  读回复失败: {e}")
                else:
                    length = max(it.output_len, len(payload) + 1)
                    body = bytes([rid]) + payload + bytes(length - 1 - len(payload))
                    dev.write_output(body)
                    self.log("  已写入 output")
        except Exception as e:
            self.log(f"  发送失败: {e}")

    def save_calibration(self):
        e = self.cal_entries
        data = {
            "mouse": {
                "vid": e["VID"].get().strip(),
                "pid": e["PID"].get().strip(),
                "iface": e["接口"].get().strip(),
                "rid": e["RID"].get().strip(),
                "opcode": e["opcode"].get().strip(),
                "offset": e["offset"].get().strip(),
            },
            "note": "由调试版手动标定保存；启动时覆盖 config.py 对应参数",
        }
        try:
            with open(calibration_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log(f"已保存标定 -> {calibration_path()}")
        except Exception as ex:
            self.log(f"保存失败: {ex}")
