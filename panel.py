"""简洁面板：按参考图重做（纵向卡片、大号百分比、细进度条、无边框圆角）。"""
from __future__ import annotations

import ctypes
import tkinter as tk
import tkinter.font as tkfont

import config
import dpi
import win_link

BG = "#1b1b1e"
CARD = "#26262a"
BORDER = "#34343a"
FG = "#f2f3f5"
MUTED = "#8b8d93"
TRACK = "#3a3a40"


def color_for(level):
    if level is None:
        return "#6b7280"
    if level >= 60:
        return "#3ccb5f"
    if level >= 30:
        return "#e6b800"
    return "#e5484d"


def _round_rect(canvas, x1, y1, x2, y2, r, **kw):
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


class Card(tk.Canvas):
    def __init__(self, parent, title, source, scale=1.0):
        self.scale = scale
        self.w = int(512 * scale)
        self.h = int(126 * scale)
        super().__init__(parent, width=self.w, height=self.h,
                         bg=BG, highlightthickness=0, bd=0)
        s = scale
        pad = int(18 * s)
        _round_rect(self, 1, 1, self.w - 1, self.h - 1, int(12 * s),
                    fill=CARD, outline=BORDER, width=1)
        self.create_text(pad, int(16 * s), text=title, anchor="nw",
                         font=("Microsoft YaHei UI", 13, "bold"), fill=FG)
        self.create_text(pad, int(42 * s), text=source, anchor="nw",
                         font=("Microsoft YaHei UI", 9), fill=MUTED)
        self.num = self.create_text(self.w - int(46 * s), int(62 * s), text="--",
                                    anchor="e", font=("Segoe UI", 32, "bold"),
                                    fill=MUTED)
        self.pct = self.create_text(self.w - int(44 * s), int(76 * s), text="%",
                                    anchor="w", font=("Microsoft YaHei UI", 10),
                                    fill=MUTED)
        y = int(100 * s)
        self.bar_x1, self.bar_x2, self.bar_y = pad, self.w - pad, y
        self.bar_w = max(3, int(5 * s))
        self.create_line(pad, y, self.w - pad, y, width=self.bar_w,
                         capstyle=tk.ROUND, fill=TRACK)
        self.fill = self.create_line(pad, y, pad, y, width=self.bar_w,
                                     capstyle=tk.ROUND, fill=color_for(None))
        self.tick = self.create_line(pad, y, pad, y, width=max(2, int(3 * s)),
                                     capstyle=tk.ROUND, fill=color_for(None))
        self._level = None

    def update(self, info):
        level = info.battery
        self._level = level
        s = self.scale
        if level is None:
            self.itemconfigure(self.num, text="--", fill=MUTED)
            self.itemconfigure(self.fill, state="hidden")
            self.itemconfigure(self.tick, state="hidden")
            return
        color = color_for(level)
        self.itemconfigure(self.num, text=str(level), fill=FG)
        self.itemconfigure(self.fill, state="normal", fill=color)
        self.itemconfigure(self.tick, state="normal", fill=color)
        end = self.bar_x1 + (self.bar_x2 - self.bar_x1) * level / 100.0
        self.coords(self.fill, self.bar_x1, self.bar_y, end, self.bar_y)
        self.coords(self.tick, end, self.bar_y - int(7 * s), end, self.bar_y + int(7 * s))


class Panel:
    def __init__(self, root: tk.Tk, state, tray, on_exit, on_debug):
        self.root = root
        self.state = state
        self.tray = tray
        self.on_exit = on_exit
        self.on_debug = on_debug
        self.visible = False
        self._exiting = False
        self._placed = False
        self._drag = (0, 0)

        dpi_px = dpi.dpi_for(root.winfo_id())
        self.scale = dpi_px / 96.0
        try:
            root.tk.call("tk", "scaling", dpi_px / 72.0)
        except Exception:
            pass
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(name).configure(size=9)
            except Exception:
                pass

        s = self.scale
        self._s = s
        root.title(config.APP_TITLE)
        root.configure(bg=BG)
        root.overrideredirect(True)
        root.resizable(False, False)
        root.withdraw()

        pad = int(24 * s)
        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=pad, pady=(int(16 * s), int(6 * s)))

        title_box = tk.Frame(header, bg=BG)
        title_box.pack(side="left")
        title = tk.Label(title_box, text="外设电量", bg=BG, fg=FG,
                         font=("Microsoft YaHei UI", 20, "bold"))
        title.pack(anchor="w")
        subtitle = tk.Label(title_box,
                            text=f"2.4G 无线外设 · 每 {config.POLL_SECONDS // 60} 分钟自动刷新",
                            bg=BG, fg=MUTED, font=("Microsoft YaHei UI", 9))
        subtitle.pack(anchor="w", pady=(int(2 * s), 0))

        close = tk.Label(header, text="×", bg=BG, fg=MUTED,
                         font=("Segoe UI", 16), cursor="hand2")
        close.pack(side="right", anchor="n")
        close.bind("<Button-1>", lambda e: self.hide())
        close.bind("<Enter>", lambda e: close.configure(fg=FG))
        close.bind("<Leave>", lambda e: close.configure(fg=MUTED))

        for w in (header, title_box, title, subtitle):
            w.bind("<Button-1>", self._start_move)
            w.bind("<B1-Motion>", self._do_move)

        self.mouse_card = Card(root, config.DEVICE_MOUSE_NAME, config.SOURCE_MOUSE, s)
        self.mouse_card.pack(padx=pad, pady=(int(8 * s), int(10 * s)))
        self.kb_card = Card(root, config.DEVICE_KEYBOARD_NAME, config.SOURCE_KEYBOARD, s)
        self.kb_card.pack(padx=pad, pady=(0, int(4 * s)))

        bottom = tk.Frame(root, bg=BG)
        bottom.pack(fill="x", padx=pad, pady=(int(10 * s), int(14 * s)))

        self.updated_label = tk.Label(bottom, text="上次更新 --:--:--", bg=BG, fg=MUTED,
                                      font=("Microsoft YaHei UI", 9))
        self.updated_label.pack(side="left")

        btn_exit = tk.Button(bottom, text="退出", command=self._exit, bg=BG, fg=FG,
                             activebackground=CARD, activeforeground=FG,
                             bd=0, highlightthickness=1, highlightbackground=BORDER,
                             padx=int(14 * s), pady=int(5 * s),
                             font=("Microsoft YaHei UI", 9), cursor="hand2")
        btn_exit.pack(side="right")

        btn_debug = tk.Button(bottom, text="调试", command=self.on_debug, bg=CARD, fg=FG,
                              activebackground="#33333a", activeforeground=FG,
                              bd=0, highlightthickness=0,
                              padx=int(14 * s), pady=int(5 * s),
                              font=("Microsoft YaHei UI", 9), cursor="hand2")
        btn_debug.pack(side="right", padx=(0, int(8 * s)))

        self.autostart_var = tk.BooleanVar(value=win_link.is_enabled())
        cb = tk.Checkbutton(bottom, text="开机自启", variable=self.autostart_var,
                            command=self._on_autostart, bg=BG, fg=FG,
                            activebackground=BG, activeforeground=FG,
                            selectcolor=CARD, bd=0, highlightthickness=0,
                            font=("Microsoft YaHei UI", 9), cursor="hand2")
        cb.pack(side="right", padx=(0, int(10 * s)))

        root.bind("<Escape>", lambda e: self.hide())
        root.after(80, self._pump)

    # ---------- 窗口 ----------
    def _start_move(self, event):
        self._drag = (event.x_root - self.root.winfo_x(),
                      event.y_root - self.root.winfo_y())

    def _do_move(self, event):
        self.root.geometry(f"+{event.x_root - self._drag[0]}+{event.y_root - self._drag[1]}")

    def _round_window(self):
        try:
            self.root.update_idletasks()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            r = int(14 * self.scale)
            try:
                frame = int(self.root.wm_frame(), 16)
            except Exception:
                frame = self.root.winfo_id()

            # Win11 DWM 圆角（平滑）
            try:
                dwm = ctypes.WinDLL("dwmapi")
                pref = ctypes.c_int(2)  # DWMWCP_ROUND
                dwm.DwmSetWindowAttribute(ctypes.c_void_p(frame), 33,
                                          ctypes.byref(pref), ctypes.sizeof(pref))
            except Exception:
                pass

            # 兜底：圆角窗口区域（64 位句柄必须声明 argtypes）
            gdi32 = ctypes.WinDLL("gdi32")
            user32 = ctypes.WinDLL("user32")
            gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
            gdi32.CreateRoundRectRgn.restype = ctypes.c_void_p
            user32.SetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
            user32.SetWindowRgn.restype = ctypes.c_int
            rgn = gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, r, r)
            ok = user32.SetWindowRgn(ctypes.c_void_p(frame), ctypes.c_void_p(rgn), True)
            if config.DEBUG:
                print(f"[round] frame={frame} size={w}x{h} r={r} setrgn={ok}", flush=True)
        except Exception as e:
            if config.DEBUG:
                print(f"[round] failed: {e}", flush=True)

    def show(self):
        self.root.deiconify()
        if not self._placed:
            self.root.update_idletasks()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            self.root.geometry(f"+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2)}")
            self._placed = True
        self._round_window()
        self.root.lift()
        self.root.focus_force()
        self.visible = True
        self._refresh_view()

    def hide(self):
        self.root.withdraw()
        self.visible = False

    # ---------- 动作 ----------
    def _exit(self):
        if self._exiting:
            return
        self._exiting = True
        self.tray.quit()
        self.on_exit()

    def _on_autostart(self):
        if self.autostart_var.get():
            if not win_link.enable():
                self.autostart_var.set(False)
        else:
            win_link.disable()

    def _refresh_view(self):
        mouse, keyboard, _ = self.state.snapshot()
        self.mouse_card.update(mouse)
        self.kb_card.update(keyboard)
        when = max(mouse.updated, keyboard.updated) if (mouse.updated or keyboard.updated) else ""
        self.updated_label.configure(text=f"上次更新 {when}" if when else "上次更新 --:--:--")

    def _pump(self):
        try:
            while True:
                msg = self.state.ui_queue.get_nowait()
                if msg == "show_panel":
                    self.show()
                elif msg == "refresh" and self.visible:
                    self._refresh_view()
                elif msg == "quit":
                    self._exit()
                    return
        except Exception:
            pass
        self.root.after(80, self._pump)
