你是一个熟悉 Windows 底层开发的工程师，擅长用 Python `ctypes` 直接调用系统 DLL。
请帮我做一个 **Windows 10/11 上的无线外设电量小工具**，要求如下。

## 一、硬性约束

1. **零第三方依赖**：只用 Python 标准库 + `ctypes`（GUI 用 `tkinter`）。
   不要用 hidapi、pystray、Pillow、pywin32。
2. **三种形态**：
   - 简洁面板：两张纵向卡片（大号百分比 + 细进度条 + 数据来源）。
   - 托盘常驻：单个图标，两个同心圆环，外环鼠标/内环键盘，弧长 = 电量。
   - 完整调试版：列出 HID 接口、转储 Feature Report、探测 Report ID、
     试发命令、手动标定协议。
3. **托盘交互**：右键图标 → 打开/前置面板（已开不重复）；左键 → 立刻刷新；
   悬停 tooltip 显示两台设备电量与更新时间。
4. **低 CPU**：用 `SetTimer` 驱动刷新，固定 5 分钟；空闲时不轮询、不 sleep 循环；
   读取放后台线程，界面不卡。
5. **开机自启**：启动文件夹里的 `.lnk`（纯 ctypes COM `IShellLink`），
   任务管理器 →「启动」可见、可禁用。
6. **不写任何日志文件**：只有 `--debug` 时才分配控制台并输出。
7. **退出必须干净**：`NIM_DELETE` → `DestroyWindow` → `PostQuitMessage(0)` → Tk `quit`，
   不能留下「图标没了、进程还在」的僵尸进程。
8. **高 DPI**：Per-Monitor V2，按 `GetDpiForWindow()` 缩放面板，托盘图标按
   `GetSystemMetricsForDpi(SM_CXSMICON)` 渲染。

## 二、要读的两台设备

| 设备 | VID:PID | 说明 |
|---|---|---|
| 达摩鲨 M3 鼠标 | `248A:FF30` | 2.4G TYPE-A 接收器，命令接口 `MI_01` |
| 腹灵 N87 键盘 | `3151:4011` | 2.4G 接收器，vendor 接口 `MI_02` |

## 三、已验证的协议（直接照抄，不用再逆向）

### 1) M3 鼠标（`248A:FF30` MI_01，usage page `0x8C`）

- feature report `0x51`，总长 21 字节（1 字节 report id + 20 字节负载）。
- 先发 `opcode 0x03`（bond info，无需 ACK）刷新缓冲区，再发 `0x06`：

  ```
  SET feature 0x51:  51 06 00 × 19
  GET feature 0x51:  21 字节
  ```

- 回复（去掉 report id 后）：

  ```
  [0]  0x06 (echo)
  [1]  0x01 (status ok)
  [7..8] firmware 0x0209 → 2.0.9
  [10] 电量百分比
  ```

- 接收器会在 input report `0x54` 回 ACK：`54 E4 <status>`。
  `status=1` 就绪、`2` 鼠标休眠、`4` 忙；读 feature 前要校验 echo，避免读到上一条的陈旧回复。
- 鼠标休眠时读不到，动一下即可恢复。

### 2) N87 键盘（`3151:4011` MI_02，usage page `0xFFFF`）

- feature report `0x00`，总长 65 字节（无 report id，首字节就是 `0x00`）。

  ```
  SET feature 0x00:  00 F7 00 × 63
  等待约 120 ms
  GET feature 0x00:  65 字节
  ```

- 回复（去掉首字节 report id 后）：

  ```
  [1] 键盘电量百分比
  [3] == 0 表示键盘在线
  [4] == 0 表示接收器侧鼠标在线（N87 接收器没配鼠标，通常为 1）
  ```

- 键盘离线时接收器仍返回缓存电量，可正常显示。

### 3) 兜底（换设备时用）

标准 HID Battery Strength（`0x0006/0x0020`）→ 监听 Input Report →
厂商协议试探 → 手动标定（Report ID / 电量下标 / 倍率存成 JSON）。

## 四、已知的坑（务必规避）

1. **feature 缓冲区是滞后的**：发命令后立刻 GET 可能拿到上一条回复。
   先发一个不同 opcode 的读（如 M3 的 `0x03`）刷新，再发目标命令，并校验 echo。
2. **不要向 M3 的输出通道 `0xB2` 发未知命令**：会静默丢失接收器配置链路，
   表现为所有命令 `read error`，只能拔插接收器恢复。只发只读查询。
3. **接收器会丢配置链路**：鼠标还能用，但命令全不应答；拔插接收器是唯一恢复方式。
4. **64 位 ctypes 句柄必须声明 argtypes/restype**，否则 `SetWindowRgn`、
   `CreateRoundRectRgn` 这类接口的句柄会被截断，圆角/区域静默失效。
5. **Tkinter 不是线程安全的**：后台线程不要直接调 Tk；用 `queue.Queue` +
   主线程 `after(80, pump)`。
6. **销毁托盘窗口后必须 `PostQuitMessage(0)`**，否则留下僵尸进程并占着单实例锁。
7. **不做 DPI 感知会糊**：`SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)`，
   按 DPI 缩放字体与像素尺寸。
8. **低完整性目录无法注册托盘**：`Shell_NotifyIconW` 返回 `error 5`，
   PyInstaller 也可能无法在 `%TEMP%` 解压；把 EXE 放到普通目录。

## 五、验收标准

1. `python main.py --panel` 能看到两张卡片，百分比与官方软件一致。
2. 右键托盘打开面板、左键刷新、悬停显示两台设备电量与更新时间。
3. 每 5 分钟自动刷新，失败显示 `--`，不弹窗、不写日志、不退出。
4. 面板在 150% 缩放下文字锐利、卡片不裁切、窗口圆角。
5. 退出后无残留进程、无残留托盘图标；连续启停 3 次正常。
6. 空闲 CPU 接近 0，托盘内存约 29 MB（打开面板后约 86 MB）。
