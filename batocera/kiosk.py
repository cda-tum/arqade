"""Lock the cabinet down so nobody can reach EmulationStation's menus.

Run on the arcade:
    python3 /userdata/kiosk.py --lock      # public-facing
    python3 /userdata/kiosk.py --unlock    # back to normal
    python3 /userdata/kiosk.py --status
    python3 /userdata/kiosk.py --screensaver   # the attract reels after 15 s idle

Why not ES's own UI Mode? Kiosk and Kid only *hide* menu entries -- START
still opens a menu and some settings are still reachable. There is no
"no menu at all" setting (the ES binary has ForceKiosk/ForceKid and
ShowHelpPrompts, but nothing that disables the menu), so instead we take the
inputs that open menus away from the joysticks:

  - START  opens the main menu
  - SELECT opens the view/game options menu

Dropping those two <input> lines from every joystick in es_input.cfg means
ES never sees the button at all, so there is nothing to hide and nothing to
unlock. Browsing and launching games (d-pad + A/B) is untouched.

**The keyboard mapping is deliberately left alone** -- that is the way back
in. Plug a USB keyboard into the cabinet and SPACE opens the main menu,
ESC/ENTER navigate, F1 is the file manager. No passkey to remember, and
physical access to a keyboard port is the "password". (So is SSH: just run
this script with --unlock.)

The games are unaffected either way: they read the joysticks directly
through pygame and never consult es_input.cfg, so Start+Select still quits
a game.
"""

import argparse
import os
import re
import shutil
import signal
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

# The compositor session ES has to draw on. Same values `grim` needs for a
# remote screenshot, and the same reason: an SSH session inherits none of it.
SWAY_ENV = {
    "XDG_RUNTIME_DIR": "/var/run",
    "WAYLAND_DISPLAY": "wayland-1",
    "SWAYSOCK": "/var/run/sway-ipc.0.sock",
}

ES_CONFIG = Path("/userdata/system/configs/emulationstation")
INPUT_CFG = ES_CONFIG / "es_input.cfg"
INPUT_BACKUP = ES_CONFIG / "es_input.cfg.arqade-orig"
SETTINGS_CFG = ES_CONFIG / "es_settings.cfg"

# Every joystick input that opens a menu or edits the library. Read them off
# the help bar in the game list: SELECT=OPTIONS, START=MENU, X/Y=SAVE
# STATES/FAVORITE and SEARCH/RANDOM, pageup/pagedown=jump. Navigation
# (up/down/left/right), BACK (a), CHOOSE (b) and hotkey are kept, so browsing
# and launching still work and Batocera's config generator still sees a
# hotkey to build emulator configs from.
MENU_INPUTS = ("start", "select", "x", "y", "pageup", "pagedown")

# The help bar also offers "GAME OPTIONS (HOLD)" on the launch button itself,
# which no amount of input stripping can remove without breaking launching.
# ES's own restricted UI mode is what closes that one, so the two are applied
# together. The passkey that unlocks it back to full is a button sequence;
# this one deliberately spells itself with X and Y, which the joysticks can
# no longer send at all -- a keyboard can. The real way back is SSH:
# `kiosk.py --unlock`.
UI_MODE = "Kiosk"
UI_PASSKEY = "xyxyxyxyxy"

# Which systems the menu shows. The cabinet is the four MQT games in public;
# in admin mode SNES joins them so it can double as a console. Everything
# else Batocera ships stays hidden either way -- add a name to ADMIN_SYSTEMS
# to reveal it in admin mode, or drop it from OTHER_SYSTEMS to make it public.
# ES reads this at start-up, and lock/unlock restart ES anyway.
OTHER_SYSTEMS = ("c64", "pcengine", "nes", "snes", "gba", "mrboom", "ports",
                 "prboom", "sdlpop", "odcommander", "megadrive")
ADMIN_SYSTEMS = ("snes",)
LOCKED_HIDDEN_SYSTEMS = ";".join(OTHER_SYSTEMS)
UNLOCKED_HIDDEN_SYSTEMS = ";".join(s for s in OTHER_SYSTEMS if s not in ADMIN_SYSTEMS)

# The attract reels (batocera/attract/) as ES's screensaver: after 15 s without
# input, on the main menu or in the game list alike, ES plays one .mp4 from
# SCREENSAVER_DIR at random, then another, and any button -- even one the
# lockdown unmapped -- brings back the screen you were on without doing
# anything else. Checked against batocera-emulationstation's source
# (SystemScreenSaver.cpp, Window.cpp):
#   - The custom video folder, not the games' <video> tags: "random video"
#     picks from every system's gamelist, *hidden systems included*, and
#     Batocera's bundled freeware ROMs ship videos of their own.
#   - The swap timeout cuts a video off and starts another pick; an hour means
#     a reel always plays to its end. At the end ES picks again, uniformly at
#     random (so the same reel can come twice), after ~0.5 s of black and a
#     fade-in.
#   - ScreenSaverControls (on by default) makes stick-right and Select skip to
#     the next video *without* waking up, which on a cabinet just looks broken.
#   - Trap: ES's menu shows ScreenSaverTime in whole minutes, so 15 s shows as
#     0, and merely opening and closing Screensaver Settings saves that 0 --
#     which switches the screensaver off. Re-run --screensaver after doing so.
#   - Waking never navigates: nothing on that code path touches the views.
#   - StopMusicOnScreenSaver (on by default) shuts the menu music down while
#     the screensaver runs. Off, the song carries on under the reels and after
#     waking. The reels have no audio track, so they never duck it either
#     (VideoVlcComponent only lowers the music for a video with sound).
SCREENSAVER_DIR = "/userdata/screensaver"
SCREENSAVER_SETTINGS = (
    ("int", "ScreenSaverTime", "15000"),
    ("string", "ScreenSaverBehavior", "random video"),
    ("bool", "SlideshowScreenSaverCustomVideoSource", "true"),
    ("string", "SlideshowScreenSaverVideoDir", SCREENSAVER_DIR),
    ("string", "SlideshowScreenSaverVideoFilter", ".mp4"),
    ("bool", "SlideshowScreenSaverVideoRecurse", "false"),
    ("int", "ScreenSaverSwapVideoTimeout", "3600000"),
    ("bool", "ScreenSaverControls", "false"),
    ("bool", "ScreenSaverVideoMute", "true"),
    ("bool", "StopMusicOnScreenSaver", "false"),
    ("string", "ScreenSaverGameInfo", "never"),
)

# Always start on the MQT system's carousel. The default, "lastsystem", is
# whatever ES showed when it last exited -- which, if that was SNES while
# unlocked, is a system the lockdown hides, and ES then starts on a system it
# cannot show. B from the game list still goes back to the carousel; add
# ("bool", "StartupOnGameList", "true") to boot straight into the game list.
MENU_SETTINGS = (
    ("string", "StartupSystem", "pygame"),
)

_CONFIG_OPEN = re.compile(r"<inputConfig\b[^>]*type=\"joystick\"")
_CONFIG_CLOSE = re.compile(r"</inputConfig>")
_MENU_INPUT = re.compile(r"<input\s+name=\"(%s)\"" % "|".join(MENU_INPUTS))


def strip_menu_inputs(text: str) -> tuple[str, int]:
    """Drop the START/SELECT lines from every joystick block, keyboard kept."""
    kept, dropped, in_joystick = [], 0, False
    for line in text.splitlines(keepends=True):
        if _CONFIG_OPEN.search(line):
            in_joystick = True
        elif _CONFIG_CLOSE.search(line):
            in_joystick = False
        if in_joystick and _MENU_INPUT.search(line):
            dropped += 1
            continue
        kept.append(line)
    return "".join(kept), dropped


def es_pids() -> list[int]:
    """PIDs of EmulationStation *and* of the wrapper that respawns it.

    Both have to go, not just ES. /usr/bin/emulationstation-standalone is a
    loop that relaunches ES whenever it exits, and `S31emulationstation stop`
    does not take the boot-time wrapper down -- so stopping ES alone left the
    old wrapper to start a second one, and the cabinet ended up with two
    EmulationStations drawing at once.

    Matching is done on /proc rather than with pgrep: comm is truncated to 15
    characters ("emulationstatio"), so `pgrep -x emulationstation` never
    fires, while `pgrep -f` matches the shell running this script.
    """
    pids = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            comm = (entry / "comm").read_text().strip()
            cmdline = (entry / "cmdline").read_bytes().decode("utf-8", "replace")
        except OSError:  # process exited while we looked
            continue
        if comm.startswith("emulationstatio") or "emulationstation-standalone" in cmdline:
            pids.append(int(entry.name))
    return pids


def es_running() -> bool:
    return bool(es_pids())


def game_running() -> str | None:
    """The ROM of the game ES has running, if any (ES starts every game through
    emulatorlauncher, whatever the system)."""
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            args = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if any(a.endswith(b"emulatorlauncher") for a in args[:2]) and b"-rom" in args[:-1]:
            return args[args.index(b"-rom") + 1].decode("utf-8", "replace")
    return None


def stop_es() -> bool:
    """Stop ES and its wrapper; report whether anything had been running.

    ES rewrites es_settings.cfg from memory when it exits, so it has to be
    down *before* we touch that file or our edit is thrown away on quit.

    Refuses while a game is running: the game outlives ES, and the new ES then
    draws over it, with the game still running unseen and unreachable behind
    it (that happened once, mid-round of Ion Surfer).
    """
    if not es_pids():
        return False
    rom = game_running()
    if rom:
        raise SystemExit(f"a game is running ({rom}): quit it first, then run this again")
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in es_pids():
            try:
                os.kill(pid, sig)
            except OSError:
                pass
        for _ in range(30):  # up to ~3s per signal
            if not es_pids():
                return True
            time.sleep(0.1)
    print("WARNING: EmulationStation did not stop")
    return True


def start_es() -> None:
    """Start EmulationStation under the sway session that is already running.

    NOT `S31emulationstation start`: all that does is `sway-launch &`, which
    is a no-op when sway is already up -- so ES simply never came back and the
    cabinet sat on the wallpaper. S31's *stop* kills sway too, which is why
    the pair looked like it worked. Since stop_es() deliberately leaves sway
    alone (killing it takes the whole UI down), the matching start is the
    wrapper itself. It is a loop that keeps ES alive, so it must be detached
    or this script never returns.
    """
    subprocess.Popen(
        ["/usr/bin/emulationstation-standalone"],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        # Without these, ES started from an SSH session has no Wayland to draw
        # on: SDL reports "No available video device", ES exits, the wrapper
        # relaunches it, and the cabinet sits on the wallpaper crash-looping
        # with nothing obviously wrong in `ps`. At boot ES inherits these from
        # the session; over SSH we have to supply them.
        env={**os.environ, **SWAY_ENV},
    )


def set_setting(kind: str, name: str, value: str) -> None:
    tree = ET.parse(SETTINGS_CFG)
    root = tree.getroot()
    for node in root.findall(kind):
        if node.get("name") == name:
            node.set("value", value)
            break
    else:
        ET.SubElement(root, kind, {"name": name, "value": value})
    tree.write(SETTINGS_CFG, encoding="UTF-8", xml_declaration=True)
    print(f"{name} = {value}")


def get_setting(name: str) -> str:
    if not SETTINGS_CFG.exists():
        return "<no settings file>"
    root = ET.parse(SETTINGS_CFG).getroot()
    for node in root:
        if node.get("name") == name:
            return node.get("value", "?")
    return "<unset>"


def lock() -> None:
    if not INPUT_BACKUP.exists():
        shutil.copy2(INPUT_CFG, INPUT_BACKUP)
        print(f"backed up {INPUT_CFG} -> {INPUT_BACKUP}")
    # Always rebuild from the pristine copy so re-running never compounds.
    text, dropped = strip_menu_inputs(INPUT_BACKUP.read_text(encoding="utf-8"))
    was_running = stop_es()
    INPUT_CFG.write_text(text, encoding="utf-8")
    print(f"removed {dropped} menu-button mappings from {INPUT_CFG}")
    set_setting("bool", "ShowHelpPrompts", "false")
    set_setting("string", "HiddenSystems", LOCKED_HIDDEN_SYSTEMS)
    set_setting("string", "UIMode", UI_MODE)
    set_setting("string", "UIMode_passkey", UI_PASSKEY)
    if was_running:
        start_es()
        print("restarted EmulationStation")


def unlock() -> None:
    if not INPUT_BACKUP.exists():
        print(f"nothing to restore: {INPUT_BACKUP} does not exist")
        return
    was_running = stop_es()
    shutil.copy2(INPUT_BACKUP, INPUT_CFG)
    print(f"restored {INPUT_CFG}")
    set_setting("bool", "ShowHelpPrompts", "true")
    set_setting("string", "HiddenSystems", UNLOCKED_HIDDEN_SYSTEMS)
    set_setting("string", "UIMode", "Full")
    if was_running:
        start_es()
        print("restarted EmulationStation")


def is_locked() -> bool:
    """Locked means there is nothing left to strip from es_input.cfg."""
    _, still_there = strip_menu_inputs(INPUT_CFG.read_text(encoding="utf-8"))
    return still_there == 0


def toggle() -> None:
    """Lock if unlocked, unlock if locked.

    This is what the button sequence on the cabinet calls. It has to be a
    toggle: with an unlock-only action there is no way to get back *into*
    kiosk mode without a laptop, which defeats the point of having a way in
    without one.
    """
    if is_locked():
        print("currently locked -> unlocking")
        unlock()
    else:
        print("currently unlocked -> locking")
        lock()


def controls() -> None:
    """Put EmulationStation's confirm/back on the cabinet's A/B convention.

    Out of the box ES confirms with B and goes back with A, which is the
    opposite of the convention the games follow (see "Button convention" in
    AGENTS.md). ES has a setting for exactly this; it lives in es_settings.cfg,
    so ES has to be down while we write it.
    """
    was_running = stop_es()
    set_setting("bool", "InvertButtons", "true")
    if was_running:
        start_es()
        print("restarted EmulationStation")


def set_screensaver_settings() -> None:
    """Write SCREENSAVER_SETTINGS and MENU_SETTINGS. ES must already be stopped."""
    for kind, name, value in SCREENSAVER_SETTINGS + MENU_SETTINGS:
        set_setting(kind, name, value)


def screensaver() -> None:
    """Play the attract reels after 15 s idle (the videos themselves are
    copied to SCREENSAVER_DIR by install_ui.py)."""
    was_running = stop_es()
    set_screensaver_settings()
    if was_running:
        start_es()
        print("restarted EmulationStation")


def status() -> None:
    live = INPUT_CFG.read_text(encoding="utf-8")
    _, would_drop = strip_menu_inputs(live)
    print(f"joystick menu-button mappings still present: {would_drop}")
    print(f"locked: {would_drop == 0}")
    for name in ("ShowHelpPrompts", "UIMode", "UIMode_passkey", "HiddenSystems"):
        print(f"{name}: {get_setting(name)}")
    for _, name, wanted in SCREENSAVER_SETTINGS + MENU_SETTINGS:
        value = get_setting(name)
        print(f"{name}: {value}{'' if value == wanted else f'   (attract reel wants {wanted})'}")
    print(f"backup present: {INPUT_BACKUP.exists()}")
    print(f"the L R L R X sequence would: {'unlock' if would_drop == 0 else 'lock'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--lock", action="store_true", help="public-facing: no menus from the pads")
    group.add_argument("--unlock", action="store_true", help="restore normal menu access")
    group.add_argument("--status", action="store_true", help="report the current state")
    group.add_argument("--toggle", action="store_true", help="lock if unlocked, unlock if locked")
    group.add_argument("--controls", action="store_true", help="A confirms / B goes back in ES")
    group.add_argument("--screensaver", action="store_true", help="the attract reels after 15 s idle")
    args = parser.parse_args()

    if args.lock:
        lock()
    elif args.unlock:
        unlock()
    elif args.toggle:
        toggle()
    elif args.controls:
        controls()
    elif args.screensaver:
        screensaver()
    else:
        status()


# install_ui.py imports this file for its ES helpers, so only run as a script.
if __name__ == "__main__":
    main()
