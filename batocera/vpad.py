"""Drive the cabinet's UI from SSH with a fake pad, for testing only.

Creates a uinput joystick with the same bus/vendor/product/version as the
cabinet's real encoders, so SDL derives the identical GUID
(030000001f08000001e4000010010000) and EmulationStation applies the same
es_input.cfg entry to it. That makes it a faithful stand-in for pressing the
real buttons -- which is the only way to check a lockdown actually holds
without standing at the cabinet.

    python3 vpad.py --seq 'wait:4,shot:start,tap:297,shot:after-start'

Steps: wait:SEC | tap:CODE | hold:CODE:SEC | down:CODE | up:CODE |
axis:CODE:VALUE | shot:NAME. (down/up are for combos, e.g. the games' own
start+select quit.)
Button CODEs are evdev codes; es_input.cfg lists them next to each input
(a=289, b=290, x=288, y=291, select=296, start=297). Screenshots land in
--shot-dir.

Not part of the cabinet install -- a diagnostic, like --input-test.
"""

import argparse
import fcntl
import os
import struct
import subprocess
import time
from pathlib import Path

EV_SYN, EV_KEY, EV_ABS = 0x00, 0x01, 0x03
UI_SET_EVBIT, UI_SET_KEYBIT = 0x40045564, 0x40045565
UI_SET_ABSBIT = 0x40045567
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502

# Matches the GUID bytes "0300 0000 1f08 0000 01e4 0000 1001 0000": each pair
# is a little-endian u16, and the zero CRC field means SDL is not mixing the
# device name in.
BUS, VENDOR, PRODUCT, VERSION = 0x0003, 0x081F, 0xE401, 0x0110
DEVICE_NAME = b"USB gamepad           "

BUTTONS = range(288, 298)  # BTN_TRIGGER .. BTN_BASE4 == SDL buttons 0..9
AXES = (0, 1)  # ABS_X, ABS_Y
AXIS_MIN, AXIS_MAX, AXIS_CENTRE = 0, 255, 127

GRIM_ENV = {**os.environ, "XDG_RUNTIME_DIR": "/var/run", "WAYLAND_DISPLAY": "wayland-1"}


def open_device() -> int:
    fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
    for ev in (EV_KEY, EV_ABS):
        fcntl.ioctl(fd, UI_SET_EVBIT, ev)
    for code in BUTTONS:
        fcntl.ioctl(fd, UI_SET_KEYBIT, code)
    for axis in AXES:
        fcntl.ioctl(fd, UI_SET_ABSBIT, axis)

    absmax, absmin = [0] * 64, [0] * 64
    for axis in AXES:
        absmax[axis], absmin[axis] = AXIS_MAX, AXIS_MIN
    payload = (
        DEVICE_NAME.ljust(80, b"\0")
        + struct.pack("HHHH", BUS, VENDOR, PRODUCT, VERSION)
        + struct.pack("I", 0)
        + struct.pack("64i", *absmax)
        + struct.pack("64i", *absmin)
        + struct.pack("64i", *([0] * 64))  # absfuzz
        + struct.pack("64i", *([0] * 64))  # absflat
    )
    os.write(fd, payload)
    fcntl.ioctl(fd, UI_DEV_CREATE)
    return fd


def emit(fd: int, kind: int, code: int, value: int) -> None:
    os.write(fd, struct.pack("llHHi", 0, 0, kind, code, value))


def sync(fd: int) -> None:
    emit(fd, EV_SYN, 0, 0)


def run(fd: int, steps: list[str], shot_dir: Path) -> None:
    for step in steps:
        action, _, rest = step.partition(":")
        parts = rest.split(":")
        if action == "wait":
            time.sleep(float(parts[0]))
        elif action == "tap":
            emit(fd, EV_KEY, int(parts[0]), 1), sync(fd)
            time.sleep(0.08)
            emit(fd, EV_KEY, int(parts[0]), 0), sync(fd)
            time.sleep(0.6)
        elif action == "hold":
            emit(fd, EV_KEY, int(parts[0]), 1), sync(fd)
            time.sleep(float(parts[1]))
            emit(fd, EV_KEY, int(parts[0]), 0), sync(fd)
            time.sleep(0.6)
        elif action == "down":  # press and keep held, for combos like start+select
            emit(fd, EV_KEY, int(parts[0]), 1), sync(fd)
            time.sleep(0.15)
        elif action == "up":
            emit(fd, EV_KEY, int(parts[0]), 0), sync(fd)
            time.sleep(0.15)
        elif action == "axis":
            emit(fd, EV_ABS, int(parts[0]), int(parts[1])), sync(fd)
            time.sleep(0.3)
        elif action == "shot":
            out = shot_dir / f"{parts[0]}.png"
            subprocess.run(["grim", str(out)], env=GRIM_ENV, check=False)
            print(f"shot {out}")
        else:
            raise SystemExit(f"unknown step: {step}")


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--seq", required=True, help="comma-separated steps")
parser.add_argument("--shot-dir", default="/tmp/vpad")
args = parser.parse_args()

shot_dir = Path(args.shot_dir)
shot_dir.mkdir(parents=True, exist_ok=True)

fd = open_device()
try:
    time.sleep(2)  # let SDL/ES notice the hotplug
    for axis in AXES:  # centre the stick, or ES reads 0 as "up" and scrolls
        emit(fd, EV_ABS, axis, AXIS_CENTRE)
    sync(fd)
    time.sleep(0.5)
    run(fd, args.seq.split(","), shot_dir)
finally:
    fcntl.ioctl(fd, UI_DEV_DESTROY)
    os.close(fd)
print("done")
