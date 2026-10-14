"""A hidden mode that adds the games not ready for visitors to the game list.

It is for testing a new game on the cabinet itself. Nothing on screen names
it: the extra games simply appear in the list, and leave it again.

A game that isn't public yet parks its .pygame loader at
/userdata/games/<rom>/<rom>.pygame instead of in the ROMs folder (see
qircuit/deploy_batocera.sh), so EmulationStation never finds it. Turning the
mode on links every parked loader into /userdata/roms/pygame/ and tells the
running ES about it; turning it off removes the links again. ES updates the
game list in place, with no restart.

    python3 /userdata/experimental.py --toggle   # what the pad combo runs
    python3 /userdata/experimental.py --on | --off | --status
    python3 /userdata/experimental.py --reset    # what the daemon runs at boot
    python3 /userdata/experimental.py --install  # the two ES hooks below

On the cabinet, holding Start + Select on *both* pads at once toggles it
(unlock_daemon.py watches for that). It always falls back to the standard
list on its own:

  - The cabinet going idle (the attract reels) ends it: --install writes a
    `screensaver-start` ES event hook that runs --off, so whoever wakes it
    finds the public list.
  - A reboot or an ES restart never comes back up in it, in three layers:
      - kiosk.py drops the links before it starts ES again (lock, unlock,
        install_ui.py), so that ES never sees them.
      - The unlock daemon runs --reset when it starts, at every boot, a few
        seconds after ES: it waits until ES answers, then takes the parked
        games out of its list, whatever state it came up in.
      - A `start` ES event hook drops the links as ES starts (a crash, a
        restart by hand). On Linux ES does not wait for event scripts
        (only for `quit`; Scripting.cpp), so it races the ROM scan: it
        usually wins, and --reset covers it when it doesn't.

How it talks to ES: the local HTTP API on 127.0.0.1:1234, which ES always
serves (batocera-emulationstation's HttpServerThread.cpp, since v30).
  - POST /addgames/pygame with a partial gamelist adds the games to the
    running list, under the names given. ES also writes those entries into
    gamelist.xml; while the file is missing, the next scan ignores and keeps
    them.
  - POST /removegames/pygame takes them out of the list and unlinks their
    files, which here are only the links. The parked loaders stay.
  Neither reloads every gamelist, so there is no "Loading..." splash and the
  cursor stays where it was. GET /reloadgames is the fallback.
"""

import argparse
import os
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROMS = Path("/userdata/roms/pygame")
PARKED = Path("/userdata/games")
SYSTEM = "pygame"
ES_API = "http://127.0.0.1:1234"  # 127.0.0.1, not localhost: ES only allows that address
RESET_WAIT = 180.0  # seconds --reset waits for ES to answer (a cold boot scans every system)
INSTALLED = Path("/userdata/experimental.py")  # where install_ui.py puts this file

ES_SCRIPTS = Path("/userdata/system/configs/emulationstation/scripts")
HOOK_NAME = "arqade-experimental.sh"
HOOKS = {
    "start": f"""#!/bin/sh
# ES is starting: drop the links that {INSTALLED.name} made, so the
# public list is what comes up. ES doesn't wait for this (it only waits for
# `quit` scripts), so it races the ROM scan; the unlock daemon's --reset at
# boot catches the times it loses.
for link in {ROMS}/*.pygame; do
    case "$(readlink "$link")" in
        {PARKED}/*) rm -f "$link" ;;
    esac
done
""",
    "screensaver-start": f"""#!/bin/sh
# The cabinet went idle: back to the public list (see {INSTALLED.name}).
exec python3 {INSTALLED} --off
""",
}


def parked() -> list[Path]:
    """Every parked loader, /userdata/games/<rom>/<rom>.pygame."""
    return sorted(p for p in PARKED.glob("*/*.pygame") if p.stem == p.parent.name)


def active() -> list[Path]:
    """The links into the ROMs folder that this mode made."""
    return sorted(
        link for link in ROMS.glob("*.pygame")
        if link.is_symlink() and os.readlink(link).startswith(f"{PARKED}/")
    )


def drop_links() -> list[Path]:
    """Remove the links without telling ES: for when ES is down (kiosk.py
    calls this before it starts ES again)."""
    links = active()
    for link in links:
        link.unlink()
    return links


def display_name(rom: str) -> str:
    return rom.replace("_", " ").title()


def gamelist(links: list[Path]) -> bytes:
    root = ET.Element("gameList")
    for link in links:
        game = ET.SubElement(root, "game")
        ET.SubElement(game, "path").text = f"./{link.name}"
        ET.SubElement(game, "name").text = display_name(link.stem)
    return ET.tostring(root, encoding="utf-8")


def es_call(path: str, body: bytes | None = None) -> int | None:
    """HTTP status of an ES API call, or None when ES didn't answer."""
    request = urllib.request.Request(ES_API + path, data=body)
    if body is not None:
        request.add_header("Content-Type", "application/xml")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except OSError:
        return None


def turn_on() -> None:
    added = []
    for loader in parked():
        link = ROMS / loader.name
        if link.is_symlink() or link.exists():
            continue  # already on, or that game is public by now
        link.symlink_to(loader)
        added.append(link)
    if not added:
        print("nothing to add" if not active() else "already on")
        return
    names = ", ".join(link.stem for link in added)
    status = es_call(f"/addgames/{SYSTEM}", gamelist(added))
    if status == 200:
        print(f"on: {names}")
    elif es_call("/reloadgames") is not None:
        print(f"on: {names} (addgames answered {status}, reloaded every gamelist instead)")
    else:
        # The start hook would drop the links anyway when ES comes up.
        for link in added:
            link.unlink()
        print("EmulationStation isn't answering on port 1234: nothing changed")


def turn_off() -> None:
    links = active()
    if not links:
        print("already off")
        return
    status = es_call(f"/removegames/{SYSTEM}", gamelist(links))
    for link in links:  # removegames unlinks them itself; this is for when it couldn't
        if link.is_symlink():
            link.unlink()
    # 204: ES didn't have them listed, so there is nothing to refresh.
    if status not in (200, 204):
        es_call("/reloadgames")
    print(f"off: {', '.join(link.stem for link in links)} (removegames answered {status})")


def reset(wait: float = RESET_WAIT) -> None:
    """Back to the public list, whatever state ES came up in.

    At boot ES may have scanned the links before the `start` hook removed
    them, and then lists games whose files are gone. So this waits until ES
    answers, drops any links, and asks ES to remove every parked game that
    isn't public. removegames also deletes the file at each path, so a path
    with a real file there (a game made public since) is never sent.
    """
    deadline = time.monotonic() + wait
    while es_call("/caps") is None:
        if time.monotonic() > deadline:
            drop_links()
            print(f"EmulationStation didn't answer within {wait:.0f} s: links dropped, list untouched")
            return
        time.sleep(2)
    drop_links()
    paths = [ROMS / loader.name for loader in parked() if not (ROMS / loader.name).exists()]
    if not paths:
        print("reset: nothing parked")
        return
    status = es_call(f"/removegames/{SYSTEM}", gamelist(paths))
    # 204: none of them was listed, which is the usual case.
    print(f"reset: {', '.join(p.stem for p in paths)} (removegames answered {status})")


def toggle() -> None:
    if active():
        turn_off()
    else:
        turn_on()


def install(dry_run: bool = False) -> None:
    """Write the ES event hooks (see the module docstring)."""
    for event, script in HOOKS.items():
        hook = ES_SCRIPTS / event / HOOK_NAME
        if hook.exists() and hook.read_text() == script:
            continue
        print(f"{'would write' if dry_run else 'wrote'} {hook}")
        if not dry_run:
            hook.parent.mkdir(parents=True, exist_ok=True)
            hook.write_text(script)
            hook.chmod(0o755)


def status() -> None:
    links = active()
    print(f"on: {bool(links)}")
    for loader in parked():
        link = ROMS / loader.name
        state = "listed" if link in links else "public" if link.exists() else "hidden"
        print(f"  {loader.parent.name}: {state}")
    for event in HOOKS:
        hook = ES_SCRIPTS / event / HOOK_NAME
        print(f"{event} hook: {'present' if hook.exists() else 'MISSING'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--on", action="store_true", help="list the parked games")
    group.add_argument("--off", action="store_true", help="back to the public list")
    group.add_argument("--toggle", action="store_true", help="on if off, off if on")
    group.add_argument("--reset", action="store_true",
                       help="wait for ES, then make sure the parked games are out of its list")
    group.add_argument("--status", action="store_true", help="report the current state")
    group.add_argument("--install", action="store_true", help="write the ES event hooks")
    args = parser.parse_args()

    if args.on:
        turn_on()
    elif args.off:
        turn_off()
    elif args.toggle:
        toggle()
    elif args.reset:
        reset()
    elif args.install:
        install()
    else:
        status()


# install_ui.py imports this file for install(), so only run as a script.
if __name__ == "__main__":
    main()
