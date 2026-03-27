#!/usr/bin/env python3
#
# Copyright (c) 2026
#
# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.
#

"""Quick test: bootloader → stage2 → xmodem send minimal SDRAM test binary."""

import sys, time, serial

PORT = "/dev/ttyUSB0"
STAGE2 = "/home/test/fpga/neorv32_demo/sw/stage2_loader/neorv32_exe.bin"
PAYLOAD = "/home/test/fpga/neorv32_demo/sw/sdram_hello/sdram_xmodem_test.bin"  # multi-addr SDRAM R/W test

SOH, EOT, ACK, NAK = 0x01, 0x04, 0x06, 0x15

def xmodem_send(ser, data):
    pad = (128 - len(data) % 128) % 128
    data += b'\x1a' * pad
    nblk = len(data) // 128
    ser.reset_input_buffer()
    time.sleep(0.05)
    for i in range(nblk):
        bn = (i + 1) & 0xFF
        blk = data[i*128:(i+1)*128]
        csum = sum(blk) & 0xFF
        pkt = bytes([SOH, bn, (~bn) & 0xFF]) + blk + bytes([csum])
        for _ in range(10):
            ser.write(pkt); ser.flush()
            t0 = time.time()
            while time.time() - t0 < 3:
                c = ser.read(1)
                if c and c[0] == ACK: break
                elif c and c[0] == NAK: break
            else: continue
            if c[0] == ACK: break
        else:
            print(f"Block {i} failed"); return False
    ser.write(bytes([EOT])); ser.flush()
    t0 = time.time()
    while time.time() - t0 < 5:
        c = ser.read(1)
        if c and c[0] == ACK: return True
    return False

with open(STAGE2, "rb") as f: stage2 = f.read()
with open(PAYLOAD, "rb") as f: payload = f.read()
print(f"stage2: {len(stage2)}B, payload: {len(payload)}B")

# Step 1: bootloader at 19200
ser = serial.Serial(PORT, 19200, timeout=1)
ser.dtr = False; ser.rts = False
time.sleep(0.1)
ser.read(5000)  # drain

buf = b""
t0 = time.time()
while time.time() - t0 < 8:
    buf += ser.read(500)
    if b"CMD:>" in buf or b"Press any key" in buf: break

if b"Press any key" in buf:
    ser.write(b" "); time.sleep(0.3); buf += ser.read(1000)
elif b"CMD:>" not in buf:
    ser.write(b" "); time.sleep(0.5); buf += ser.read(1000)

if b"CMD:>" not in buf:
    print(f"No prompt: {buf!r}"); sys.exit(1)
print("Bootloader ready")

# Upload stage2
ser.reset_input_buffer()
ser.write(b"u"); time.sleep(0.5)
resp = ser.read(1000)
if b"bin" not in resp:
    print(f"No upload prompt: {resp!r}"); sys.exit(1)

time.sleep(0.2)
ser.write(stage2); ser.flush()
resp = b""
t0 = time.time()
while time.time() - t0 < 15:
    resp += ser.read(500)
    if b"OK" in resp: break
if b"OK" not in resp:
    print(f"Upload failed: {resp!r}"); sys.exit(1)
print("Stage2 uploaded")

# Execute
ser.write(b"e"); time.sleep(0.05)
ser.baudrate = 115200
print("Switched to 115200, waiting for NAK...")

buf = b""
t0 = time.time()
while time.time() - t0 < 15:
    chunk = ser.read(500)
    if chunk:
        buf += chunk
        sys.stdout.write(chunk.decode("ascii", errors="replace"))
        sys.stdout.flush()
    if bytes([NAK]) in buf: break

if bytes([NAK]) not in buf:
    print(f"\nNo NAK: {buf!r}"); sys.exit(1)

# xmodem send payload
print(f"\nSending {len(payload)}B via xmodem...")
if not xmodem_send(ser, payload):
    print("xmodem failed"); sys.exit(1)
print("xmodem done!")

# Watch output
print("Waiting for SDRAM output...")
t0 = time.time()
while time.time() - t0 < 10:
    data = ser.read(500)
    if data:
        sys.stdout.write(data.decode("ascii", errors="replace"))
        sys.stdout.flush()

ser.close()
print("\nDone.")
