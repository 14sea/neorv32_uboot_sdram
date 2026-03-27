#!/usr/bin/env python3
"""
load_uboot.py — Upload stage2_loader then send U-Boot via xmodem.

Flow:
  1. Program FPGA with NEORV32 bitstream (if --rbf given)
  2. Upload stage2_loader.exe via NEORV32 bootloader (19200 baud)
  3. stage2_loader starts, switches to 115200 baud
  4. Host sends U-Boot binary via xmodem (115200 baud)
  5. stage2_loader jumps to 0x40000000 → U-Boot starts

Usage:
  python3 host/load_uboot.py --stage2 sw/stage2_loader/neorv32_exe.bin \
      --uboot /home/test/u-boot/u-boot.bin --port /dev/ttyUSB0
"""

import argparse
import sys
import time
import subprocess
import serial

BOOTLOADER_BAUD = 19200
STAGE2_BAUD     = 115200

# xmodem constants
SOH = 0x01
EOT = 0x04
ACK = 0x06
NAK = 0x15
CAN = 0x18


def read_until(ser, pattern, timeout=8.0, echo=True):
    buf = b""
    t0 = time.time()
    while time.time() - t0 < timeout:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            if echo:
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
            if pattern in buf:
                return buf
    return buf


def upload_stage2(ser, exe_data):
    """Upload stage2_loader via NEORV32 bootloader."""
    print("[*] Waiting for NEORV32 bootloader 'Press any key'...")
    buf = read_until(ser, b"Press any key", timeout=10.0)
    if b"Press any key" not in buf:
        print("\n[!] Bootloader not found"); return False

    ser.write(b" ")   # abort countdown
    buf = read_until(ser, b"CMD:>", timeout=4.0)
    if b"CMD:>" not in buf:
        print("\n[!] CMD:> not received"); return False

    # Upload command
    ser.reset_input_buffer()
    ser.write(b"u")
    buf2 = read_until(ser, b"bin... ", timeout=4.0)
    if b"bin... " not in buf2:
        print("\n[!] No upload prompt"); return False

    time.sleep(0.2)
    ser.write(exe_data)
    ser.flush()

    buf3 = read_until(ser, b"OK", timeout=15.0)
    if b"ERROR" in buf3:
        print("\n[!] Upload error"); return False
    if b"OK" not in buf3:
        print("\n[!] No OK"); return False

    # Execute
    ser.write(b"e")
    return True


def xmodem_send(ser, data):
    """Send data via xmodem (checksum variant)."""
    # Pad to multiple of 128
    pad = (-len(data)) % 128
    data = data + bytes([0x1A] * pad)
    n_blocks = len(data) // 128

    print(f"[*] xmodem: sending {len(data)} bytes in {n_blocks} blocks")

    # Wait for NAK from receiver
    print("[*] Waiting for NAK from stage2_loader...")
    t0 = time.time()
    while time.time() - t0 < 10.0:
        if ser.in_waiting:
            c = ser.read(1)
            if c == bytes([NAK]):
                break
    else:
        print("[!] No NAK received"); return False

    for blk in range(n_blocks):
        blk_data = data[blk*128:(blk+1)*128]
        blk_num  = (blk + 1) & 0xFF
        csum     = sum(blk_data) & 0xFF

        pkt = bytes([SOH, blk_num, (~blk_num) & 0xFF]) + blk_data + bytes([csum])

        retries = 0
        while retries < 10:
            ser.write(pkt)
            ser.flush()

            # Wait for ACK/NAK
            t0 = time.time()
            resp = b""
            while time.time() - t0 < 3.0:
                if ser.in_waiting:
                    resp += ser.read(1)
                    if resp[-1:] in (bytes([ACK]), bytes([NAK]), bytes([CAN])):
                        break

            if resp and resp[-1] == ACK:
                break
            elif resp and resp[-1] == CAN:
                print("\n[!] Receiver cancelled"); return False
            else:
                retries += 1
                print(f"\r[*] block {blk+1}/{n_blocks} NAK retry {retries}", end="")

        if retries >= 10:
            print(f"\n[!] block {blk+1} failed after 10 retries"); return False

        if (blk + 1) % 32 == 0 or blk + 1 == n_blocks:
            print(f"\r[*] xmodem: {blk+1}/{n_blocks} blocks sent", end="", flush=True)

    print()

    # Send EOT
    for _ in range(3):
        ser.write(bytes([EOT]))
        t0 = time.time()
        while time.time() - t0 < 2.0:
            if ser.in_waiting:
                c = ser.read(1)
                if c == bytes([ACK]):
                    print("[+] EOT acknowledged")
                    return True
        time.sleep(0.1)

    print("[!] EOT not ACKed"); return True  # U-Boot likely already jumping


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port",   default="/dev/ttyUSB0")
    ap.add_argument("--stage2", required=True, help="stage2_loader neorv32_exe.bin")
    ap.add_argument("--uboot",  required=True, help="u-boot.bin")
    ap.add_argument("--rbf",    default=None,  help="FPGA bitstream .rbf (optional, skip if omitted)")
    ap.add_argument("--fpga-loader", default="/home/test/fpga/openFPGALoader/build/openFPGALoader")
    args = ap.parse_args()

    with open(args.stage2, "rb") as f: stage2_data = f.read()
    with open(args.uboot,  "rb") as f: uboot_data  = f.read()
    print(f"[*] stage2: {len(stage2_data)} bytes")
    print(f"[*] U-Boot: {len(uboot_data)} bytes")

    ser = serial.Serial(args.port, BOOTLOADER_BAUD, timeout=0.5,
                        xonxoff=False, rtscts=False, dsrdtr=False)
    ser.dtr = False; ser.rts = False
    time.sleep(0.1)
    ser.reset_input_buffer()

    # Program FPGA first (if rbf given)
    if args.rbf:
        print(f"[*] Programming FPGA: {args.rbf}")
        ret = subprocess.run([args.fpga_loader, "-c", "usb-blaster", args.rbf],
                             capture_output=True, text=True)
        print(ret.stdout.strip())
        if ret.returncode != 0:
            print(f"[!] FPGA programming failed: {ret.stderr}"); sys.exit(1)
    else:
        print("[*] Skipping FPGA programming (no --rbf)")
        # Trigger reset by toggling DTR
        ser.dtr = True; time.sleep(0.05); ser.dtr = False

    # Upload stage2 via bootloader
    if not upload_stage2(ser, stage2_data):
        ser.close(); sys.exit(1)

    # Switch to 115200 baud
    print(f"\n[*] Switching to {STAGE2_BAUD} baud...")
    ser.close()
    time.sleep(0.3)
    ser = serial.Serial(args.port, STAGE2_BAUD, timeout=0.5,
                        xonxoff=False, rtscts=False, dsrdtr=False)

    # Wait for stage2 to send NAK (stage2 resends NAK every 3s)
    print("[*] Waiting for stage2 NAK...")
    t0 = time.time()
    got_nak = False
    while time.time() - t0 < 15.0:
        if ser.in_waiting:
            b = ser.read(ser.in_waiting)
            sys.stdout.buffer.write(b); sys.stdout.buffer.flush()
            if bytes([NAK]) in b:
                got_nak = True
                break
        time.sleep(0.05)
    if not got_nak:
        print("\n[!] stage2 not ready (no NAK)"); ser.close(); sys.exit(1)

    # Send U-Boot via xmodem
    if not xmodem_send(ser, uboot_data):
        ser.close(); sys.exit(1)

    # Read U-Boot output for up to 15 seconds
    print("[*] Reading U-Boot output...")
    ser.timeout = 0.1
    t0 = time.time()
    all_output = b""
    last_data = time.time()
    while time.time() - t0 < 15.0:
        chunk = ser.read(256)
        if chunk:
            all_output += chunk
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            last_data = time.time()
            # Stop early if we get the prompt
            if b"=>" in all_output or b"U-Boot>" in all_output:
                # Got prompt — send a command
                time.sleep(0.2)
                ser.write(b"version\r\n")
                time.sleep(1)
                more = ser.read(512)
                sys.stdout.buffer.write(more)
                sys.stdout.buffer.flush()
                break
        elif time.time() - last_data > 5.0 and all_output:
            # No new data for 5s after receiving something
            break

    if b"U-Boot" in all_output:
        print("\n\n[+] U-Boot confirmed running!")
    else:
        print("\n\n[?] U-Boot banner not seen in output")

    print(f"[+] Connect terminal: minicom -b {STAGE2_BAUD} -D {args.port}")
    ser.close()


if __name__ == "__main__":
    main()
