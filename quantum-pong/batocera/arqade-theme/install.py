"""Install the ARQADE artwork into the copied "mqt" Batocera theme.

Run on the arcade after copying this folder to /userdata/arqade-theme:
    python3 /userdata/arqade-theme/install.py
Then reboot (do not restart only the menu over SSH).

Safe to run several times: the splash XML files are always rebuilt from
their original .bak copies, so edits never stack up.

Two things bit us once and are guarded against here -- see the "Splash
screens" section of ../../../AGENTS.md for the full story:

  - Artwork must be 8-bit PNG. The originals here were 16-bit/color PNGs,
    which neither `fbv` (the boot-splash image renderer) nor EmulationStation
    would load, so both silently fell back to Batocera's own logo.
  - /userdata/splash is picked over by /etc/init.d/S28splash, which prefers a
    VIDEO over an image and otherwise falls back to Batocera's built-in
    splash.mp4. The image branch additionally needs /dev/fb0 + fbv, so a
    .mp4 alongside the .png is the reliable option -- that's why
    splash/ ships both.
  - Files are chmod'd readable: shutil.copy2 preserves the source mode, and
    a 600 source would otherwise land as a 600 file on the cabinet.
"""

import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
THEME = Path("/userdata/themes/mqt")
BOOT_SPLASH_DIR = Path("/userdata/splash")
SPLASH = "./art/mqt_splash.png"
FILE_MODE = 0o644

# The compositor's wallpaper. sway sets this in /etc/sway/config as
#   output * bg /usr/share/emulationstation/resources/logo.png fill
# and it's what's actually visible behind EmulationStation's start-up
# progress bar and in the gap while a game launches/exits -- so leaving it
# as Batocera's own logo means the OS branding still flashes up twice even
# once every themed splash is replaced. / is a writable overlay, so we swap
# the file and keep the original beside it.
ES_RESOURCES = Path("/usr/share/emulationstation/resources")
WALLPAPER = ES_RESOURCES / "logo.png"
WALLPAPER_BACKUP = ES_RESOURCES / "logo.png.batocera-orig"
SWAYSOCK = "/var/run/sway-ipc.0.sock"


def _copy(src: Path, dst: Path) -> None:
    shutil.copy2(src, dst)
    dst.chmod(FILE_MODE)
    print(f"copied  {dst}")


def install_wallpaper() -> None:
    source = HERE / "splash" / "arqade_splash.png"
    if not source.exists() or not ES_RESOURCES.is_dir():
        print(f"SKIPPED wallpaper: {source} or {ES_RESOURCES} missing")
        return
    if not WALLPAPER_BACKUP.exists() and WALLPAPER.exists():
        shutil.copy2(WALLPAPER, WALLPAPER_BACKUP)
        print(f"backed up {WALLPAPER} -> {WALLPAPER_BACKUP}")
    _copy(source, WALLPAPER)
    # Apply to the running compositor too, so it doesn't need a reboot.
    if Path(SWAYSOCK).exists():
        rc = subprocess.run(
            ["swaymsg", "output", "*", "bg", str(WALLPAPER), "fill"],
            env={**os.environ, "SWAYSOCK": SWAYSOCK},
            capture_output=True,
        ).returncode
        print(f"swaymsg reload: {'ok' if rc == 0 else f'failed (rc={rc})'}")


def copy_art() -> None:
    # Mirror art/ from this folder into the theme, overwriting old images
    for src in sorted((HERE / "art").rglob("*")):
        if src.is_file():
            dst = THEME / src.relative_to(HERE)
            dst.parent.mkdir(parents=True, exist_ok=True)
            _copy(src, dst)
    # Boot splash shown right after power-on
    BOOT_SPLASH_DIR.mkdir(parents=True, exist_ok=True)
    # Batocera picks a random file from this folder, so drop the old MQT one
    old = BOOT_SPLASH_DIR / "mqt_splash.png"
    if old.exists():
        old.unlink()
        print(f"removed {old}")
    for src in (HERE / "splash").glob("*"):
        _copy(src, BOOT_SPLASH_DIR / src.name)


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
install_wallpaper()

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
