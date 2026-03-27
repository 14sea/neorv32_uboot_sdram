#!/usr/bin/env python3
#
# Copyright (c) 2026
#
# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.
#

"""
boot_uboot.py — Full boot sequence: FPGA → bootloader → stage2 → xmodem → U-Boot

Steps:
  1. Program FPGA with neorv32_demo_debug.rbf
  2. Bootloader (19200): upload stage2_loader, execute
  3. Stage2 (115200): send U-Boot via xmodem to SDRAM 0x40000000
  4. Stage2 jumps to U-Boot; interactive terminal
"""

import argparse
import os
import subprocess
import sys
import time
import serial

BOOTLOADER_BAUD = 19200
APP_BAUD = 115200
XMODEM_BLOCK_SIZE = 128
SOH = 0x01
EOT = 0x04
ACK = 0x06
NAK = 0x15


def read_until(ser, pattern, timeout=6.0, quiet=False):
    buf = b""
    t0 = time.time()
    while time.time() - t0 < timeout:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            if not quiet:
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
            if pattern in buf:
                return buf
    return buf


def xmodem_send(ser, data, timeout=3.0):
    """Send data via xmodem (checksum mode, 128-byte blocks)."""
    # Pad to multiple of 128
    pad_len = (XMODEM_BLOCK_SIZE - len(data) % XMODEM_BLOCK_SIZE) % XMODEM_BLOCK_SIZE
    data += b'\x1a' * pad_len  # SUB padding
    num_blocks = len(data) // XMODEM_BLOCK_SIZE

    print(f"[xmodem] {len(data)} bytes, {num_blocks} blocks")

    # NAK already received by caller; drain any extras
    ser.reset_input_buffer()
    time.sleep(0.05)

    # Send blocks
    for blk_idx in range(num_blocks):
        blk_num = (blk_idx + 1) & 0xFF
        offset = blk_idx * XMODEM_BLOCK_SIZE
        block = data[offset:offset + XMODEM_BLOCK_SIZE]
        csum = sum(block) & 0xFF

        packet = bytes([SOH, blk_num, (~blk_num) & 0xFF]) + block + bytes([csum])

        retries = 0
        while retries < 10:
            ser.write(packet)
            ser.flush()

            # Wait for ACK/NAK
            resp = b""
            t0 = time.time()
            while time.time() - t0 < timeout:
                c = ser.read(1)
                if c:
                    if c[0] == ACK:
                        break
                    elif c[0] == NAK:
                        retries += 1
                        break
                    else:
                        resp += c
            else:
                retries += 1
                continue

            if c and c[0] == ACK:
                break
        else:
            print(f"\n[!] Block {blk_idx} failed after retries")
            return False

        if (blk_idx + 1) % 100 == 0 or blk_idx == num_blocks - 1:
            pct = 100 * (blk_idx + 1) // num_blocks
            print(f"\r[xmodem] {blk_idx + 1}/{num_blocks} ({pct}%)", end="", flush=True)

    print()

    # Send EOT
    ser.write(bytes([EOT]))
    ser.flush()
    t0 = time.time()
    while time.time() - t0 < 5:
        c = ser.read(1)
        if c and c[0] == ACK:
            print("[xmodem] Transfer complete")
            return True
    print("[!] No ACK for EOT")
    return False


def main():
    ap = argparse.ArgumentParser(description="Boot U-Boot on NEORV32 AX301")
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--rbf", default=None,
                    help="Bitstream (default: neorv32_demo_debug.rbf)")
    ap.add_argument("--stage2", default=None,
                    help="Stage2 loader (default: sw/stage2_loader/neorv32_exe.bin)")
    ap.add_argument("--uboot", default=None,
                    help="U-Boot binary (default: ~/u-boot/u-boot.bin)")
    ap.add_argument("--skip-program", action="store_true",
                    help="Skip FPGA programming")
    args = ap.parse_args()

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rbf = args.rbf or os.path.join(base, "neorv32_demo.rbf")
    stage2 = args.stage2 or os.path.join(base, "sw", "stage2_loader", "neorv32_exe.bin")
    uboot = args.uboot or os.path.expanduser("~/u-boot/u-boot.bin")
    loader = os.path.join(base, "..", "openFPGALoader", "build", "openFPGALoader")

    for f, name in [(stage2, "stage2"), (uboot, "u-boot.bin")]:
        if not os.path.exists(f):
            print(f"[!] {name} not found: {f}")
            sys.exit(1)

    with open(stage2, "rb") as f:
        stage2_data = f.read()
    with open(uboot, "rb") as f:
        uboot_data = f.read()

    print(f"[*] stage2: {len(stage2_data)} bytes")
    print(f"[*] u-boot: {len(uboot_data)} bytes")

    # ── Step 1: Program FPGA ──
    if not args.skip_program:
        print(f"\n[1] Programming FPGA: {rbf}")
        r = subprocess.run([loader, "-c", "usb-blaster", rbf],
                           capture_output=True, text=True, timeout=30)
        print(r.stdout.strip())
        if r.returncode != 0:
            print(f"[!] Programming failed: {r.stderr}")
            sys.exit(1)

    # ── Step 2: Bootloader → upload stage2 ──
    print(f"\n[2] Connecting to bootloader at {BOOTLOADER_BAUD} baud...")
    time.sleep(0.3)
    ser = serial.Serial(args.port, BOOTLOADER_BAUD, timeout=1,
                        xonxoff=False, rtscts=False, dsrdtr=False)
    ser.dtr = False
    ser.rts = False
    time.sleep(0.1)
    ser.read(5000)  # drain stale JTAG bytes

    buf = b""
    t0 = time.time()
    while time.time() - t0 < 8:
        chunk = ser.read(500)
        if chunk:
            buf += chunk
        if b"CMD:>" in buf or b"Press any key" in buf:
            break

    if b"Press any key" in buf:
        ser.write(b" ")
        time.sleep(0.3)
        buf += ser.read(1000)
    elif b"CMD:>" not in buf:
        ser.write(b" ")
        time.sleep(0.5)
        buf += ser.read(1000)

    if b"CMD:>" not in buf:
        print(f"[!] No bootloader prompt. Got: {buf!r}")
        ser.close()
        sys.exit(1)
    print("[2] Bootloader ready")

    # Upload stage2
    ser.reset_input_buffer()
    ser.write(b"u")
    time.sleep(0.5)
    resp = ser.read(1000)
    if b"bin" not in resp:
        print(f"[!] No upload prompt: {resp!r}")
        ser.close()
        sys.exit(1)

    time.sleep(0.2)
    ser.write(stage2_data)
    ser.flush()

    resp = b""
    t0 = time.time()
    while time.time() - t0 < 15:
        resp += ser.read(500)
        if b"OK" in resp:
            break

    if b"OK" not in resp:
        print(f"[!] Stage2 upload failed: {resp!r}")
        ser.close()
        sys.exit(1)
    print(f"[2] Stage2 uploaded ({len(stage2_data)} bytes)")

    # Execute stage2
    ser.write(b"e")
    time.sleep(0.05)

    # ── Step 3: Switch to 115200, wait for stage2 prompt ──
    ser.baudrate = APP_BAUD
    print(f"\n[3] Switched to {APP_BAUD} baud, waiting for stage2...")

    # Read stage2 output until we see NAK byte (0x15) = xmodem ready
    buf = b""
    t0 = time.time()
    while time.time() - t0 < 15:
        chunk = ser.read(500)
        if chunk:
            buf += chunk
            # Print readable parts
            try:
                text = chunk.decode("ascii", errors="replace")
                sys.stdout.write(text)
                sys.stdout.flush()
            except:
                pass
        # Stage2 sends NAK when ready for xmodem
        if bytes([NAK]) in buf:
            break

    if bytes([NAK]) not in buf:
        print(f"\n[!] Stage2 not ready (no NAK). Got: {buf[-200:]!r}")
        ser.close()
        sys.exit(1)

    # ── Step 4: Send U-Boot via xmodem ──
    print(f"\n[4] Sending U-Boot ({len(uboot_data)} bytes) via xmodem...")
    if not xmodem_send(ser, uboot_data):
        print("[!] xmodem transfer failed")
        ser.close()
        sys.exit(1)

    # ── Step 5: Watch stage2 verify + jump, then U-Boot output ──
    print("\n[5] Waiting for U-Boot...")
    t0 = time.time()
    while time.time() - t0 < 15:
        data = ser.read(500)
        if data:
            try:
                text = data.decode("ascii", errors="replace")
                sys.stdout.write(text)
                sys.stdout.flush()
            except:
                print(repr(data))

    ser.close()
    print("\n\n[*] Done. Use minicom -b 115200 -D /dev/ttyUSB0 for interactive U-Boot.")


if __name__ == "__main__":
    main()
