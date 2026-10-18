# M3 / N87 电量查看器

Windows 上读取两只 2.4G 外设电量的小工具。**纯 ctypes 调系统 DLL，零第三方依赖**——
不用 hidapi、不用 pystray、不用 Pillow、不用 pywin32，装了 Python 就能跑。

界面用 `tkinter`，托盘用 `Shell_NotifyIconW`，HID 用 `hid.dll` + `setupapi.dll`，
全部通过标准库 `ctypes` 直接调用。

## ⚠️ 只支持这两台设备

这**不是一个通用工具**。协议来自公开文档，并在真机上逐字节验证过——换成别的鼠标或键盘，
大概率一个字节都读不出来（界面会显示 `--`）。

| 设备 | VID:PID | 读取方式 |
|---|---|---|
| 达摩鲨 M3 鼠标 | `248A:FF30` | feature report `0x51`，opcode `0x06`；电量 = 回复去掉 report id 后 `[10]` |
| 腹灵 N87 键盘 | `3151:4011` | feature report `0xF7` 状态；电量 = 回复去掉 report id 后 `[1]`，`[3] == 0` 表示在线 |

**你的设备不在这两行里？** 别硬改这个仓库，往下看「用 prompt 做一份你自己的」。

## 三种形态

### 1. 简洁面板

无边框圆角窗口（Win11 DWM 圆角 + `SetWindowRgn` 兜底），拖动标题区可移动，右上角 `×` 收起面板。

纵向两张卡片：左侧设备图标（鼠标/键盘）、设备名、协议来源、右侧大号百分比（小号 `%`）、细进度条。
底部：上次更新时间、开机自启、调试、退出。

### 2. 托盘常驻

单个图标：两个同心圆环，**外环 = 鼠标、内环 = 键盘**，顺时针弧长 = 电量，
颜色随电量变化（≥60 绿 / 30–59 黄 / <30 红）。

- **右键图标** → 打开/前置面板（已开只前置，不重复创建）
- **左键图标** → 立刻刷新一次
- **悬停** → `达摩鲨M3：86% | 腹灵N87樱之恋：71%（22:45:07）`
- 任一设备电量低于 **15%** 时弹出「电量不足 / 请充电」通知；同一次低电量只提醒一次，回到 20% 以上后重置

### 3. 完整调试版

面板点「调试」或启动参数 `--debug-ui`：

- 列出所有 HID 接口（VID:PID、usage page/usage、feature/input/output 长度、完整路径）
- 转储 Feature Report（逐个 Report ID 读取并显示 hex）
- 探测 Report ID（向选中接口发 0x00–0x20 零报文，列出被接受的 ID；会二次确认）
- 试发命令（Report ID + hex 数据 + feature/output，发送并读回复）
- 手动标定（设备/VID/PID/接口/RID/opcode/offset 保存到 `calibration.json`）

## 使用方法

```bash
python main.py              # 托盘常驻
python main.py --panel      # 启动即显示面板
python main.py --debug      # 分配控制台并打印读取日志
python main.py --debug-ui   # 启动即打开调试窗口
```

打包成单文件 EXE：

```powershell
py -3 -m PyInstaller --noconfirm --clean --onefile --noconsole `
  --name BatteryTray --icon assets\battery.ico `
  --add-data "assets\battery.ico;assets" main.py
```

或直接运行 `build.ps1`。

### 版本资源与 MOTW

- 构建命令带 `--version-file version_info.txt`，保证 CompanyName / ProductName / FileVersion / OriginalFilename 非空。
- 构建后运行 `tools\strip-motw.ps1 -Path .\dist` 去除 MOTW，`-Verify` 复验应输出 `clean`。
- 一键脚本：`build.ps1`。
> 建议把 EXE 放在普通目录运行。低完整性目录（例如某些沙箱工作区）会导致
> `Shell_NotifyIconW` 返回 `error 5`，PyInstaller 也可能无法在 `%TEMP%` 解压。

## 用 prompt 做一份你自己的

这套东西的价值不在代码，在**方法**。下面这段 prompt 把探测过程、已验证协议和踩过的坑都写进去了，
交给一个**能动手的 Agent** 就能按你自己的设备重做一份。

> **为什么必须是 Agent，不能是聊天 AI？**
> 这不是「写点代码」的活：要枚举本机 HID 接口、读描述符、发 feature 命令、看真实回复、
> 再在真机上验证——每一步都得**实际在这台电脑上跑起来**。
> 纯聊天窗口只能给你一段猜出来的代码；能执行命令、能读写文件的 Agent 才调得通。
> （WorkBuddy / CodeBuddy / Cursor / Claude Code 这类都属于 Agent。）

1. **复制**下面折叠块里的 prompt（或直接打开 [`PROMPT.md`](PROMPT.md)）
2. **贴给一个 Agent**：关键是要能执行命令、读写文件
3. **换成你的设备**：把 prompt 里「要读的两台设备」替换掉。
   不知道 VID/PID 就这样查：设备管理器 → 右键设备 → 属性 → 详细信息 → 硬件 Id，
   会看到形如 `HID\VID_XXXX&PID_YYYY` 的值
4. **让它跑通**：如果读不到电量，用完整调试版的「转储 Feature / 探测 Report ID /
   试发命令」把真实偏移摸出来，再补回协议段

<details>
<summary><b>点开看完整 prompt（可直接复制）</b></summary>

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
3. 每 5 分钟自动刷新，读取失败显示 `--` 且不弹窗（低电量提醒除外），不写日志、不退出。
4. 面板在 150% 缩放下文字锐利、卡片不裁切、窗口圆角。
5. 退出后无残留进程、无残留托盘图标；连续启停 3 次正常。
6. 空闲 CPU 接近 0，托盘内存约 29 MB（打开面板后约 86 MB）。

</details>

## 环境要求

- Windows 10 / 11
- Python 3.10+（官方安装包自带 `tkinter`）
- 打包需要 `pyinstaller`

## 目录说明

| 文件 | 说明 |
|---|---|
| `config.py` | VID/PID、接口匹配、命令、字节偏移、刷新间隔，全部集中可改 |
| `hid_api.py` | HID 枚举 + feature/output 读写（纯 ctypes） |
| `devices.py` | 两个设备的电量读取逻辑（与 UI 解耦） |
| `state.py` | 线程共享状态 + UI 消息队列 |
| `tray.py` | 单图标托盘、`SetTimer`、同心圆环图标绘制 |
| `panel.py` | tkinter 无边框圆角面板 |
| `debug_ui.py` | 完整调试版 |
| `win_link.py` | 启动文件夹 `.lnk`（纯 ctypes COM） |
| `dpi.py` | Per-Monitor V2 DPI 感知与缩放 |
| `main.py` | 入口：单实例、控制台、Tk + 托盘线程 |
| `assets/make_icon.py` | 生成多尺寸圆环 `.ico`（不依赖 Pillow） |
| `docs/` | 协议来源文档（公开资料，原样收录） |
| `PROMPT.md` | 把整个项目整理成一份可复用的提示词 |

## 实现细节

1. **HID 读取的“陈旧回复”**：接收器的 feature 缓冲区在回复落地前一直是上一条内容。
   M3 先发 `0x03` 刷新再发 `0x06`，并校验 `[0] == 0x06 && [1] == 0x01`；N87 则是
   `0xF7` 状态查询后等 120 ms。
2. **同心圆环图标**：32×32（按系统小图标尺寸可到 16/20/24）的 BGRA 缓冲区，
   4× 超采样后降采样抗锯齿；外环鼠标、内环键盘，弧长按电量，颜色分档；
   `CreateDIBSection` + `CreateIconIndirect` 生成 HICON。
3. **无边框圆角**：`SetProcessDpiAwarenessContext` + `SetWindowRgn(CreateRoundRectRgn)`
   兜底，Win11 上再叠加 DWM `DWMWA_WINDOW_CORNER_PREFERENCE`。
4. **退出与单实例**：命名互斥量；退出时 `NIM_DELETE` → `DestroyWindow` →
   `PostQuitMessage`，同时把 `quit` 消息投递给 Tk 主线程，确保进程真正结束。

## 已知限制

- **鼠标休眠时读不到**：会显示 `--`，动一下鼠标或左键刷新即可恢复。
- **键盘离线时**：接收器仍返回缓存电量，程序照常显示。
- **不要向 M3 输出通道 `0xB2` 发未知命令**：会丢接收器配置链路，需拔插恢复。
- **接收器重新插拔后**设备路径会变，程序下次刷新会重新枚举，无需重启。
- tkinter 面板打开后约 86 MB 内存；不打开面板时约 29 MB。

## 隐私

- **不联网**：没有任何 http / socket / urllib / 遥测调用，所有读取都在本地 HID 层完成。
- **不写日志**：默认不产生任何日志文件；只有 `--debug` 时才分配控制台打印。
- **不上传**：设备路径、VID/PID 只在内存里用，不落盘。

## 致谢

本项目的**README 结构**、「用 prompt 做一份你自己的」这一节的思路，以及部分 Windows 底层
踩坑记录，借鉴了 [yszyszysz233/2.4G-battery-viewer](https://github.com/yszyszysz233/2.4G-battery-viewer)。

那个项目针对的是 ATK / VXE 鼠标与 DARKRIM 耳机，设备与协议都不同；本项目的两台设备、
协议、代码与调试版都是独立实现的，但「零第三方依赖 + 让 Agent 在真机上复现协议」的
方法论来自它，特此致谢。

## 说明

协议来自公开文档，并在真机上验证：

- 键盘（ROYUAN / YC 方案）：[`sharkfin/docs/PROTOCOL.md`](https://github.com/dniminenn/sharkfin/blob/master/docs/PROTOCOL.md)
- 鼠标（Darmoshark M3）：[`darmoshark-m3-configurator/docs/PROTOCOL.md`](https://github.com/Barba2k2/darmoshark-m3-configurator/blob/main/PROTOCOL.md)

本仓库**没有**逆向厂商二进制、没有抓包、没有调用 IDA/Ghidra；
只使用 Windows 标准 HID API（`hid.dll` / `setupapi.dll`）读取 feature report。

本项目与达摩鲨、腹灵、ROYUAN、Darmoshark 均无关联，仅供学习与个人使用。
