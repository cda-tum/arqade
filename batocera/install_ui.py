"""Install the cabinet's front end: the game icons and the attract reel.

deploy_ui.sh copies this folder to /userdata/arqade-ui and runs it there:
    python3 /userdata/arqade-ui/install_ui.py --dry-run   # say what would change
    python3 /userdata/arqade-ui/install_ui.py

It does three things, with EmulationStation stopped for all of them (and
started again afterwards, if it was running):

  - images/*.png -> /userdata/roms/pygame/images/: the per-game logos and
    marquees (batocera/logos/) that the menu shows for each game.
  - gamelist.xml: each game's name, description, image and marquee are
    brought in line with the repo's batocera/gamelist.xml, and games it
    doesn't list yet are added. Everything else in the cabinet's copy is kept
    -- ES writes play counts, last-played and play time there, and games from
    elsewhere stay listed -- and the file as it was is saved beside it as
    gamelist.xml.arqade-bak first.
  - reels/arqade_reel_*.mp4 -> /userdata/screensaver/, and ES's screensaver
    settings set to play them after 15 s idle (kiosk.py --screensaver; see
    the notes there). Reels from an earlier build that this one no longer
    has are removed, or ES would keep picking them.

ES has to be down because it owns both files it would otherwise race: it
rewrites es_settings.cfg from memory when it exits, and the gamelist with it
when play statistics changed. kiosk.py's stop_es()/start_es() do that the way
that is known to work on this cabinet; this uses the copy deployed beside it,
and also installs that copy as /userdata/kiosk.py (which the unlock daemon
and an admin over SSH run).

The loading-screen art (boot video, splash stills) is not here: that is the
theme installer's job, quantum-pong/batocera/arqade-theme/install.py, which
deploy_ui.sh runs too.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROMS = Path("/userdata/roms/pygame")
IMAGES = ROMS / "images"
GAMELIST = ROMS / "gamelist.xml"
GAMELIST_BACKUP = ROMS / "gamelist.xml.arqade-bak"
REEL_PATTERN = "arqade_reel*.mp4"  # also the single arqade_reel.mp4 of the first deploy
KIOSK = Path("/userdata/kiosk.py")
FILE_MODE = 0o644
# What the repo decides for each game; ES's own fields are left alone.
REPO_FIELDS = ("name", "desc", "image", "marquee")

sys.path.insert(0, str(HERE))
import kiosk  # noqa: E402


def copy(src: Path, dst: Path, dry_run: bool) -> None:
    if dst.exists() and dst.read_bytes() == src.read_bytes():
        return
    print(f"{'would copy' if dry_run else 'copied'}  {dst}")
    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        dst.chmod(FILE_MODE)


def merge_gamelist(repo: ET.Element, live: ET.Element) -> list[str]:
    """Update `live` in place from `repo`; return what changed."""
    changes = []
    entries = {(g.findtext("path") or "").strip(): g for g in live.iter("game")}
    for game in repo.iter("game"):
        path = (game.findtext("path") or "").strip()
        target = entries.get(path)
        if target is None:
            added = ET.SubElement(live, "game")
            for tag in ("path", *REPO_FIELDS, "lang"):
                if game.findtext(tag) is not None:
                    ET.SubElement(added, tag).text = game.findtext(tag)
            changes.append(f"added   {path}")
            continue
        for tag in REPO_FIELDS:
            wanted = game.findtext(tag)
            if wanted is None:
                continue
            node = target.find(tag)
            if node is None:
                node = ET.SubElement(target, tag)
            if (node.text or "") != wanted:
                changes.append(f"{tag:<7} {path}: {node.text!r} -> {wanted!r}")
                node.text = wanted
    return changes


def install_icons(dry_run: bool) -> None:
    for src in sorted((HERE / "images").glob("*.png")):
        copy(src, IMAGES / src.name, dry_run)


def install_gamelist(dry_run: bool) -> None:
    repo = ET.parse(HERE / "gamelist.xml").getroot()
    tree = ET.parse(GAMELIST)
    changes = merge_gamelist(repo, tree.getroot())
    for change in changes:
        print(f"gamelist: {change}")
    if not changes:
        print("gamelist: already up to date")
        return
    if dry_run:
        return
    shutil.copy2(GAMELIST, GAMELIST_BACKUP)
    print(f"backed up {GAMELIST} -> {GAMELIST_BACKUP}")
    ET.indent(tree, "\t")
    tree.write(GAMELIST, encoding="utf-8", xml_declaration=True)
    print(f"wrote   {GAMELIST}")


def install_reels(dry_run: bool) -> None:
    folder = Path(kiosk.SCREENSAVER_DIR)
    reels = sorted((HERE / "reels").glob(REEL_PATTERN))
    if not reels:
        print(f"SKIPPED reels: none in {HERE / 'reels'}")
        return
    for src in reels:
        copy(src, folder / src.name, dry_run)
    if not folder.is_dir():
        return
    wanted = {src.name for src in reels}
    for old in sorted(folder.glob(REEL_PATTERN)):
        if old.name not in wanted:
            print(f"{'would remove' if dry_run else 'removed'} {old}")
            if not dry_run:
                old.unlink()
    # ES picks at random from every .mp4 in there, so anything else would
    # play too. Say so rather than deleting someone's file.
    others = [p.name for p in folder.glob("*.mp4") if not p.match(REEL_PATTERN)]
    if others:
        print(f"NOTE: {folder} also holds {', '.join(others)}; the screensaver plays those too")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="only say what would change")
    args = parser.parse_args()

    copy(HERE / "kiosk.py", KIOSK, args.dry_run)
    install_icons(args.dry_run)
    install_reels(args.dry_run)
    if args.dry_run:
        install_gamelist(True)
        for kind, name, value in kiosk.SCREENSAVER_SETTINGS + kiosk.MENU_SETTINGS:
            current = kiosk.get_setting(name)
            if current != value:
                print(f"would set {name}: {current} -> {value}")
        return

    was_running = kiosk.stop_es()
    try:
        install_gamelist(False)
        kiosk.set_screensaver_settings()
    finally:
        if was_running:
            kiosk.start_es()
            print("restarted EmulationStation")


if __name__ == "__main__":
    main()
