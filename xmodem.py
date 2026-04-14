#!/usr/bin/env python3
"""
XMODEM Sender for u-blox Module Firmware Updates
================================================

Simple and tested XMODEM-1K sender for u-blox module firmware updates.
Includes robust error handling and buffer management.

Usage: python xmodem.py COM3 firmware.bin [115200]
"""

import serial
import time
import struct
import os
import sys

class XModemSender:
    # XMODEM Protocol Constants
    SOH = 0x01  # Start of Header (128-byte blocks)
    STX = 0x02  # Start of Text (1K blocks)
    EOT = 0x04  # End of Transmission
    ACK = 0x06  # Acknowledge
    NAK = 0x15  # Negative Acknowledge
    CAN = 0x18  # Cancel
    C   = 0x43  # Request CRC mode ('C')
    
    def __init__(self, port, baudrate=115200):
        self.serial = serial.Serial(port, baudrate, timeout=15)
        self.debug = True
    
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
                    print(f"Error: Failed to send block {block_number}")
                    return False
                
                # After block 1, bootloader erases flash - wait for it to be ready
                if block_number == 1:
                    print("Waiting for bootloader flash erase...")
                    time.sleep(3)
                    self.serial.reset_input_buffer()
                
                progress = (block_index + 1) * 100 // total_blocks
                print(f"Progress: {progress}% ({block_index + 1}/{total_blocks} blocks)")
                
                # Increment block number with natural 8-bit wraparound  
                block_number = (block_number + 1) % 256
        
        # Send End of Transmission
        print("Sending end of transmission...")
        return self._send_eot()
    
    def _wait_for_start(self):
        """Wait for receiver ready signal"""
        print("Waiting for receiver ready signal...")
        
        # Clear buffers
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()
        
        for attempt in range(60):  # 60 second timeout
            char = self.serial.read(1)
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
                    print(f"Unexpected response: {char.hex()}")
                time.sleep(0.1)
                self.serial.reset_input_buffer()
            
            time.sleep(1)
        
        print("Timeout waiting for receiver")
        return False
    
    def _send_block(self, block_num, data):
        """Send a single XMODEM-1K block with retries"""
        block_complement = (~block_num) & 0xFF  # Bitwise complement for XMODEM protocol
        
        for retry in range(10):
            # Build block: STX + block_num + complement + data + CRC16
            block = bytes([self.STX, block_num, block_complement]) + data
            crc = self._calculate_crc16(data)
            block += struct.pack('>H', crc)
            
            # Pre-send flush for block 2: bootloader may still have garbage in buffer
            if block_num == 2 and retry == 0:
                self.serial.reset_input_buffer()
            
            # Send block
            self.serial.write(block)
            self.serial.flush()
            
            # Wait for response
            response = self.serial.read(1)
            if response == bytes([self.ACK]):
                if self.debug:
                    print(f"Block {block_num} acknowledged")
                return True
            elif response == bytes([self.NAK]):
                if self.debug:
                    print(f"Block {block_num} NAK, retrying...")
                time.sleep(0.1)
                self.serial.reset_input_buffer()
                continue
            elif response == bytes([self.CAN]):
                print("Transfer cancelled by receiver")
                return False
            else:
                if self.debug and response:
                    print(f"Unexpected response: {response.hex()}")
                time.sleep(0.1)
                self.serial.reset_input_buffer()
                continue
        
        print(f"Block {block_num} failed after 10 retries")
        return False
    
    def _send_eot(self):
        """Send End of Transmission"""
        for attempt in range(10):
            self.serial.write(bytes([self.EOT]))
            self.serial.flush()
            
            response = self.serial.read(1)
            if response == bytes([self.ACK]):
                print("Transfer completed successfully!")
                self.serial.close()
                return True
            
            time.sleep(1)
        
        print("Failed to get EOT acknowledgment")
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


def ublox_firmware_update(port, firmware_file, baudrate=115200):
    """Update u-blox module firmware using XMODEM-1K"""
    print("u-blox Module Firmware Update Tool")
    print("=" * 40)
    
    try:
        # Step 1: Send AT command to enter XMODEM mode
        print("Connecting to module...")
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
            print(f"Probe {probe + 1}: {probe_resp}")
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
        xmodem.debug = True
        
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
            print("Firmware update failed!")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    if len(sys.argv) < 3:
        print("XMODEM Sender for u-blox Module Firmware Updates")
        print("Usage: python xmodem.py <port> <firmware_file> [baud_rate]")
        print("")
        print("Examples:")
        print("  python xmodem.py COM3 firmware.bin")
        print("  python xmodem.py COM3 firmware.bin 115200")
        print("  python xmodem.py /dev/ttyUSB0 firmware.bin 3000000")
        return 1
    
    port = sys.argv[1]
    firmware_file = sys.argv[2]
    baudrate = int(sys.argv[3]) if len(sys.argv) > 3 else 115200
    
    success = ublox_firmware_update(port, firmware_file, baudrate)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
