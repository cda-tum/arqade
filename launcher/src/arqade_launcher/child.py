"""Runs one game in its own process, the way Batocera's loader does:

    python -m arqade_launcher.child <game src dir> <package> [game args...]

Before the game is imported, this installs two things into pygame:

- **Virtual cabinet pads.** The keyboard drives two fake joysticks that report
  exactly what the cabinet's pads report: buttons on their raw numbers
  (settings.RAW_BUTTONS) and the stick as analog axes 0/1. Every game already
  reads those, so one key mapping works the same in all of them, with no game
  changes. Real joysticks are hidden while this is on, so they can't collide
  with the fake ones.
- **The exit key.** Esc ends the game from anywhere, so every game has the
  same way back to the menu, whatever its own controls.
- **The idle exit** (batocera/arqade_idle.py, the cabinet's own): a game
  nobody touches for 20 s ends too, and the menu's attract reels follow.

Both come from the JSON in the ARQADE_INPUT environment variable (written by
runner.py). Polling games (`Joystick(i).get_button(n)`) and event-driven ones
(JOYBUTTONDOWN, JOYAXISMOTION, JOYDEVICEADDED -- Ion Surfer) both work.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
from pathlib import Path

ENV_VAR = "ARQADE_INPUT"
IDLE_MODULE = Path(__file__).resolve().parents[3] / "batocera" / "arqade_idle.py"


class VirtualPad:
    """Stands in for pygame.joystick.Joystick, driven by held keyboard keys."""

    def __init__(self, index: int, buttons: dict[int, list[int]],
                 axes: dict[int, list[tuple[int, int]]], held: set[int]):
        self.index = index
        self.buttons = buttons  # raw button -> keys
        self.axes = axes  # axis -> [(key, sign)]
        self.held = held  # shared with the event filter

    def init(self) -> None:
        pass

    def quit(self) -> None:
        pass

    def get_init(self) -> bool:
        return True

    def get_id(self) -> int:
        return self.index

    def get_instance_id(self) -> int:
        return self.index

    def get_guid(self) -> str:
        return f"arqade-keyboard-pad-{self.index}"

    def get_name(self) -> str:
        return f"ARQADE keyboard pad P{self.index + 1}"

    def get_power_level(self) -> str:
        return "wired"

    def get_numaxes(self) -> int:
        return 2

    def get_numbuttons(self) -> int:
        return 12

    def get_numhats(self) -> int:
        return 0  # like the cabinet

    def get_numballs(self) -> int:
        return 0

    def get_button(self, button: int) -> bool:
        return any(key in self.held for key in self.buttons.get(button, ()))

    def get_axis(self, axis: int) -> float:
        value = sum(sign for key, sign in self.axes.get(axis, ()) if key in self.held)
        return float(max(-1, min(1, value)))

    def get_hat(self, hat: int):
        import pygame
        raise pygame.error("Invalid joystick hat")

    def get_ball(self, ball: int):
        import pygame
        raise pygame.error("Invalid joystick trackball")

    def rumble(self, low: float, high: float, duration: int) -> bool:
        return False

    def stop_rumble(self) -> None:
        pass


def install(config: dict):
    """Patch pygame for the game about to be imported. Returns a function that
    undoes it (for tests)."""
    import pygame

    exit_key = config.get("exit_key")
    held: set[int] = set()
    pads: list[VirtualPad] = []
    key_actions: dict[int, list[tuple[VirtualPad, str, int]]] = {}
    for index, bindings in enumerate(config.get("pads") or []):
        buttons: dict[int, list[int]] = {}
        axes: dict[int, list[tuple[int, int]]] = {}
        pad = VirtualPad(index, buttons, axes, held)
        for binding in bindings:
            key, kind, number = binding["key"], binding["kind"], binding["index"]
            if kind == "button":
                buttons.setdefault(number, []).append(key)
            else:
                axes.setdefault(number, []).append((key, binding["sign"]))
            key_actions.setdefault(key, []).append((pad, kind, number))
        pads.append(pad)

    joystick_events = {
        pygame.JOYAXISMOTION, pygame.JOYBALLMOTION, pygame.JOYHATMOTION,
        pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYDEVICEADDED,
        pygame.JOYDEVICEREMOVED, pygame.CONTROLLERAXISMOTION,
        pygame.CONTROLLERBUTTONDOWN, pygame.CONTROLLERBUTTONUP,
        pygame.CONTROLLERDEVICEADDED, pygame.CONTROLLERDEVICEREMOVED,
        pygame.CONTROLLERDEVICEREMAPPED,
    }
    original = {
        "get": pygame.event.get,
        "get_count": pygame.joystick.get_count,
        "Joystick": pygame.joystick.Joystick,
    }
    announced = False

    def read(pad: VirtualPad, kind: str, number: int):
        return pad.get_button(number) if kind == "button" else pad.get_axis(number)

    def translate(event, out: list) -> None:
        """Turn one key event into the joystick events it causes. Only real
        changes are sent, so key repeat or a second key on the same button
        doesn't fire it again."""
        affected = key_actions.get(event.key, ())
        before = [read(*action) for action in affected]
        (held.add if event.type == pygame.KEYDOWN else held.discard)(event.key)
        for (pad, kind, number), was in zip(affected, before):
            now = read(pad, kind, number)
            if now == was:
                continue
            if kind == "button":
                out.append(pygame.event.Event(
                    pygame.JOYBUTTONDOWN if now else pygame.JOYBUTTONUP,
                    joy=pad.index, instance_id=pad.index, button=number))
            else:
                out.append(pygame.event.Event(
                    pygame.JOYAXISMOTION, joy=pad.index, instance_id=pad.index,
                    axis=number, value=now))

    def get(*args, **kwargs):
        nonlocal announced
        events = original["get"](*args, **kwargs)
        out = []
        if pads and not announced and pygame.joystick.get_init():
            # SDL announces each joystick once, right after joystick.init().
            announced = True
            out += [pygame.event.Event(pygame.JOYDEVICEADDED, device_index=pad.index,
                                       guid=pad.get_guid()) for pad in pads]
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == exit_key:
                raise SystemExit(0)
            if pads and event.type in joystick_events:
                continue  # a real joystick: hidden behind the virtual pads
            out.append(event)
            if pads and event.type in (pygame.KEYDOWN, pygame.KEYUP):
                translate(event, out)
        return out

    def get_count() -> int:
        return len(pads)

    def joystick(index: int) -> VirtualPad:
        if not 0 <= index < len(pads):
            raise pygame.error("Invalid joystick device number")
        return pads[index]

    pygame.event.get = get
    if pads:
        pygame.joystick.get_count = get_count
        pygame.joystick.Joystick = joystick

    def restore() -> None:
        pygame.event.get = original["get"]
        pygame.joystick.get_count = original["get_count"]
        pygame.joystick.Joystick = original["Joystick"]

    return restore


def load_idle():
    """batocera/arqade_idle.py, the module the cabinet's loaders install too.
    Loaded by path: putting batocera/ on sys.path would hand the game every
    other script in there as well."""
    spec = importlib.util.spec_from_file_location("arqade_idle", IDLE_MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    src_dir, package, game_args = argv[0], argv[1], argv[2:]
    sys.path.insert(0, src_dir)
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    config = json.loads(os.environ.get(ENV_VAR) or "{}")
    if config:
        install(config)
    load_idle().install()
    importlib.import_module(f"{package}.main").main(game_args)


if __name__ == "__main__":
    main()
