# u-blox XMODEM C Implementation

XMODEM-1K sender implementation for u-blox module firmware updates (Windows).

## Requirements

- Windows operating system
- C compiler (GCC/MinGW or Visual Studio)

## Compilation

### Using GCC/MinGW

```bash
gcc -o xmodem xmodem.c -lkernel32
```

### Using Visual Studio Developer Command Prompt

```bash
cl /Fe:xmodem.exe xmodem.c kernel32.lib
```

### Using Visual Studio IDE

1. Create a new Console Application project
2. Add `xmodem.c` to the project
3. Build the solution (F7 or Build → Build Solution)

## Usage

```bash
# Basic usage (default 115200 baud)
xmodem.exe COM3 firmware.bin

# With custom baud rate
xmodem.exe COM3 firmware.bin 3000000
```

### Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `port` | Serial port (e.g., COM3, COM10) | Required |
| `firmware_file` | Path to firmware binary file | Required |
| `baud_rate` | Transfer baud rate | 115200 |

## Supported Modules

This tool works with u-blox short-range modules running u-connectXpress firmware:
- NORA-W36 series
- NORA-B26 series
- NORA-B27 series

## How It Works

1. **Connection**: Opens serial port at 115200 baud
2. **Enter XMODEM Mode**: Sends `AT+USYFWUS=<baudrate>` command
3. **Transfer**: Uses XMODEM-1K protocol (1024-byte blocks with CRC-16)
4. **Verification**: Checks firmware version after update

## Protocol Details

- **Protocol**: XMODEM-1K with CRC-16 error detection
- **Block Size**: 1024 bytes
- **Error Handling**: Automatic retries (up to 10 per block)
- **Timeout**: 60 seconds for handshake, 3 seconds per block response

## Example Output

```
u-blox Module Firmware Update Tool
========================================
Connecting to module...
Opening serial port: COM3
Entering XMODEM mode at 115200 baud...
Starting XMODEM-1K transfer at 115200 baud...
Sending file: firmware.bin
File size: 1445120 bytes
Total blocks: 1412
Protocol: XMODEM-1K with CRC-16
Waiting for receiver ready signal...
Receiver ready (CRC mode)
[XMODEM] Sending block 1, try 1
[XMODEM] Block 1 acknowledged
Progress: 1% (1/1412 blocks)
...
Progress: 100% (1412/1412 blocks)
[XMODEM] Sending EOT
[XMODEM] Transfer completed successfully

Firmware update completed successfully!
Checking firmware version...
Firmware version: 3.1.0-150
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Could not open serial port" | Check port name, ensure no other app is using it |
| "Timeout waiting for start signal" | Check serial connection, verify module is powered |
| "Cancelled by receiver" | Reset module and retry |
| "Failed after 10 retries" | Check cable quality, reduce baud rate |
| Windows error 2 | Port doesn't exist, check Device Manager |
| Windows error 5 | Access denied, close other serial applications |

## COM Port Handling

The implementation automatically handles Windows COM port naming:
- **COM1-COM9**: Used directly (e.g., `COM3`)
- **COM10 and higher**: Automatically converted to `\\.\COM10` format

## Key Features

- **Native Windows API**: Direct serial port handling for best performance
- **XMODEM-1K**: 1024-byte blocks for efficient transfers
- **CRC-16**: Robust error detection
- **Automatic Retries**: Up to 10 retries per block
- **High Baud Rate**: Supports up to 3Mbps

## See Also

- [u-blox Support](https://www.u-blox.com/support) - Product documentation and support
