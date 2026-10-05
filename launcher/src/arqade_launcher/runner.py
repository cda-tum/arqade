"""Starting a game: the command line, the input config it gets, and waiting
for it to finish.

Each game runs in a fresh process, as on the cabinet. They all end with
`pygame.quit()` and `sys.exit()`, set SDL options when imported and keep
state in their modules, so running them inside the launcher's own process
would break the menu; a crash in one game would also take the menu down.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import deque
from dataclasses import dataclass

import pygame

from arqade_launcher import child
from arqade_launcher.catalog import Game
from arqade_launcher.settings import ACTIONS, AXES, EXIT_KEY, PLAYERS, RAW_BUTTONS, Settings


@dataclass
class Result:
    code: int
    stderr_tail: list[str]


def key_code(name: str | None) -> int | None:
    if not name:
        return None
    try:
        return pygame.key.key_code(name)
    except ValueError:
        return None


def input_config(settings: Settings) -> dict:
    """What child.py needs: the exit key, plus each pad's bindings when the
    keyboard is to drive virtual pads."""
    pads = []
    if settings.pads:
        for player in PLAYERS:
            bindings = []
            for action in ACTIONS:
                key = key_code(settings.keys[player].get(action))
                if key is None:
                    continue
                if action in RAW_BUTTONS:
                    bindings.append({"key": key, "kind": "button", "index": RAW_BUTTONS[action]})
                else:
                    axis, sign = AXES[action]
                    bindings.append({"key": key, "kind": "axis", "index": axis, "sign": sign})
            pads.append(bindings)
    return {"exit_key": key_code(EXIT_KEY), "pads": pads}


def game_args(settings: Settings, window_size: tuple[int, int]) -> list[str]:
    """The same flags the cabinet's loader passes, adapted to this PC."""
    if settings.fullscreen:
        args = ["--fullscreen"]
    else:
        args = ["--window-size", f"{window_size[0]}x{window_size[1]}"]
    if settings.pads:
        # The keyboard is the pads now; the games' own key bindings would
        # double-fire on top of them (and P1's and P2's overlap).
        args.append("--no-keyboard")
    if settings.show_fps:
        args.append("--fps")
    return args


def command(game: Game, settings: Settings, window_size: tuple[int, int]) -> list[str]:
    return [sys.executable, "-m", child.__name__, str(game.src_dir), game.package,
            *game_args(settings, window_size)]


def run_game(game: Game, settings: Settings, window_size: tuple[int, int]) -> Result:
    """Run a game to completion. Its stderr still reaches the terminal live;
    the last lines are kept so the menu can say why a game crashed."""
    env = dict(os.environ)
    env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    env[child.ENV_VAR] = json.dumps(input_config(settings))
    tail: deque[str] = deque(maxlen=20)
    try:
        proc = subprocess.Popen(command(game, settings, window_size), cwd=game.project_dir,
                                env=env, stderr=subprocess.PIPE, text=True, errors="replace")
    except OSError as exc:
        return Result(code=-1, stderr_tail=[str(exc)])
    assert proc.stderr is not None
    for line in proc.stderr:
        sys.stderr.write(line)
        tail.append(line.rstrip("\n"))
    return Result(code=proc.wait(), stderr_tail=list(tail))
