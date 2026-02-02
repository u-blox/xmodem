# u-blox XMODEM Python Implementation

XMODEM-1K sender implementation for u-blox module firmware updates.

## Requirements

- Python 3.6 or later
- pyserial library

## Installation

```bash
pip install pyserial
```

## Usage

```bash
# Basic usage (default 115200 baud)
python xmodem.py COM3 firmware.bin

# With custom baud rate
python xmodem.py COM3 firmware.bin 3000000

# Linux/macOS
python xmodem.py /dev/ttyUSB0 firmware.bin 115200
```

### Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `port` | Serial port (e.g., COM3, /dev/ttyUSB0) | Required |
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
- **Timeout**: 60 seconds for handshake, 15 seconds per block

## Example Output

```
u-blox Module Firmware Update Tool
========================================
Connecting to module...
Entering XMODEM mode at 115200 baud...
Starting XMODEM-1K transfer at 115200 baud...
Sending file: firmware.bin
File size: 1445120 bytes
Total blocks: 1412
Protocol: XMODEM-1K with CRC-16
Waiting for receiver ready signal...
Receiver ready (CRC mode)
Progress: 1% (14/1412 blocks)
...
Progress: 100% (1412/1412 blocks)
Sending end of transmission...
Transfer completed successfully!

Firmware update completed successfully!
Checking firmware version...
Firmware version: 3.1.0-150
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "File not found" | Verify firmware file path |
| "Timeout waiting for receiver" | Check serial connection, verify module is powered |
| "Transfer cancelled by receiver" | Reset module and retry |
| "Block failed after 10 retries" | Check cable quality, reduce baud rate |

## Cross-Platform Support

- **Windows**: Use COM port names (COM3, COM10, etc.)
- **Linux**: Use device paths (/dev/ttyUSB0, /dev/ttyACM0)
- **macOS**: Use device paths (/dev/cu.usbserial-xxxx)

## See Also

- [u-blox Support](https://www.u-blox.com/support) - Product documentation and support
