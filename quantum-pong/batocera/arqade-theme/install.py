"""Install the ARQADE artwork into the copied "mqt" Batocera theme.

Run on the arcade after copying this folder to /userdata/arqade-theme:
    python3 /userdata/arqade-theme/install.py
Then reboot (do not restart only the menu over SSH).

Safe to run several times: the splash XML files are always rebuilt from
their original .bak copies, so edits never stack up.
"""

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
THEME = Path("/userdata/themes/mqt")
BOOT_SPLASH_DIR = Path("/userdata/splash")
SPLASH = "./art/mqt_splash.png"


def copy_art() -> None:
    # Mirror art/ from this folder into the theme, overwriting old images
    for src in sorted((HERE / "art").rglob("*")):
        if src.is_file():
            dst = THEME / src.relative_to(HERE)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"copied  {dst}")
    # Boot splash shown right after power-on
    BOOT_SPLASH_DIR.mkdir(parents=True, exist_ok=True)
    # Batocera picks a random file from this folder, so drop the old MQT one
    old = BOOT_SPLASH_DIR / "mqt_splash.png"
    if old.exists():
        old.unlink()
        print(f"removed {old}")
    for src in (HERE / "splash").glob("*"):
        shutil.copy2(src, BOOT_SPLASH_DIR / src.name)
        print(f"copied  {BOOT_SPLASH_DIR / src.name}")


def patch(name: str, edits: list[tuple[str, str]]) -> None:
    path = THEME / name
    backup = path.with_name(name + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    # Always start from the untouched original
    text = backup.read_text(encoding="utf-8-sig")
    for old, new in edits:
        if old in text:
            text = text.replace(old, new, 1)
            print(f"patched {name}: {old!r}")
        else:
            print(f"SKIPPED {name}: {old!r} not found")
    path.write_text(text, encoding="utf-8")


copy_art()

# Menu start/reload screen: our image instead of the built-in Batocera logo
patch("_splash.xml", [
    ("<path>:/logo.png</path>", f"<path>{SPLASH}</path>"),
])

# Game launch screen: always our image, without the grey tint
patch("gamesplash.xml", [
    ('<image name="background">',
     f'<image name="background">\n      <path>{SPLASH}</path>'),
    ("<color>A0A0A0FF</color>", "<color>FFFFFFFF</color>"),
])
