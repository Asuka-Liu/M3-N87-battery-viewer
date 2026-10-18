# Darmoshark M3 — configuration protocol (`dms` contract)

**English** · [Português](PROTOCOL.pt-BR.md)

Reverse engineered from the official WebHID configurator bundle
(`darmoshark.cc`, an Angular app built on the Keychron platform). The mouse sold
as **Attack Shark M3** identifies itself in firmware as **Darmoshark M3**.

## Identity

| Field | Value |
|---|---|
| VID:PID | `0x248A:0xFF12` (Telink) |
| vpId (catalogue) | `613089042` = `vid << 16 \| pid` |
| Official definition | `https://launcher.keychron.com/static/device/613089042/json/v3.json` |
| Metadata | `https://launcher.keychron.com/vapi/v2/product/613089042` |
| DPI | 50–26000, default levels 400/800/1600/3200/4800 |
| Report rates | 125 / 500 / 1000 Hz |

## HID channels

The mouse exposes different interfaces depending on how it is connected.

| Interface | Usage page | Role |
|---|---|---|
| 0 / 1 | `0x01`, `0x0C` | mouse / keyboard / consumer (generic) |
| 2 | `0x8C` | DFU **and** config over the cable — see below |
| receiver, iface 1 | `0x8C` | DFU **and** config over 2.4GHz — same descriptor |

The 2.4GHz receiver (`0x248A:0xFF30`, product string `RF Dongle`) enumerates
three interfaces and exposes **no vendor usage page of its own**: its config
interface carries the very same `0x8C` descriptor as the mouse does over the
cable. The pages `0xFF0A` / `0xFFC1` and the output reports `0xB3` / `0xB5`
belong to other models in the vendor bundle — on this hardware they exist
nowhere, and writing them reaches nothing.

Report ids of that descriptor, identical on both interfaces:

| Report | Kind | Size | Role |
|---|---|---|---|
| `0xB1` / `0xB2` | input / output | 32 B | DFU |
| `0x51` | feature | 20 B | identity over the cable, **config over the receiver** |
| `0x52` | feature | 64 B | config over the cable, long commands over the receiver |
| `0x53` | feature | 1000 B | unused here |
| `0x54` | input | 20 B | acknowledgements from the receiver |

Two transports carry the very same payloads:

| Operation | Cable (feature `0x52`) | Receiver (feature `0x51`) |
|---|---|---|
| Write configuration | ✅ works | ✅ works |
| Read configuration | ❌ always returns the identity block | ✅ works |
| Acknowledgement | none, writes are silent | `0xE4` on input `0x54` |
| DPI levels | 5 (short form only) | 5 |
| Bootloader read | the mouse's | the **receiver's** own |

> **A note on how this was nearly missed.** The cable interface was first
> dismissed as DFU-only because it stayed silent on a *read* command. But
> `setDpi` is fire-and-forget in the original protocol, so silence is the
> normal outcome of a **successful write**. Test the operation you actually
> need before concluding a channel does not support it.

Over the cable the USB endpoint already runs at 1000 Hz
(`ReportInterval = 1000 µs`), so `setReportRate` only has an observable effect
in the wireless modes.

## 2.4GHz receiver channel (feature `0x51`)

The commands are the same 20-byte payloads, sent as feature report `0x51`
(zero padded); anything longer goes as feature `0x52`, 64 bytes. Writes are
fire-and-forget, exactly as over the cable.

Reads are what the cable cannot do. The receiver answers on **input report
`0x54`** with an acknowledgement frame, and the reply itself is then fetched
from the feature report:

```
54 E4 <status> 00
```

The byte after the status is where the vendor bundle expects the echoed
opcode, but this receiver always sends `00` there: the acknowledgement does not
say which command it belongs to.

| Status | Meaning |
|---|---|
| 0 | queued — send the same command again in a moment |
| 1 | ready — the reply is waiting in the feature report |
| 2 | **no link to the mouse** — usually the mouse is asleep; moving it or clicking brings the link back |
| 4 | busy — same as queued |

A read typically posts `E4 00` then `E4 01` within 10–120 ms. A write posts a
single `E4 00` when the receiver queues it, from a few ms to 800 ms after it was
sent; the mouse applies it up to ~200 ms later. The bond read (opcode 3) posts
no acknowledgement at all; its reply is in the feature report within a few ms.

Four traps, all of which cost hours:

- **Status 2 is a sleeping mouse, not a broken receiver.** After some idle
  time every command answers `2`. Moving the mouse or clicking wakes it and the
  link comes back without touching the receiver (confirmed on hardware).
- **The feature buffer is stale until the new reply lands.** Reading it too
  early returns the *previous* answer, which looks like a valid reply to the
  wrong question. Always check the echoed opcode — and for commands that
  address a slot (buttons, macros) the echoed index too, since every button
  shares one opcode.
- **"Ready" is not reliable, and the echo alone cannot prove freshness.** About
  one read in ten posts `E4 00` and never `E4 01`, while the reply does land.
  Two reads of the same opcode echo the same bytes, so waiting for `1` or
  trusting the echo both fail sometimes. What works: when the buffer already
  echoes the command about to be sent, first send a read with a different
  echo (the bond read, instant; or the snapshot when the bond itself is asked;
  another slot for button reads), wait for its echo, then send the real
  request and poll the buffer until its echo appears — it can only be new.
- **Stale acknowledgements wait in the queue.** Since the frame names no
  command, a leftover `E4` is indistinguishable from the next one. Drain input
  `0x54` before sending anything, and over the receiver read the setting back
  after a write until it shows, so the next reader sees the new value.

Reads confirmed on hardware:

| Opcode | Returns |
|---|---|
| 3 | bond info: VID, PID and link state of the linked mouse |
| 4 | firmware string (`2.0.9r`) |
| 5 | product name (`M3 Mouse`) |
| 6 | protocol version, work mode, battery |
| 7 | **the configuration snapshot** |

### Configuration snapshot — opcode `0x07`

Offsets counted from the opcode echo, after stripping the report id. This is
the `getBaseInfo` of the `M` contract — the `dms` opcode `0x06` used over the
cable answers nothing here.

| Offset | Field |
|---|---|
| 0 | opcode echo (`0x07`) |
| 1 | active onboard profile |
| 2 / 3 / 4 | usb / 2.4GHz / bluetooth slot — low nibble active dpi index, high nibble report-rate index |
| 5..14 | five little-endian uint16 dpi values |
| 15 | sensor bits, 1 = on — `[1:0]` lift-off, `[2]` wave, `[3]` line, `[4]` motion, `[6]` scroll, `[7]` eSports; `[5]` is set on the M3 and maps to nothing known |
| 16 | number of enabled dpi levels |
| 17 | click debounce, in milliseconds |
| 18 | sleep timer, in minutes (read-only here, see opcode 10) |

Example, read from an M3 on firmware `2.0.9r`:

```
51 07 00 13 13 03 90 01 20 03 40 06 80 0c c0 12 35 05 08 00 00
```

profile 0 · active level 3 · rate index 1 · 400/800/1600/3200/4800 ·
debounce 8 ms · lift-off 1.

> The rate nibble is the index of the frequency in the profile list
> (125/500/1000 Hz). Measured through the receiver by timing the mouse's own
> input reports under continuous movement: index 0 arrives every 8.00 ms,
> 1 every 2.00 ms, 2 every 1.00 ms. The receiver also accepts index 3, which
> the M3 profile does not declare; indexes 4 and above are ignored.

## Commands

No checksum in the payload; the report id determines the size.

### Read configuration — `0xB3`, 63 B payload

```
[0] = 0x06
```

Reply (input report, `[0]` ∈ {`0x05`, `0x06`}):

| Offset | Content |
|---|---|
| 1 | profile |
| 2 / 3 / 4 | USB / 2.4G / BT slot — high nibble report rate, low nibble DPI index |
| 5..14 | 5 DPI levels, little-endian uint16 |
| 15 | system flags (lod, wave, line, motion, scroll, eSports) |
| 16 | number of enabled levels (`gears`) |
| 17 | delay |
| 18 | sleep, in minutes |
| 19 | battery — bit 7 charging, bits 0–6 percentage |
| 20..25 | DPI levels 6–8 |
| 27/28/29 | scroll speed / inertia / spl |
| 30..39 | debounce |

### Write DPI (≤5 levels) — `0xB5`, 20 B payload

```
[0]      = 0x40
[1..3]   = active level index (repeated 3x)
[4..13]  = 5 × little-endian uint16
[14]     = number of enabled levels
```

Example — 400/800/1600/3200/4800, active at index 2:

```
40 02 02 02 90 01 20 03 40 06 80 0c c0 12 05 00 00 00 00 00
```

### Write DPI (>5 levels) — `0xB3`, 63 B payload

```
[0]      = 0x44
[1..3]   = active level index
[4]      = level count
[5..]    = N × little-endian uint16
```

## Cable transport (feature report `0x52`)

The `dms` payloads — byte for byte identical — are sent as feature report
`0x52`, zero padded to 64 bytes.

```
send_feature_report(0x52, payload + padding_to_64)
```

Confirmed on hardware (Darmoshark M3, fw 2.0.9r), validated through the
indicator LED colour on every level change:

| Command | Sent | Resulting LED |
|---|---|---|
| `setDpi` level 1 | `40 01 01 01 ...` | blue (800 DPI) |
| `setDpi` level 4 | `40 04 04 04 ...` | yellow (4800 DPI) |
| `setDpi` level 0 | `40 00 00 00 ...` | red (400 DPI) |

Channels tested that do **not** carry config: feature `0x51`, output `0xB2` with
a raw payload, and output `0xB2` with the payload wrapped in `AA/55` (kinds 1, 2
and 3). Only `0x52` forwards to the core.

Reads through `0x52` hit a fixed handler: any opcode returns the identity block
(VID, PID, firmware, battery), never the configuration snapshot.

### Five level ceiling over the cable

Only the **short format** (`setDpi`, opcode `0x40`) crosses the cable channel.
The extended format (`setDpiExtended`, opcode `0x44`, used for 6 or more levels)
is accepted without error but **ignored by the firmware** — tested with both 6
and 5 levels, neither took effect.

Since the short packet reserves bytes `[4..13]` for five `uint16` values, the
ceiling over the cable is **5 DPI levels**. Each accepts any value within
50–26000; what is not possible is having a sixth.

## DFU channel (cable, usage page `0x8C`)

Framing: output report `0xB2`, reply on input report `0xB1`, possibly split
across several 32 B packets.

```
[0] 0xAA          header
[1] 0x55 / 0x56   send no-ack / send ack
[2] len
[3] ~len          one's complement of len
[4] kind
[5] command
[6] checksum (sum of the parameter bytes)
```

Read commands confirmed on the M3:

| Cmd | kind | Returns |
|---|---|---|
| 96 | 1 | module, firmware and hardware |
| 97 | 2 | DFU bootloader revision |

Reply to cmd 96, after reassembling the fragments (payload starts at offset 5
of the first packet):

| Offset | Field |
|---|---|
| 4..13 | module model (`MOTO_M3`) |
| 16..25 | firmware version (`2.0.9r`) |
| 26..35 | hardware version (`1.0.0`) |

## Identity channel (cable, feature report `0x51`)

Round trip through a feature report: write the command, read the reply from the
same id.

Command `0x06` — reply (after the echoed report id):

| Offset | Field |
|---|---|
| 0 | opcode echo |
| 1 | status (1 = ok) |
| 3..4 | VID little-endian |
| 5..6 | PID little-endian |
| 7..8 | firmware (`0x0209` → 2.0.9) |
| 10 | battery percentage |

### Read opcodes on the `0x51` channel

Reply layout: `[0]` echoed opcode, `[1]` length, `[2..]` data.

| Opcode | Returns | Example |
|---|---|---|
| `0x02` | no reply | — |
| `0x03` | no reply (dongle command) | — |
| `0x04` | firmware string | `2.0.9r` |
| `0x05` | product name | `M3 Mouse` |
| `0x06` | identity + battery | VID, PID, fw, `%` |

None of them carries DPI state. The report ids `0xB3`/`0xB5` do not exist as
feature reports on this channel: they return only zeros.

## `dms` command table

Opcode in byte 0 of the payload. Routing: `0xB5` = 20 B payload, `0xB3` = 63 B
payload. The ACK comes back as `0xE4 <status> <opcode>`, with `status = 0` on
success.

| Opcode | Name | Report | Role |
|---|---|---|---|
| 2 | `getProtocol` | 0xB5 | protocol version |
| 3 | `getBondInfo` | 0xB5 | pairing state with the receiver |
| 4 | `getDeviceString` | 0xB3 | device string |
| 5 | `getMouseInfo` | 0xB5 | basic info |
| 6 | `getMouseExtInfo` | 0xB3 | **full configuration snapshot** |
| 10 | `deviceTime` | 0xB5 | sleep timer — `[1]` 1=set 2=get, `[2]` minutes. Cable only: the receiver contract never sends it, a write through the receiver leaves snapshot byte 18 unchanged, and a `get` never turns ready |
| 11 | `pairButton` | 0xB5 | pairing |
| 14 | `profileSwitch` | 0xB5 | profile switch — `[1]` index |
| 15 | `driverConfigRecovery` | 0xB5 | reset; `[1]=63` = factory defaults |
| 35 / 36 | `get/setLightEffectParam` | 0xB5 | lighting |
| 64 | `setDpi` | 0xB5 | DPI, up to 5 levels |
| 65 | `setReportRate` | 0xB5 | `[1..2]` rate index, repeated; the rest zero. Both vendor contracts call the index `level` — it is not a DPI level. Confirmed on the receiver |
| 66 | `setSensorLiftCutoff` | 0xB5 | `[1]` LOD, `[2]` wave, `[3]` line, `[4]` motion, `[6]` scroll, `[7]` eSports. wave/line/motion: 1 = on, 2 = off; scroll/eSports: 2 = on, 1 = off (confirmed one switch at a time against snapshot byte 15). Every write sets all five, so change lift-off by resending the stored switches |
| 67 | `setButtonDebounce` | 0xB5 | `[1]` ms |
| 68 | `setDpiExtended` | 0xB3 | DPI, more than 5 levels |
| 69 | `setScroll` | 0xB5 | `[1]` speed, `[2]` inertia, `[3]` spl |
| 82 | `setButtonConfig` | 0xB3 | `[1]` button, `[3]` kind, `[4..]` data |
| 83 / 84 | `setMacroName` / `setMacroData` | 0xB3 | macros |
| 97 / 98 | `getAllButtonConfig` / `getButtonConfig` | 0xB3 | button reads |
| 99 / 100 | `getMacroName` / `getMacroData` | 0xB3 | macro reads |
| 113 / 114 | `longDataTransfer` / `longDataFlowControl` | 0xB3 | long transfer |

### Button assignment kinds

`0` remove · `1` mouse · `2` keyboard · `3` media · `4` macro · `5` dpi ·
`6` light · `7` gameReinforce · `8` shortCut · `9` disable · `10` profileSwitch

### Asynchronous events (input reports)

| `[0]` | Event |
|---|---|
| 225 | lighting changed |
| 226 | base changed — `[1]` workMode, `[2]` connection, `[3..4]` battery, `[5..7]` dpi/rate/level |
| 229 | profile changed — `[1]` new profile |

## `dms_v2` variant

The configurator detects the contract from an initial report: if `reply[6] == 21`
and `reply[7] == 25` it uses `dms_v2`, otherwise `dms`. The M3 uses `dms` —
`dms_v2` has its own opcodes and is not implemented here.
