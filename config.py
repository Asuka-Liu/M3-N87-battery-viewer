"""集中配置：换设备时只改这里。

协议来源（公开文档）：
  鼠标 M3  : darmoshark-m3-configurator/docs/PROTOCOL.md
  键盘 N87 : sharkfin/docs/PROTOCOL.md（ROYUAN / YC3121 方案）
"""

# ---------------- 鼠标：Darmoshark M3 2.4G 接收器 ----------------
MOUSE_VID = 0x248A
MOUSE_PID = 0xFF30
MOUSE_IFACE_HINT = "MI_01"
MOUSE_FEATURE_RID = 0x51
MOUSE_FEATURE_LEN = 21
MOUSE_OPCODE_BOND = 0x03
MOUSE_OPCODE_BATTERY = 0x06
MOUSE_BATTERY_OFFSET = 10
MOUSE_REPLY_TIMEOUT = 0.35

# ---------------- 键盘：腹灵 N87 2.4G 接收器 ----------------
KB_VID = 0x3151
KB_PID = 0x4011
KB_IFACE_HINT = "MI_02"
KB_FEATURE_RID = 0x00
KB_FEATURE_LEN = 65
KB_OPCODE_STATUS = 0xF7
KB_BATTERY_OFFSET = 1
KB_ONLINE_OFFSET = 3
KB_REPLY_WAIT = 0.12

# ---------------- 程序行为 ----------------
POLL_SECONDS = 300

APP_NAME = "BatteryTray"
APP_TITLE = "外设电量"
DEBUG = False
MUTEX_NAME = "Local\\BatteryTray_SingleInstance"
WINDOW_CLASS = "BatteryTrayHiddenWindow"
STARTUP_LNK_NAME = "BatteryTray.lnk"

ICON_ID = 1

DEVICE_MOUSE_NAME = "达摩鲨M3"
DEVICE_KEYBOARD_NAME = "腹灵N87樱之恋"
SOURCE_MOUSE = "M3 接收器 · 2.4G · feature 0x51 / opcode 0x06"
SOURCE_KEYBOARD = "N87 接收器 · 2.4G · feature 0xF7 状态"
SOURCE_UNKNOWN = "未找到设备"
