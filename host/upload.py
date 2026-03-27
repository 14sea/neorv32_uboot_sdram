#!/usr/bin/env python3
"""
upload.py — Upload NEORV32 firmware to the AX301 via UART bootloader.

Boot sequence:
  1. Program FPGA: openFPGALoader → NEORV32 resets, bootloader starts at 19200 baud
  2. This script aborts the 8s auto-boot countdown with SPACE
  3. Sends 'u' to upload, streams neorv32_exe.bin (must wait for full "bin... " prompt)
  4. Sends 'e' to execute; bootloader jumps to 0x00000000
  5. App changes UART to APP_BAUD; host switches to match

Key pitfalls discovered during bringup:
  - FIFO overflow: send binary only AFTER full "Awaiting neorv32_exe.bin... " is received
    (bootloader's 1-byte RX FIFO overflows if binary arrives while bootloader is still printing)
  - Must send 'e' after 'u' — 'u' only uploads, does not auto-execute
  - No buffer flush after baud rate switch — banner arrives immediately after jump

Usage:
  python3 host/upload.py --port /dev/ttyUSB0 --exe sw/hello_world/neorv32_exe.bin
  python3 host/upload.py --port /dev/ttyUSB0 --exe sw/hello_world/neorv32_exe.bin --app-baud 19200
"""

import argparse
import sys
import time
import serial


BOOTLOADER_BAUD = 19200


def read_until(ser, pattern, timeout=6.0):
    buf = b""
    t0 = time.time()
    while time.time() - t0 < timeout:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            if pattern in buf:
                return buf
    return buf


def main():
    ap = argparse.ArgumentParser(description="NEORV32 bootloader firmware uploader")
    ap.add_argument("--port",     default="/dev/ttyUSB0")
    ap.add_argument("--exe",      required=True, help="Path to neorv32_exe.bin")
    ap.add_argument("--app-baud", type=int, default=115200,
                    help="Baud rate of the application (default 115200)")
    args = ap.parse_args()

    with open(args.exe, "rb") as f:
        exe_data = f.read()
    print(f"[*] Firmware: {args.exe} ({len(exe_data)} bytes)")
    print(f"[*] Opening {args.port} at {BOOTLOADER_BAUD} baud")

    ser = serial.Serial(args.port, BOOTLOADER_BAUD, timeout=0.5,
                        xonxoff=False, rtscts=False, dsrdtr=False)
    ser.dtr = False
    ser.rts = False
    time.sleep(0.2)
    ser.reset_input_buffer()

    # ── Wait for "Press any key to abort" then abort auto-boot ──
    print("[*] Waiting for bootloader prompt...")
    buf = read_until(ser, b"Press any key", timeout=6.0)
    if b"Press any key" not in buf:
        print("\n[!] Bootloader not responding. Is FPGA programmed?")
        ser.close(); sys.exit(1)

    ser.write(b" ")   # abort auto-boot
    buf = read_until(ser, b"CMD:>", timeout=4.0)
    if b"CMD:>" not in buf:
        print("\n[!] CMD:> not received"); ser.close(); sys.exit(1)

    # ── Upload ('u') ──
    ser.reset_input_buffer()
    ser.write(b"u")

    # Wait for FULL "Awaiting neorv32_exe.bin... " (including trailing space)
    # Critical: must wait until the full prompt is received before sending binary,
    # otherwise the 1-byte RX FIFO overflows while bootloader is still printing.
    buf2 = read_until(ser, b"bin... ", timeout=4.0)
    if b"bin... " not in buf2:
        print("\n[!] No upload prompt"); ser.close(); sys.exit(1)

    # 200ms delay for bootloader to finish printing and enter stream_get()
    time.sleep(0.2)
    ser.write(exe_data)
    ser.flush()

    buf3 = read_until(ser, b"OK", timeout=15.0)
    if b"ERROR" in buf3:
        print(f"\n[!] Upload error: {buf3[-40:]}"); ser.close(); sys.exit(1)
    if b"OK" not in buf3:
        print("\n[!] No OK response"); ser.close(); sys.exit(1)

    # ── Execute ('e') ──
    ser.write(b"e")
    read_until(ser, b"Booting", timeout=3.0)

    print(f"\n[+] Upload successful! App is running at {args.app_baud} baud.")
    if args.app_baud != BOOTLOADER_BAUD:
        print(f"[+] Switch terminal to {args.app_baud} baud: minicom -b {args.app_baud} -D {args.port}")
    ser.close()


if __name__ == "__main__":
    main()
