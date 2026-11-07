#!/usr/bin/env python3
"""Query a Brother PT-P300BT over its Bluetooth serial port and decode the status reply."""
import os
import select
import shutil
import subprocess
import sys
import termios
import time

PORT = "/dev/cu.PT-P300BT8261"
PRINTER_ADDRESS = "98-6e-e8-48-10-d6"

MEDIA_TYPES = {0x00: "none", 0x01: "laminated", 0x03: "non-laminated",
               0x11: "heat-shrink", 0x17: "laminated (TZe)", 0xFF: "incompatible"}
ERR1 = {0x01: "no media", 0x04: "cutter jam", 0x08: "weak batteries", 0x40: "high-voltage adapter"}
ERR2 = {0x01: "wrong media", 0x10: "cover open", 0x20: "overheating"}
STATUS_TYPES = {0x00: "reply to status request", 0x01: "printing completed", 0x02: "error",
                0x04: "turned off", 0x05: "notification", 0x06: "phase change"}


def reconnect(address=PRINTER_ADDRESS):
    """Re-pair before each session.

    With this printer on macOS, a fresh pairing allows exactly one serial session;
    once the port is closed, later opens get no reply until the device is re-paired.
    """
    blueutil = shutil.which("blueutil") or "/opt/homebrew/bin/blueutil"
    if not os.path.exists(blueutil):
        sys.exit("blueutil not found: brew install blueutil")
    run = lambda *args: subprocess.run([blueutil, *args], capture_output=True, timeout=45)
    run("--unpair", address)
    time.sleep(2)
    run("--pair", address, "0000")
    deadline = time.time() + 30
    while not os.path.exists(PORT) and time.time() < deadline:
        run("--connect", address)
        time.sleep(3)
    if not os.path.exists(PORT):
        sys.exit(f"{PORT} did not appear after re-pairing; is the printer on?")
    time.sleep(2)


def open_port(path):
    reconnect()
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY)
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0                                   # iflag
    attrs[1] = 0                                   # oflag
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[3] = 0                                   # lflag (raw)
    attrs[4] = attrs[5] = termios.B9600
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    return fd


def read_exact(fd, n, timeout):
    buf = b""
    deadline = time.time() + timeout
    while len(buf) < n:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        ready, _, _ = select.select([fd], [], [], remaining)
        if ready:
            buf += os.read(fd, n - len(buf))
    return buf


def decode(reply):
    flags = lambda v, table: [name for bit, name in table.items() if v & bit] or ["none"]
    return {
        "errors": flags(reply[8], ERR1) + ([] if reply[9] == 0 else flags(reply[9], ERR2)),
        "tape width (mm)": reply[10],
        "media type": MEDIA_TYPES.get(reply[11], hex(reply[11])),
        "status type": STATUS_TYPES.get(reply[18], hex(reply[18])),
    }


def main():
    print(f"Opening {PORT} ...")
    fd = open_port(PORT)
    try:
        os.write(fd, b"\x00" * 100)      # invalidate
        os.write(fd, b"\x1b\x40")        # initialize
        os.write(fd, b"\x1b\x69\x53")    # status request
        reply = read_exact(fd, 32, timeout=10)
    finally:
        os.close(fd)
    if len(reply) != 32:
        sys.exit(f"Expected 32 bytes, got {len(reply)}: {reply.hex()}")
    print("Raw:", reply.hex())
    for k, v in decode(reply).items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
