#!/usr/bin/env python3
"""
XMODEM Sender for u-blox Module Firmware Updates
================================================

Simple and tested XMODEM-1K sender for u-blox module firmware updates.
Includes robust error handling and buffer management.

Usage: python xmodem.py COM3 firmware.bin [115200]
       python xmodem.py --version
"""

import time
import struct
import os
import sys

# Tool version. Kept in sync with the u-connectXpress user guide and the
# latest u-blox module firmware release that this tool has been validated
# against.
__version__ = "3.4.0"

# `serial` (pyserial) is imported lazily inside main() so that `--version`
# and the usage banner work without requiring pyserial to be installed.
serial = None  # type: ignore

class XModemSender:
    # XMODEM Protocol Constants
    SOH = 0x01  # Start of Header (128-byte blocks)
    STX = 0x02  # Start of Text (1K blocks)
    EOT = 0x04  # End of Transmission
    ACK = 0x06  # Acknowledge
    NAK = 0x15  # Negative Acknowledge
    CAN = 0x18  # Cancel
    C   = 0x43  # Request CRC mode ('C')
    
    def __init__(self, port, baudrate=115200, debug=False):
        self.serial = serial.Serial(port, baudrate, timeout=15)
        self.debug = debug
    
    def send_file(self, filename):
        """Send file using XMODEM-1K protocol"""
        if not os.path.exists(filename):
            print(f"Error: File '{filename}' not found")
            return False
        
        file_size = os.path.getsize(filename)
        block_size = 1024  # Always use XMODEM-1K for firmware
        total_blocks = (file_size + block_size - 1) // block_size
        
        print(f"Sending file: {filename}")
        print(f"File size: {file_size} bytes")
        print(f"Total blocks: {total_blocks}")
        print("Protocol: XMODEM-1K with CRC-16")
        
        # Wait for receiver ready signal
        if not self._wait_for_start():
            return False
        
        # Send all blocks
        with open(filename, 'rb') as f:
            block_number = 1

            for block_index in range(total_blocks):
                data = f.read(block_size)
                if len(data) < block_size:
                    data += b'\x1A' * (block_size - len(data))  # Pad with SUB

                if not self._send_block(block_number, data):
                    print(f"\nError: Failed to send block {block_number}")
                    return False

                # NOTE: Do NOT sleep after block 1. The ACK for block 1 is only
                # emitted by the bootloader once the flash erase has completed
                # and the block has been written. Adding a delay here exceeds
                # the bootloader's inter-block timeout and causes it to NAK,
                # then abort and reset the module.

                progress = (block_index + 1) * 100 // total_blocks
                print(f"\rProgress: {progress:3d}% ({block_index + 1}/{total_blocks} blocks)",
                      end='', flush=True)

                # Increment block number with natural 8-bit wraparound
                block_number = (block_number + 1) % 256

        print()  # newline after progress bar

        # Send End of Transmission
        return self._send_eot()

    def _wait_for_start(self):
        """Wait for receiver ready signal"""
        print("Waiting for receiver ready signal...")

        # Clear buffers
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()

        for attempt in range(60):  # 60 second timeout
            char = self.serial.read(1)
            if char and self.debug:
                print(f"[DBG] start-signal byte 0x{char.hex()}")
            if char == bytes([self.C]):
                print("Receiver ready (CRC mode)")
                return True
            elif char == bytes([self.NAK]):
                print("Receiver ready (checksum mode)")
                return True
            elif char == bytes([self.CAN]):
                print("Transfer cancelled by receiver")
                return False
            elif char:
                if self.debug:
                    print(f"Unexpected response: 0x{char.hex()}")
                time.sleep(0.1)
                self.serial.reset_input_buffer()

            time.sleep(1)

        print("Timeout waiting for start signal")
        return False
    
    def _send_block(self, block_num, data):
        """Send a single XMODEM-1K block with retries"""
        block_complement = (~block_num) & 0xFF  # Bitwise complement for XMODEM protocol

        # Block 1 may take several seconds while the bootloader erases flash;
        # subsequent blocks are normally acknowledged within ~100 ms.
        original_timeout = self.serial.timeout
        block_timeout = 30 if block_num == 1 else 3

        try:
            for retry in range(10):
                if retry > 0 and self.debug:
                    print(f"\n[XMODEM] Retrying block {block_num} (try {retry + 1}/10)")

                # Build block: STX + block_num + complement + data + CRC16
                block = bytes([self.STX, block_num, block_complement]) + data
                crc = self._calculate_crc16(data)
                block += struct.pack('>H', crc)
                if self.debug:
                    print(f"[DBG] send block {block_num} (try {retry + 1}), {len(block)} bytes, crc=0x{crc:04X}")

                # Pre-send flush for block 2: bootloader may still have garbage in buffer
                if block_num == 2 and retry == 0:
                    self.serial.reset_input_buffer()

                # Send block
                self.serial.timeout = block_timeout
                self.serial.write(block)
                self.serial.flush()

                # Wait for response
                response = self.serial.read(1)
                if self.debug and response:
                    print(f"[DBG] block {block_num} response 0x{response.hex()}")
                if response == bytes([self.ACK]):
                    return True
                elif response == bytes([self.NAK]):
                    if self.debug and retry > 0:
                        print(f"[XMODEM] NAK received for block {block_num}")
                    time.sleep(0.1)
                    self.serial.reset_input_buffer()
                    continue
                elif response == bytes([self.CAN]):
                    print("\nTransfer cancelled by receiver")
                    return False
                else:
                    if self.debug and response:
                        print(f"\n[XMODEM] Unexpected response for block {block_num}: {response.hex()}")
                    elif self.debug:
                        print(f"\n[XMODEM] Timeout waiting for response on block {block_num}")
                    time.sleep(0.1)
                    self.serial.reset_input_buffer()
                    continue

            print(f"\nBlock {block_num} failed after 10 retries")
            return False
        finally:
            self.serial.timeout = original_timeout
    
    def _send_eot(self):
        """Send End of Transmission"""
        print("[XMODEM] Sending EOT")
        for attempt in range(10):
            self.serial.write(bytes([self.EOT]))
            self.serial.flush()

            response = self.serial.read(1)
            if response == bytes([self.ACK]):
                print("[XMODEM] Transfer completed successfully")
                self.serial.close()
                return True
            else:
                if self.debug and response:
                    print(f"[XMODEM] Unexpected EOT response: 0x{response.hex()}")
                elif self.debug:
                    print("[XMODEM] Timeout waiting for EOT response")
            time.sleep(1)

        print("[XMODEM] Failed to get EOT acknowledgment")
        return False
    
    def _calculate_crc16(self, data):
        """Calculate CRC-16 for XMODEM (CCITT polynomial 0x1021)"""
        crc = 0x0000
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc <<= 1
                crc &= 0xFFFF
        return crc


def ublox_firmware_update(port, firmware_file, baudrate=115200, debug=False):
    """Update u-blox module firmware using XMODEM-1K"""
    print(f"u-blox Module Firmware Update Tool v{__version__}")
    print("=" * 40)
    if debug:
        print("[DBG] debug logging enabled")
    
    try:
        # Step 1: Send AT command to enter XMODEM mode
        print("Connecting to module...")
        print(f"Opening serial port: {port}")
        at_serial = serial.Serial(port, 115200, timeout=5)

        # Wait for module to be ready (opening port toggles DTR which may reset the module)
        print("Waiting for module ready...")
        time.sleep(0.5)
        at_serial.reset_input_buffer()

        module_ready = False
        for probe in range(10):
            at_serial.write(b"AT\r")
            time.sleep(0.5)
            probe_resp = at_serial.read(64)
            # Decode for human-readable output (strip trailing CR/LF noise)
            probe_text = probe_resp.decode('utf-8', errors='replace').strip()
            print(f"Probe {probe + 1}: {probe_text}")
            if b"OK" in probe_resp:
                module_ready = True
                break
            time.sleep(1)
            at_serial.reset_input_buffer()
        
        if not module_ready:
            print("Error: Module not responding to AT commands")
            at_serial.close()
            return False
        
        print(f"Entering XMODEM mode at {baudrate} baud...")
        at_serial.write(f"AT+USYFWUS={baudrate}\r".encode())
        
        response = at_serial.read(100)
        if b"OK" not in response:
            print(f"Warning: Unexpected response: {response}")
        
        time.sleep(2)
        
        # Step 2: Change baud rate in-place (no close/reopen to avoid DTR/RTS toggle resetting the module)
        print(f"Starting XMODEM-1K transfer at {baudrate} baud...")
        at_serial.baudrate = baudrate
        at_serial.reset_input_buffer()
        
        xmodem = XModemSender.__new__(XModemSender)
        xmodem.serial = at_serial
        xmodem.debug = debug
        
        if xmodem.send_file(firmware_file):
            print("\nFirmware update completed successfully!")
            # Step 3: Check new firmware version
            print("Checking firmware version...")
            time.sleep(5)
            
            for attempt in range(6):
                try:
                    check_serial = serial.Serial(port, 115200, timeout=5)
                    check_serial.write(b"AT+GMR\r")
                    time.sleep(1)
                    response = check_serial.read(200)
                    check_serial.close()
                    
                    if response and b"OK" in response:
                        version_lines = response.decode('utf-8', errors='ignore').strip().split('\n')
                        for line in version_lines:
                            if line.strip() and line.strip() != 'OK' and not line.startswith('AT'):
                                print(f"Firmware version: {line.strip()}")
                                return True
                        break
                except Exception:
                    print(f"Module restarting (attempt {attempt + 1}/6)...")
                    if attempt < 5:
                        time.sleep(5)
            
            return True
        else:
            print("\nFirmware update failed!")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    args = sys.argv[1:]

    # --version / -v: print version and exit
    if args and args[0] in ("--version", "-v"):
        print(f"ucx-xmodem {__version__}")
        return 0

    debug = False
    while args and args[0] in ("--debug", "-d"):
        debug = True
        args.pop(0)

    if len(args) < 2:
        print(f"XMODEM Sender for u-blox Module Firmware Updates (v{__version__})")
        print("Usage: python xmodem.py [--debug|-d] <port> <firmware_file> [baud_rate]")
        print("       python xmodem.py --version")
        print("")
        print("Options:")
        print("  --debug, -d    Verbose protocol logging for troubleshooting")
        print("  --version, -v  Print tool version and exit")
        print("")
        print("Examples:")
        print("  python xmodem.py COM3 firmware.bin")
        print("  python xmodem.py COM3 firmware.bin 115200")
        print("  python xmodem.py --debug COM22 firmware.bin")
        return 1

    # Lazy import so --version and usage work without pyserial installed.
    global serial
    try:
        import serial as _serial
        serial = _serial
    except ImportError:
        print("Error: pyserial is required. Install it with: pip install pyserial")
        return 1

    port = args[0]
    firmware_file = args[1]
    baudrate = int(args[2]) if len(args) > 2 else 115200

    success = ublox_firmware_update(port, firmware_file, baudrate, debug=debug)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
