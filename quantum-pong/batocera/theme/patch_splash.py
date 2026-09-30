"""Swap the Batocera logo on the loading screens of the copied "mqt" theme.

Edits two files in /userdata/themes/mqt:
  _splash.xml     - menu start/reload screen (uses the built-in :/logo.png)
  gamesplash.xml  - screen shown while a game launches
Each file is backed up as <name>.bak once, before its first change.
"""

import shutil
from pathlib import Path

THEME = Path("/userdata/themes/mqt")
SPLASH = "./art/mqt_splash.png"


def patch(name: str, edits: list[tuple[str, str]]) -> None:
    path = THEME / name
    text = path.read_text(encoding="utf-8-sig")
    backup = path.with_name(name + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    for old, new in edits:
        if old in text:
            # Only the first match, so other elements keep their settings
            text = text.replace(old, new, 1)
            print(f"{name}: replaced {old!r}")
        else:
            print(f"{name}: NOT FOUND {old!r} (skipped)")
    path.write_text(text, encoding="utf-8")


# Menu splash: our image instead of the Batocera logo, dark text on white
patch("_splash.xml", [
    ("<path>:/logo.png</path>", f"<path>{SPLASH}</path>"),
    ('<text name="label">\n      <color>FFFFFFFF</color>',
     '<text name="label">\n      <color>333333FF</color>'),
])

# Game launch splash: always show our image, untinted
patch("gamesplash.xml", [
    ('<image name="background">',
     f'<image name="background">\n      <path>{SPLASH}</path>'),
    ("<color>A0A0A0FF</color>", "<color>FFFFFFFF</color>"),
])
