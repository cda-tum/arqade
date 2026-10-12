"""Lock and unlock the cabinet from the cabinet itself -- no laptop needed.

`kiosk.py --lock` takes START/SELECT/X/Y away from EmulationStation, so there
is no way back in from the pads through ES. This watches the joysticks
directly, underneath ES, for a secret button sequence and runs
`kiosk.py --toggle` when it sees it -- locking if unlocked and unlocking if
locked, so the same code gets you both in and out.

It also watches for **Start + Select held on both pads at once**, and runs
`experimental.py --toggle` for it: the games that aren't public yet join the
game list, or leave it again (see experimental.py). That needs both hands on
both pads, which nobody does by accident, and Start/Select are inert in a
locked ES anyway.

    python3 unlock_daemon.py            # run it (this is what boot does)
    python3 unlock_daemon.py --install  # start it on every boot
    python3 unlock_daemon.py --watch    # print presses, change nothing

**The sequence is L R L R X**, on either pad, within SEQUENCE_WINDOW seconds.

Why that one, and why it cannot fire by accident:

  - The lockdown removed x, y, pageup and pagedown from es_input.cfg, and L/R
    *were* pageup/pagedown. So all three of these buttons are now completely
    inert in EmulationStation -- nothing on screen reacts while you type it.
  - In a game they are live (Qlimbers gates, Ion Surfer's sandbox), so the
    daemon ignores everything while a game is running. See game_running().

Cost: none worth measuring. It blocks in select() and the kernel does not
schedule it until a button is physically pressed -- idle CPU is 0.0%, not
"low". It reads the devices without EVIOCGRAB, so it only observes and can
never take input away from ES or from a game.
"""

import fcntl
import os
import select
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

# Raw joystick indices, the numbers the games and es_input.cfg use. See
# "Confirmed raw button numbers" in AGENTS.md.
BUTTON = {"X": 0, "A": 1, "B": 2, "Y": 3, "L": 4, "R": 5, "SELECT": 8, "START": 9}

SEQUENCE = [BUTTON[n] for n in ("L", "R", "L", "R", "X")]
SEQUENCE_WINDOW = 6.0  # seconds to complete it before the attempt resets
RESCAN_INTERVAL = 5.0  # seconds between looks for newly plugged-in pads

KIOSK = Path("/userdata/kiosk.py")
EXPERIMENTAL = Path("/userdata/experimental.py")
ROMS = "/userdata/roms/pygame"
LOG = Path("/userdata/system/logs/arqade-unlock.log")
CUSTOM_SH = Path("/userdata/system/custom.sh")
SELF = Path(__file__).resolve()

EV_KEY = 0x01
EVENT_SIZE = struct.calcsize("llHHi")  # 24 bytes: timeval, type, code, value
EVIOCGNAME = 0x81004506  # _IOR('E', 0x06, 256)
KEY_MAX = 0x2FF
BTN_JOYSTICK = 0x120  # 288
KEY_BYTES = KEY_MAX // 8 + 1
EVIOCGBIT_KEY = 0x80000000 | (KEY_BYTES << 16) | (ord("E") << 8) | (0x20 + EV_KEY)


def log(message: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"{stamp} {message}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as fh:
            fh.write(line + "\n")
    except OSError:
        pass  # logging must never take the daemon down


def device_name(fd: int) -> str:
    buf = bytearray(256)
    try:
        fcntl.ioctl(fd, EVIOCGNAME, buf)
    except OSError:
        return ""
    return buf.split(b"\0", 1)[0].decode("utf-8", "replace").strip()


def button_indices(fd: int) -> dict[int, int]:
    """evdev key code -> the raw button index SDL (pygame, ES) gives it.

    SDL numbers a joystick's buttons by counting the key codes the device
    has, from BTN_JOYSTICK upwards and then the ones below it. So the raw
    index is 288 + n only while the device has every code in between: true
    for X/A/B/Y/L/R here (confirmed against es_input.cfg), but not something
    to assume for Select (8) and Start (9).
    """
    bits = bytearray(KEY_BYTES)
    try:
        fcntl.ioctl(fd, EVIOCGBIT_KEY, bits)
    except OSError:
        return {}
    codes = [c for c in range(KEY_MAX) if bits[c // 8] >> (c % 8) & 1]
    ordered = [c for c in codes if c >= BTN_JOYSTICK] + [c for c in codes if c < BTN_JOYSTICK]
    return {code: raw for raw, code in enumerate(ordered)}


def open_pads(known: set[str] | None = None) -> dict[int, tuple[str, str, dict[int, int]]]:
    """Open every gamepad event device not already open, read-only, no grab.

    Rescanned periodically rather than opened once: a controller unplugged and
    plugged back in comes up as a new event node, and a daemon holding only
    the fds it found at boot would silently stop seeing that pad forever.
    """
    known = known or set()
    pads = {}
    for path in sorted(Path("/dev/input").glob("event*")):
        if path.name in known:
            continue
        try:
            fd = os.open(str(path), os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            continue
        name = device_name(fd)
        if "gamepad" in name.lower() or "joystick" in name.lower():
            pads[fd] = (path.name, f"{path.name} ({name})", button_indices(fd))
        else:
            os.close(fd)
    return pads


def game_running() -> bool:
    """True while a .pygame ROM is running.

    L/R/X are real gameplay buttons inside the games, so the sequence must be
    ignored there -- otherwise Ion Surfer's sandbox could spell it by accident.
    """
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if ROMS in (entry / "cmdline").read_bytes().decode("utf-8", "replace"):
                return True
        except OSError:
            continue
    return False


def hand_off(script: Path, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, str(script), *args], capture_output=True, text=True
    )
    for line in (result.stdout + result.stderr).splitlines():
        log(f"  {script.name}: {line}")
    log(f"{script.name} finished (rc={result.returncode})")


def toggle_lock() -> None:
    """Hand off to kiosk.py --toggle: lock if unlocked, unlock if locked.

    It must toggle. An unlock-only sequence leaves no way back *into* kiosk
    mode from the cabinet, so re-entering the code just unlocks an already
    unlocked machine and you are stuck in admin mode without a laptop.
    """
    log("sequence matched -- toggling the lock")
    hand_off(KIOSK, "--toggle")


def reset_experimental() -> None:
    """At start-up, i.e. at every boot: make sure ES shows the public list.

    ES may have scanned experimental mode's links before its `start` hook
    removed them (it doesn't wait for event scripts), so experimental.py
    --reset waits for ES and takes the parked games out of its list. In a
    thread, because that wait can take a minute and the pads are watched
    meanwhile.
    """
    if EXPERIMENTAL.exists():
        threading.Thread(target=hand_off, args=(EXPERIMENTAL, "--reset"), daemon=True).start()


def toggle_experimental() -> None:
    log("Start + Select held on both pads -- toggling the experimental games")
    hand_off(EXPERIMENTAL, "--toggle")


class BothPadsCombo:
    """Start + Select held on two pads at once, reported once per hold.

    It fires on the press that completes the combo, whichever of the four
    that is, and not again until every one of those buttons is let go.
    """

    KEYS = (BUTTON["START"], BUTTON["SELECT"])

    def __init__(self) -> None:
        self.held: set[tuple[int, int]] = set()  # (pad, raw button)
        self.armed = True

    def press(self, pad: int, raw: int) -> bool:
        if raw not in self.KEYS:
            return False
        self.held.add((pad, raw))
        pads = {p for p, _ in self.held if all((p, k) in self.held for k in self.KEYS)}
        if len(pads) >= 2 and self.armed:
            self.armed = False
            return True
        return False

    def release(self, pad: int, raw: int) -> None:
        self.held.discard((pad, raw))
        if not self.held:
            self.armed = True

    def forget(self, pad: int) -> None:
        """A pad was unplugged: its buttons will never report a release."""
        self.held = {(p, k) for p, k in self.held if p != pad}
        if not self.held:
            self.armed = True


def run(watch_only: bool = False) -> None:
    pads = open_pads()
    for _, description, _ in pads.values():
        log(f"watching {description}")
    if not pads:
        log("no gamepads yet -- will keep looking")
    log("sequence is L R L R X" + (" (watch mode, changes nothing)" if watch_only else ""))
    if not watch_only:
        reset_experimental()

    combo = BothPadsCombo()
    progress = 0
    started = 0.0
    next_scan = time.monotonic() + RESCAN_INTERVAL
    while True:
        ready, _, _ = select.select(list(pads), [], [], 1.0)
        now = time.monotonic()
        if progress and now - started > SEQUENCE_WINDOW:
            progress = 0  # took too long, start over

        if now >= next_scan:
            next_scan = now + RESCAN_INTERVAL
            for fd, entry in open_pads({name for name, _, _ in pads.values()}).items():
                pads[fd] = entry
                log(f"watching {entry[1]} (new)")

        for fd in ready:
            try:
                data = os.read(fd, EVENT_SIZE * 64)
            except OSError:
                # Device went away (unplugged); drop it and let the rescan
                # pick it up again if it comes back.
                log(f"lost {pads[fd][1]}")
                os.close(fd)
                del pads[fd]
                combo.forget(fd)
                continue
            indices = pads[fd][2]
            for offset in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
                _, _, etype, code, value = struct.unpack(
                    "llHHi", data[offset:offset + EVENT_SIZE]
                )
                if etype != EV_KEY:
                    continue
                raw = indices.get(code, code - BTN_JOYSTICK)
                if value == 0:
                    combo.release(fd, raw)
                    continue
                if value != 1:  # 2 is autorepeat
                    continue
                if watch_only:
                    log(f"press: {pads[fd][0]} code {code} (raw index {raw})")
                    continue
                # Tracked even in a game, so a combo still held when the game
                # quits doesn't fire in the menu; it only acts outside one.
                both_pads = combo.press(fd, raw)
                if game_running():
                    progress = 0
                    continue
                if both_pads:
                    progress = 0
                    toggle_experimental()
                    continue
                if raw == SEQUENCE[progress]:
                    if progress == 0:
                        started = now
                    progress += 1
                    if progress == len(SEQUENCE):
                        progress = 0
                        toggle_lock()
                else:
                    # A wrong button restarts, but still counts as a first
                    # press if it happens to be the sequence's own opener.
                    progress = 1 if raw == SEQUENCE[0] else 0
                    started = now


def install() -> None:
    """Start the daemon on every boot via /userdata/system/custom.sh.

    S99userservices runs that file late in boot, which is fine here: this only
    needs to be up before somebody wants to unlock, not before ES. (The
    wallpaper hook is the opposite case and has to run at S00 -- see AGENTS.md.)
    """
    marker = "# arqade-unlock"
    # The stop pattern is bracketed on purpose. `pkill -f unlock_daemon.py`
    # also matches any shell whose own command line contains that text --
    # including the one running this script -- and kills it. Writing one
    # character as a character class makes the pattern no longer match its
    # own spelling, while still matching the daemon.
    script = f"""#!/bin/bash
{marker}: watch the pads for the unlock sequence and combo, see {SELF.name}
case "$1" in
    start) setsid nohup python3 {SELF} >/dev/null 2>&1 < /dev/null & ;;
    stop)  pkill -f 'unlock_daemo[n]\\.py' ;;
esac
"""
    if CUSTOM_SH.exists() and marker not in CUSTOM_SH.read_text():
        print(f"SKIPPED {CUSTOM_SH}: already exists and isn't ours -- merge by hand")
        return
    CUSTOM_SH.parent.mkdir(parents=True, exist_ok=True)
    CUSTOM_SH.write_text(script)
    CUSTOM_SH.chmod(0o755)
    print(f"wrote {CUSTOM_SH} -- the daemon will start on every boot")


if __name__ == "__main__":
    if "--install" in sys.argv:
        install()
    else:
        run(watch_only="--watch" in sys.argv)
