# ucx-xmodem

XMODEM-1K firmware update tools for **u-blox short-range modules** running
**u-connectXpress**. Two reference implementations from the same source of
truth, with identical command-line interface and runtime output:

| Implementation | File | Use when |
|----------------|------|----------|
| **Python** | [`xmodem.py`](xmodem.py) | Quick PC-side updates, scripting, CI |
| **C (Win32)** | [`xmodem.c`](xmodem.c) | Standalone Windows binary, embedding, no Python dependency |

The current release (`VERSION` = **3.4.0**) is validated against
**u-connectXpress 3.4.0** firmware on **NORA-W36** at **115200** and
**1 000 000** baud.

---

## Table of contents

- [Supported modules](#supported-modules)
- [Quick start (Python)](#quick-start-python)
- [Quick start (C)](#quick-start-c)
- [Command-line interface](#command-line-interface)
- [How it works](#how-it-works)
- [Versioning policy](#versioning-policy)
- [Troubleshooting](#troubleshooting)
- [Limitations and known issues](#limitations-and-known-issues)
- [Repository layout](#repository-layout)
- [Contributing / reporting issues](#contributing--reporting-issues)
- [See also](#see-also)

---

## Supported modules

Tools are validated against u-blox short-range modules running u-connectXpress:

- **NORA-W36** (Wi-Fi + Bluetooth LE)
- **NORA-B26** (Bluetooth LE Central + Peripheral)
- **NORA-B27** (Bluetooth LE Peripheral only)
- **ANNA-B56** (Bluetooth LE Central + Peripheral)

Any other u-blox module that exposes the `AT+USYFWUS=<baudrate>` AT command
should also work, but only the modules above are CI-validated.

---

## Quick start (Python)

### Requirements

- Python **3.8** or newer
- [pyserial](https://pypi.org/project/pyserial/) — only required to actually
  run a flash; `--version` and `--help` work without it.

### Install

```bash
pip install pyserial
```

### Flash

```bash
# Default baud (115200)
python xmodem.py COM22 NORA-W36X-SW-3.4.0-120.bin

# 1 Mbit (recommended for large images, ~14 s per MB)
python xmodem.py COM22 NORA-W36X-SW-3.4.0-120.bin 1000000

# Linux / macOS
python xmodem.py /dev/ttyUSB0 firmware.bin 1000000
```

---

## Quick start (C)

### Requirements

- Windows (uses `windows.h` / `kernel32`)
- One of:
  - **GCC** (MSYS2 / MinGW-w64), or
  - **MSVC** (`cl.exe`, e.g. from "x64 Native Tools Command Prompt")

> Linux/macOS port: not in this release. The protocol code is portable, only
> the serial-port glue is Win32. Pull requests welcome.

### Compile

GCC / MinGW:

```powershell
gcc -Wall -Wextra -O2 -o xmodem.exe xmodem.c -lkernel32
```

MSVC:

```powershell
cl /nologo /O2 /Fe:xmodem.exe xmodem.c kernel32.lib
```

### Flash

```powershell
# Default baud (115200)
.\xmodem.exe COM22 NORA-W36X-SW-3.4.0-120.bin

# 1 Mbit
.\xmodem.exe COM22 NORA-W36X-SW-3.4.0-120.bin 1000000
```

---

## Command-line interface

Both implementations expose **the same flags, examples, and runtime
messages**. The only intentional difference is the program name in the usage
banner.

```text
Usage: xmodem.exe        [--debug|-d] <port> <firmware_file> [baud_rate]
       python xmodem.py  [--debug|-d] <port> <firmware_file> [baud_rate]

Options:
  --debug,   -d   Verbose protocol logging for troubleshooting
  --version, -v   Print tool version and exit
```

### Arguments

| Arg              | Description                                              | Default  |
|------------------|----------------------------------------------------------|----------|
| `<port>`         | Serial port (e.g. `COM22`, `/dev/ttyUSB0`)               | required |
| `<firmware_file>`| Path to the firmware `.bin` image                         | required |
| `[baud_rate]`    | Transfer baud (115200, 460800, 921600, 1000000, 3000000) | `115200` |

### Exit codes

| Code | Meaning                                          |
|------|--------------------------------------------------|
| `0`  | Update completed successfully                    |
| `1`  | Argument error or update failed                  |

### Example output (success, normal mode)

```text
u-blox Module Firmware Update Tool v3.4.0
========================================
Connecting to module...
Opening serial port: \\.\COM22
Waiting for module ready...
Probe 1: AT
OK
Entering XMODEM mode at 1000000 baud...
Starting XMODEM-1K transfer at 1000000 baud...
Sending file: NORA-W36X-SW-3.4.0-120.bin
File size: 1417216 bytes
Total blocks: 1384
Protocol: XMODEM-1K with CRC-16
Waiting for receiver ready signal...
Receiver ready (CRC mode)
Progress: 100% (1384/1384 blocks)
[XMODEM] Sending EOT
[XMODEM] Transfer completed successfully

Firmware update completed successfully!
Checking firmware version...
Firmware version: "3.4.0-120"
```

### Example output (`--debug`)

`--debug` adds one line per block plus the response byte, the start-signal
byte, and verbose retry/timeout reasons. Use this when collecting logs for a
support ticket.

```text
[DBG] debug logging enabled
...
[DBG] start-signal byte 0x43
[DBG] send block 1 (try 1), 1029 bytes, crc=0xF9F0
[DBG] block 1 response 0x06
[DBG] send block 2 (try 1), 1029 bytes, crc=0x13F5
[DBG] block 2 response 0x06
...
```

---

## How it works

```
PC                                Module (running u-connectXpress)
 │                                 │
 │── AT\r ──────────────────────▶ │   probe AT mode
 │◀──────────────────── AT\r\nOK │
 │                                 │
 │── AT+USYFWUS=<baud>\r ───────▶ │   request firmware-update mode
 │◀───────────────────────── OK  │   (module switches to bootloader)
 │── (change PC baud in-place) ─  │
 │                                 │
 │◀─────────────────── 'C' (0x43)│   bootloader requests CRC mode
 │── STX | 0x01 | 0xFE | 1024B | CRC16 ▶│  block 1 (slow: flash erase)
 │◀────────────────── ACK (0x06) │
 │── STX | 0x02 | 0xFD | 1024B | CRC16 ▶│  block 2
 │◀────────────────── ACK (0x06) │
 │     ... repeat ...              │
 │── EOT (0x04) ────────────────▶ │
 │◀────────────────── ACK (0x06) │   image written, module reboots
 │                                 │
 │── AT+GMR\r ──────────────────▶ │   read back new firmware version
 │◀────────────── 3.4.0-120 / OK │
```

Key implementation choices:

- **No DTR/RTS reset.** The PC keeps the same `HANDLE` / `Serial` object across
  the AT→XMODEM transition and only changes the baud rate in place. Closing
  and reopening would toggle DTR/RTS and reset the module.
- **Block 1 has a 30 s read timeout.** The bootloader only ACKs block 1 *after*
  the flash-erase has finished. Earlier versions of this tool slept 3 s
  between block 1 and block 2 — that exceeded the bootloader's inter-block
  timeout and caused `+STARTUP` reboot loops. Fixed in 3.4.0.
- **XMODEM-1K + CRC-16/CCITT** (poly `0x1021`, init `0x0000`).
- **Up to 10 retries per block.** A failed block is re-sent unchanged.
- **Pre-block-2 input flush** clears any residual bytes the bootloader
  emitted after the long block-1 wait.

---

## Versioning policy

The tool version tracks the latest u-connectXpress **release** it has been
validated against. Three places must stay in lock-step:

| Where | What |
|-------|------|
| [`VERSION`](VERSION) | Source of truth, plain-text version string |
| [`xmodem.c`](xmodem.c) | `#define UCX_XMODEM_VERSION "X.Y.Z"` |
| [`xmodem.py`](xmodem.py) | `__version__ = "X.Y.Z"` |

The companion repo [u-blox/u-connectXpress](https://github.com/u-blox/u-connectXpress)
generator runs a sync check on every build and warns if these drift.

Releases are tagged on the form `X.Y.Z` (annotated tag, no `v` prefix), e.g.
`3.4.0`. Check it out with:

```bash
git clone --branch 3.4.0 https://github.com/u-blox/ucx-xmodem.git
```

---

## Troubleshooting

### "Module not responding to AT commands"
- Wrong COM port — list available ports with `Get-PnpDevice -Class Ports`
  (Windows) or `ls /dev/tty*` (Linux/macOS).
- Module is held in reset by another tool (e.g. an open serial-monitor in
  another program). Close the other tool.
- Wrong baud — tool always opens the AT phase at **115200**. If you have
  changed the persistent UART baud with `AT+UMRS`, set it back to 115200
  first.
- USB-to-UART driver issue — try unplugging/replugging the EVK.

### "Receiver ready (CRC mode)" never appears / `Probe 1: \x15\x15\x15`
- The module is **already in XMODEM mode** from a previous interrupted
  attempt. Power-cycle the EVK (or wait ~60 s for the bootloader timeout)
  and try again.

### `+STARTUP` appears mid-transfer / NAK on block 2
- You are running an old (pre-3.4.0) version of the tool that slept after
  block 1. Pull the latest `main` (or check out tag `3.4.0`).

### "Block N failed after 10 retries"
- Cable quality / USB hub — try a shorter, known-good USB cable, plug
  directly into the host (no hub).
- Baud rate too high for the cable/driver combination — drop from
  `1000000` to `460800` or back to `115200`.
- Run again with `--debug` and attach the log to your support ticket.

### "Transfer cancelled by receiver" (CAN, 0x18)
- Image rejected by the bootloader (wrong product, wrong signing, corrupt
  binary). Verify the `.bin` is the correct one for your module.

### Python: `ModuleNotFoundError: No module named 'serial'`
- Install pyserial in the **same** Python interpreter you run `xmodem.py`
  with:
  ```bash
  python -m pip install pyserial
  ```
- Note: `python xmodem.py --version` works **without** pyserial — the import
  is lazy.

### Windows: `Could not open serial port COMxx`, error 5
- Permission / sharing violation — another program (Tera Term, PuTTY,
  Arduino IDE, VS Code serial monitor) has the port open. Close it.

### Windows: `Could not open serial port COMxx`, error 2
- Port does not exist. Re-check `Get-PnpDevice -Class Ports`.

---

## Limitations and known issues

- Only the **C/Win32** implementation builds out of the box on Windows.
  Porting to POSIX `termios` is straightforward — patches welcome.
- No simultaneous transfer to multiple modules from the same process.
- The post-flash `AT+GMR` version-check loop is best-effort (fail-soft) —
  a missing version readout does **not** indicate a failed flash. The
  authoritative success indicator is `[XMODEM] Transfer completed
  successfully` followed by `Firmware update completed successfully!`.
- No resume / partial-update support. A failed transfer must restart from
  block 1.
- The C implementation hard-codes the AT-mode baud at 115200 (the
  bootloader's expected default). If your module's persistent UART baud has
  been changed, restore it with `AT+UMRS` before flashing.

---

## Repository layout

```
ucx-xmodem/
├── README.md                 ← you are here
├── README_xmodem_python.md   ← deeper Python notes
├── README_xmodem_c.md        ← deeper C notes
├── VERSION                   ← single source of truth for the version
├── xmodem.c                  ← C/Win32 sender
├── xmodem.py                 ← Python sender
└── .gitignore
```

---

## Contributing / reporting issues

- Bug reports and pull requests: <https://github.com/u-blox/ucx-xmodem/issues>
- For protocol issues, please attach a log captured with `--debug` and
  include:
  - Module part number and firmware version (`AT+GMR`)
  - Host OS, USB-to-UART bridge, and baud rate used
  - Full command line you ran
  - Whether the module had been flashed before in the same session

When changing the protocol code, please update **both** `xmodem.py` and
`xmodem.c` so they stay byte-for-byte compatible at the wire level and
line-for-line aligned in user-visible output.

---

## See also

- [u-blox/u-connectXpress](https://github.com/u-blox/u-connectXpress) —
  u-connectXpress AT command specification, error codes, and the per-product
  user guides that document the `AT+USYFWUS` command.
- [u-blox short-range modules](https://www.u-blox.com/en/short-range-modules)
- [pyserial documentation](https://pyserial.readthedocs.io/)
- [XMODEM-1K protocol reference](https://en.wikipedia.org/wiki/XMODEM)
