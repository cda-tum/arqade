"""Lock the cabinet down so nobody can reach EmulationStation's menus.

Run on the arcade:
    python3 /userdata/kiosk.py --lock      # public-facing
    python3 /userdata/kiosk.py --unlock    # back to normal
    python3 /userdata/kiosk.py --status

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
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

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


def es_running() -> bool:
    """True if EmulationStation is up.

    Not `pgrep -x emulationstation`: Linux truncates a process's comm to 15
    characters, so it is really "emulationstatio" and the exact-match never
    fires. Matching /proc/*/comm by prefix avoids both that and the opposite
    trap of `pgrep -f`, which happily matches the shell running this script.
    """
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if (entry / "comm").read_text().strip().startswith("emulationstatio"):
                return True
        except OSError:  # process exited while we looked
            continue
    return False


def stop_es() -> bool:
    """Stop ES and report whether it had been running.

    ES rewrites es_settings.cfg from memory when it exits, so it has to be
    down *before* we touch that file or our edit is thrown away on quit.
    """
    if not es_running():
        return False
    subprocess.run(["/etc/init.d/S31emulationstation", "stop"], capture_output=True)
    return True


def start_es() -> None:
    # The init script does not return -- it keeps ES in the foreground -- so
    # detach it, or running this over SSH hangs until the cabinet is switched
    # off and killing the SSH session takes ES down with it.
    subprocess.Popen(
        ["/etc/init.d/S31emulationstation", "start"],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
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


def status() -> None:
    live = INPUT_CFG.read_text(encoding="utf-8")
    _, would_drop = strip_menu_inputs(live)
    print(f"joystick menu-button mappings still present: {would_drop}")
    print(f"locked: {would_drop == 0}")
    for name in ("ShowHelpPrompts", "UIMode", "UIMode_passkey"):
        print(f"{name}: {get_setting(name)}")
    print(f"backup present: {INPUT_BACKUP.exists()}")
    print(f"the L R L R X sequence would: {'unlock' if would_drop == 0 else 'lock'}")


parser = argparse.ArgumentParser(description=__doc__)
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("--lock", action="store_true", help="public-facing: no menus from the pads")
group.add_argument("--unlock", action="store_true", help="restore normal menu access")
group.add_argument("--status", action="store_true", help="report the current state")
group.add_argument("--toggle", action="store_true", help="lock if unlocked, unlock if locked")
group.add_argument("--controls", action="store_true", help="A confirms / B goes back in ES")
args = parser.parse_args()

if args.lock:
    lock()
elif args.unlock:
    unlock()
elif args.toggle:
    toggle()
elif args.controls:
    controls()
else:
    status()
