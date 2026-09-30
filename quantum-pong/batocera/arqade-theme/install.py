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

# ...and / does not survive a reboot. It's an overlay whose upper layer is a
# tmpfs (`mount | grep overlay`), so the wallpaper above is RAM-only and the
# Batocera logo comes back on every boot. /boot is a real partition, and
# /etc/init.d/S00bootcustom runs /boot/boot-custom.sh before sway and
# EmulationStation start, so re-apply it from /userdata (also persistent)
# there. Batocera's own batocera-save-overlay would work too, but it carves a
# 100 MB image out of /boot to snapshot all of /, which is a lot of machinery
# for one file.
BOOT_CUSTOM = Path("/boot/boot-custom.sh")
WALLPAPER_SOURCE = BOOT_SPLASH_DIR / "arqade_splash.png"
BOOT_MARKER = "# arqade-wallpaper"
BOOT_SCRIPT = f"""#!/bin/sh
{BOOT_MARKER}: / is a tmpfs overlay, so /usr edits are lost on reboot. Put
# the ARQADE logo back before sway reads it as its wallpaper -- it is what
# shows behind EmulationStation's loading bar and in the gap while a game
# launches and exits.
if [ "$1" = "start" ] && [ -f "{WALLPAPER_SOURCE}" ]; then
    cp "{WALLPAPER_SOURCE}" "{WALLPAPER}"
fi
"""


def _copy(src: Path, dst: Path) -> None:
    shutil.copy2(src, dst)
    dst.chmod(FILE_MODE)
    print(f"copied  {dst}")


def install_wallpaper() -> None:
    source = HERE / "splash" / "arqade_splash.png"
    if not source.exists() or not ES_RESOURCES.is_dir():
        print(f"SKIPPED wallpaper: {source} or {ES_RESOURCES} missing")
        return
    # Keep Batocera's own logo beside ours. The backup lives under /usr and so
    # disappears on reboot -- but by then the boot hook has already put our
    # image in place, so re-making it would just back up our own file. Compare
    # the bytes and only save a genuinely different original.
    if (
        not WALLPAPER_BACKUP.exists()
        and WALLPAPER.exists()
        and WALLPAPER.read_bytes() != source.read_bytes()
    ):
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


def install_boot_hook() -> None:
    """Re-apply the wallpaper on every boot, from the persistent /boot partition."""
    if BOOT_CUSTOM.exists() and BOOT_MARKER not in BOOT_CUSTOM.read_text():
        print(f"SKIPPED {BOOT_CUSTOM}: already exists and isn't ours -- merge by hand")
        return
    # /boot is mounted read-only; S00bootcustom runs the file through bash
    # explicitly, so it needs no execute bit (it's vfat and has none anyway).
    if subprocess.run(["mount", "-o", "remount,rw", "/boot"], capture_output=True).returncode:
        print(f"SKIPPED {BOOT_CUSTOM}: could not remount /boot read-write")
        return
    try:
        BOOT_CUSTOM.write_text(BOOT_SCRIPT)
        print(f"wrote   {BOOT_CUSTOM}")
    finally:
        subprocess.run(["mount", "-o", "remount,ro", "/boot"], capture_output=True)


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
    # name may be nested ("views/system.xml"), so build the .bak from the
    # file name only -- with_name(name + ".bak") would reject the slash.
    backup = path.with_name(path.name + ".bak")
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
install_boot_hook()

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


def hint(name: str, label: str, y: float) -> str:
    """One bottom-right control-hint line for the system (main) menu."""
    return f"""<text name="{name}" extra="true">
      <text>{label}</text>
      <pos>0.97 {y}</pos>
      <size>0.6 0.05</size>
      <origin>1 0</origin>
      <alignment>right</alignment>
      <fontPath>./../art/fonts/Cabin-Regular.ttf</fontPath>
      <fontSize>0.03</fontSize>
      <color>C8C8C8</color>
      <zIndex>60</zIndex>
    </text>
    """


# Main menu (the system carousel):
#  - Blank the three metadata labels in the top left. They come from
#    es_systems_mqt.cfg ("TUM Chair for Design Automation" / "MQT" / "2026");
#    emptying the theme's bindings is safer than editing that cfg, which is
#    what took the menu to a black screen once before.
#  - Add control hints bottom right. These are theme text, NOT baked into
#    art/bg.png: the theme draws that image through <color>${backgroundColor}</color>
#    (200000, near-black), so any text painted into the file itself would be
#    tinted to invisibility.
patch("views/system.xml", [
    ("<text>${system.sortedBy}</text>", "<text></text>"),
    ("<text>${system.fullName}</text>", "<text></text>"),
    ("<text>${system.releaseYearOrNull}</text>", "<text></text>"),
    ('<image name="BottomBar" extra="static">',
     hint("arqadeHintSelect", "Press B button to select games", 0.83)
     + hint("arqadeHintBack", "Press A button to return", 0.875)
     + '<image name="BottomBar" extra="static">'),
])
