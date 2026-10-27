"""Translate pygame keyboard/joystick events into logical per-player actions.

Devices, pad layouts and the two-player keyboard are shared by all games
(arqade_common.input). The four face buttons double as a d-pad (X up, Y
left, B down, A right); A also confirms and B goes back; L and R do the
SANDBOX's extras.

Event driven: each action is held while any of its sources (a key, a
joystick button, an axis, the hat) is down. The pure decision functions
(axis_to_direction, should_quit) and Pad's press/auto-repeat logic are unit
tested; the event plumbing needs real devices and is verified by running it.
"""

from __future__ import annotations

import pygame
from arqade_common.input import (
    KEYBOARD_LAYOUT,
    LastDevice,
    PadLayout,
    PadSlots,
    default_pad_layout,
)

from ion_surfer.config import INPUT_CONFIG

PLAYERS = ("p1", "p2")  # pad 0, pad 1


# Batocera's pygame system runs evmapy, which turns player 1's pad into
# keyboard presses (d-pad -> arrow keys, a/b/x/y -> A/B/X/Y, start -> Enter,
# select -> Space, ...). Those fake keys collide with the dev keyboard layout
# (P1's stick moving P2, one button firing two actions), so the cabinet
# loader passes --no-keyboard and only the joysticks are read.
_keyboard_enabled = True


def set_keyboard_enabled(enabled: bool) -> None:
    global _keyboard_enabled
    _keyboard_enabled = enabled


def keyboard_enabled() -> bool:
    return _keyboard_enabled


class _NoKeys:
    """Stands in for pygame.key.get_pressed() while the keyboard is off."""

    def __getitem__(self, key: int) -> bool:
        return False


def read_keys():
    """pygame.key.get_pressed(), or an all-released stand-in with --no-keyboard."""
    return pygame.key.get_pressed() if _keyboard_enabled else _NoKeys()


def axis_to_direction(axis_value: float, deadzone: float) -> int:
    if axis_value < -deadzone:
        return -1
    if axis_value > deadzone:
        return 1
    return 0


def should_quit(*, p1_start: bool, p1_select: bool, p2_start: bool, p2_select: bool) -> bool:
    """Start + Select held together by one player. There is deliberately no
    quit key: Esc leaves fullscreen in a browser, and the PC launcher handles
    Esc itself (it ends the game process)."""
    return (p1_start and p1_select) or (p2_start and p2_select)


# What each of a player's printed buttons does. In the SANDBOX, blue's L/R
# remove/add an ion, red's L cools while held and R toggles passive cooling;
# Select fires that pad's laser kick there, and is otherwise only half of the
# quit combo. One button can drive several actions; the menu code checks
# confirm/back first and returns, so B never also scrolls down.
BUTTON_ACTIONS = {
    player: {"x": ("up",), "y": ("left",), "b": ("down", "back"), "a": ("right", "confirm"),
             "l": (l_act,), "r": (r_act,), "start": ("start",), "select": ("select",)}
    for player, l_act, r_act in (("p1", "remove_ion", "add_ion"), ("p2", "cool", "passive_cool"))
}
DIRECTIONS = ("up", "down", "left", "right")


def key_codes(names: list[str]) -> list[int]:
    return [getattr(pygame, name) for name in names]


def keymap(player: str) -> dict[int, tuple[str, ...]]:
    """Each of the player's keys in the shared layout -> its actions."""
    layout = KEYBOARD_LAYOUT[player]
    keys = {getattr(pygame, layout[d]): (d,) for d in DIRECTIONS}
    keys.update({getattr(pygame, layout[b]): acts for b, acts in BUTTON_ACTIONS[player].items()})
    return keys


class Pad:
    DIRS = ("left", "right", "up", "down")

    # Every action a pad can carry, derived from the config rather than
    # written out again here. This list used to be a hand-maintained copy of
    # INPUT_CONFIG, and the moment the two disagreed -- a "confirm" action
    # added to the config but not to the list -- the first press of that
    # button raised KeyError and took the whole game down mid-play.
    ACTIONS = tuple(dict.fromkeys(
        [*DIRECTIONS, *(act for m in BUTTON_ACTIONS.values() for acts in m.values() for act in acts)]
    ))

    def __init__(self):
        self.src = {a: set() for a in self.ACTIONS}
        self.pressed = set()
        self.rep = {d: 0.0 for d in self.DIRS}
        self.consumed = set()  # (action, source) used up until released, see consume_buttons

    def consume_buttons(self):
        """Every button or key held right now stops counting until it is
        released, as if it had never been pressed. The stick is left alone
        (it can't dismiss anything, so holding it is meant), and so are
        Start and Select, so the quit combo still works with them held."""
        for act, sources in self.src.items():
            if act in ("start", "select"):
                continue
            for source in [s for s in sources if isinstance(s, tuple)]:
                sources.discard(source)
                self.consumed.add((act, source))
        self.pressed.clear()

    def held(self, act):
        # .get, not [act]: an unknown action is "not held", never a crash.
        return bool(self.src.get(act))

    def set(self, act, source, on):
        if (act, source) in self.consumed:
            if not on:
                self.consumed.discard((act, source))
            return
        was = self.held(act)
        sources = self.src.setdefault(act, set())
        if on:
            sources.add(source)
        else:
            sources.discard(source)
        if on and not was:
            self.pressed.add(act)
            if act in self.rep:
                self.rep[act] = 0.28

    def update(self, dt):
        for d in self.DIRS:
            if self.held(d):
                self.rep[d] -= dt
                if self.rep[d] <= 0:
                    self.pressed.add(d)
                    self.rep[d] = 0.09


class Controls:
    def __init__(self, pad_layout: PadLayout | None = None):
        self.pads = [Pad(), Pad()]
        self.any_button = False  # any joystick button (or, with the keyboard on, key) went down
        # Which joystick is whose: pads join P1 then P2 as they appear (in a
        # browser, only after their first button press).
        self.slots = PadSlots()
        self.pad_layout = pad_layout or default_pad_layout()
        # Keyboard or pad, per player, so on-screen hints name what they're holding.
        self.devices = LastDevice()
        self.keymap = [keymap(p) for p in PLAYERS]
        self.slots.scan()

    @property
    def joys(self):
        """Every connected joystick by device index (for the input test)."""
        return {i: pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())}

    def begin_frame(self):
        for p in self.pads:
            p.pressed.clear()
        self.any_button = False

    def consume_buttons(self):
        for p in self.pads:
            p.consume_buttons()

    def any_pressed(self, act):
        return any(act in p.pressed for p in self.pads)

    def pause_pressed(self):
        """Start on either pad (or either player's Start key) pauses and
        resumes. Select never does: it is reserved for the Start + Select
        quit combo."""
        return self.any_pressed("start")

    def quit_combo(self):
        a, b = self.pads
        return should_quit(
            p1_start=a.held("start"), p1_select=a.held("select"),
            p2_start=b.held("start"), p2_select=b.held("select"),
        )

    def _joy_pad(self, e):
        slot = self.slots.slot_of(e.instance_id)
        return None if slot is None else self.pads[slot]

    def handle(self, e):
        self.slots.handle_event(e)
        self.devices.handle_event(e, self.slots, keyboard=_keyboard_enabled)
        layout = self.pad_layout
        if e.type in (pygame.KEYDOWN, pygame.KEYUP):
            if not _keyboard_enabled:
                return
            on = e.type == pygame.KEYDOWN
            self.any_button |= on
            for pi, m in enumerate(self.keymap):
                for act in m.get(e.key, ()):
                    self.pads[pi].set(act, ("k", e.key), on)
        elif e.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
            # any button at all, mapped or not, on any pad: the HOW TO PLAY
            # card is dismissed with it
            self.any_button |= e.type == pygame.JOYBUTTONDOWN
            pad = self._joy_pad(e)
            if pad is None:
                return
            on = e.type == pygame.JOYBUTTONDOWN
            player = PLAYERS[self.pads.index(pad)]
            for name, raw in (*layout.buttons.items(), *layout.dpad_buttons.items()):
                if e.button == raw:
                    for act in BUTTON_ACTIONS[player].get(name, (name,)):
                        pad.set(act, ("jb", e.button), on)
        elif e.type == pygame.JOYAXISMOTION:
            pad = self._joy_pad(e)
            if pad is None:
                return
            ax_x, ax_y = layout.stick_axes
            d = axis_to_direction(e.value, INPUT_CONFIG["axis_deadzone"])
            if e.axis == ax_x:
                pad.set("left", "jax", d < 0)
                pad.set("right", "jax", d > 0)
            elif e.axis == ax_y:
                pad.set("up", "jay", d < 0)
                pad.set("down", "jay", d > 0)
        elif e.type == pygame.JOYHATMOTION:
            pad = self._joy_pad(e)
            # the layout's d-pad hat, or else hat 0, for pads that have one
            if pad is None or e.hat != (layout.dpad_hat or 0):
                return
            hx, hy = e.value
            pad.set("left", "hat", hx < 0)
            pad.set("right", "hat", hx > 0)
            pad.set("up", "hat", hy > 0)
            pad.set("down", "hat", hy < 0)

    def update(self, dt):
        for p in self.pads:
            p.update(dt)
