"""Launcher settings: display mode, how games read the keyboard, and the
keyboard -> cabinet pad mapping.

Stored as JSON in the user's config directory. Keys are kept as pygame's own
key names (`pygame.key.name`), so the file stays readable and hand-editable.
A missing, broken or partly filled file never stops the launcher: anything it
can't use falls back to the defaults below.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

PLAYERS = ("p1", "p2")

# In the order the key-mapping screen lists them. The six buttons follow the
# pads' printed 2x3 grid, row-major: L X R / Y B A.
ACTIONS = ("up", "down", "left", "right", "l", "x", "r", "y", "b", "a", "start", "select")
DIRECTIONS = ("up", "down", "left", "right")

LABELS = {
    "up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT",
    "l": "L", "x": "X", "r": "R", "y": "Y", "b": "B", "a": "A",
    "start": "START", "select": "SELECT",
}

# Raw joystick button numbers the cabinet's pads report for each printed
# button (AGENTS.md, "Confirmed raw button numbers"). Every game is written
# against these, so the virtual pads in child.py report exactly the same.
RAW_BUTTONS = {"x": 0, "a": 1, "b": 2, "y": 3, "l": 4, "r": 5, "select": 8, "start": 9}
# Direction -> (axis, sign). The stick is an analog axis on the cabinet, not
# a hat: axis 0 is left/right, axis 1 up/down, negative is left/up.
AXES = {"left": (0, -1), "right": (0, 1), "up": (1, -1), "down": (1, 1)}

# Esc always leaves a running game and is never bound to a pad.
EXIT_KEY = "escape"

# Two players on one keyboard, P1 on the left half and P2 on the right, each
# with a stick and the pad's 2x3 grid. Only keys that sit in the same place on
# QWERTY and QWERTZ (no Y/Z, no punctuation), so the defaults also make sense
# on a German keyboard.
DEFAULT_KEYS = {
    "p1": {
        "up": "w", "down": "s", "left": "a", "right": "d",
        "l": "f", "x": "g", "r": "h",
        "y": "v", "b": "b", "a": "n",
        "start": "1", "select": "2",
    },
    "p2": {
        "up": "up", "down": "down", "left": "left", "right": "right",
        "l": "u", "x": "i", "r": "o",
        "y": "j", "b": "k", "a": "l",
        "start": "return", "select": "right shift",
    },
}


def default_keys() -> dict[str, dict[str, str | None]]:
    return copy.deepcopy(DEFAULT_KEYS)


@dataclass
class Settings:
    fullscreen: bool = True
    # True: the keyboard drives two virtual cabinet pads in every game (and the
    # games' own keyboard controls are switched off). False: each game reads
    # the keyboard its own way, and real joysticks pass straight through.
    pads: bool = True
    show_fps: bool = False
    # The gameplay reel after a while without input on the game menu.
    attract: bool = True
    # player -> action -> pygame key name, or None when unbound.
    keys: dict[str, dict[str, str | None]] = field(default_factory=default_keys)

    def to_json(self) -> dict:
        return {"fullscreen": self.fullscreen, "pads": self.pads,
                "show_fps": self.show_fps, "attract": self.attract, "keys": self.keys}

    @classmethod
    def from_json(cls, raw: object) -> Settings:
        settings = cls()
        if not isinstance(raw, dict):
            return settings
        for name in ("fullscreen", "pads", "show_fps", "attract"):
            if isinstance(raw.get(name), bool):
                setattr(settings, name, raw[name])
        keys = raw.get("keys")
        if isinstance(keys, dict):
            for player in PLAYERS:
                bound = keys.get(player)
                if not isinstance(bound, dict):
                    continue
                for action in ACTIONS:
                    if action in bound and (bound[action] is None or isinstance(bound[action], str)):
                        settings.keys[player][action] = bound[action]
        return settings

    def bind(self, player: str, action: str, key: str | None) -> tuple[str, str] | None:
        """Bind `key` to one player's action. A key does one thing only, so if
        it was bound elsewhere that binding is cleared; returns where from."""
        moved_from = None
        if key is not None:
            for other_player in PLAYERS:
                for other_action, other_key in self.keys[other_player].items():
                    if other_key == key and (other_player, other_action) != (player, action):
                        self.keys[other_player][other_action] = None
                        moved_from = (other_player, other_action)
        self.keys[player][action] = key
        return moved_from


def default_path() -> Path:
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"])
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "arqade" / "settings.json"


def load(path: Path) -> Settings:
    try:
        return Settings.from_json(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return Settings()


def save(settings: Settings, path: Path) -> None:
    """Write atomically, so a crash mid-write can't leave a half file behind."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(settings.to_json(), indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        print(f"arqade: could not save settings to {path}: {exc}", file=sys.stderr)
