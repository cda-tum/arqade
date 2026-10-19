"""Idle exit: a game nobody has touched for 20 seconds closes itself.

On the cabinet that drops back to EmulationStation's game list, which plays
the attract reels as its screensaver 15 s later. In the PC launcher it drops
back to the launcher's menu, which does the same. A game left running
mid-round, or sitting on its title screen, never keeps the cabinet from its
attract mode.

It works from outside the games, so none of them carries any code for it:
install() wraps pygame.event.get, which every game reads its input through
(see "Local PC launcher" in ../AGENTS.md), and the game exits the way the
launcher's Esc does, with SystemExit from inside that call. Each game's
Batocera loader (deploy_batocera.sh copies this file beside the package) and
the launcher's child.py install it. Running a game on its own, or capturing
attract footage (attract/capture.py), doesn't.

Input is a joystick button pressed or released, a stick crossing half
deflection (so a drifting analog pad doesn't count), a hat, a key or a mouse
button. The clock only runs while the game calls event.get: a longer gap
between two calls (loading) counts as MAX_STEP.

A joystick button, stick or hat held down counts as input for as long as it
is held, up to HOLD_LIMIT. "Held" must never get stuck, or the game never
exits. That happened on the cabinet (2026-10-19): Batocera's evmapy turns
P1's stick into arrow and keypad keys, and when the stick jumps from one side
straight to the other between two reads it presses the new key without
releasing the old one, so the game saw a KEYDOWN with no KEYUP. Hence:

- Keys only count when they go down or up, never as held. On the cabinet
  every key is evmapy's echo of P1's pad, whose own joystick events count;
  in the launcher every bound key drives a virtual pad.
- What the events say is held is checked against the joystick itself on
  every call (LivePads), so a release the game threw away (event.clear, a
  filtered event.get, a pad re-opened) still lets go.
- Nothing counts as held for longer than HOLD_LIMIT after it went down: a
  jammed button or an axis that rests at full deflection (a trigger) still
  closes the game, HOLD_LIMIT + TIMEOUT after it went down.
"""

from __future__ import annotations

import time

import pygame

TIMEOUT = 20.0  # seconds without input before the game exits
AXIS_THRESHOLD = 0.5  # stick deflection that counts as pushed
MAX_STEP = 0.25  # the most one gap between event.get calls adds
HOLD_LIMIT = 40.0  # the longest one held button/stick/hat keeps the game alive


def zone(value: float) -> int:
    """-1, 0 or 1: which side of AXIS_THRESHOLD a stick is on."""
    return 0 if abs(value) < AXIS_THRESHOLD else (1 if value > 0 else -1)


class LivePads:
    """Reads a held button, stick or hat off the joystick itself.

    Called with a held key ("button"/"axis"/"hat", instance id, number), it
    returns the input's live non-neutral state, or None once it is let go,
    the pad is gone or can't be read. Pads are looked up through
    pygame.joystick.Joystick(i) at call time, so the launcher's virtual pads
    (child.py, instance id == index) are read the same way as real ones."""

    def __init__(self):
        self.pads: dict[int, object] = {}  # instance id -> Joystick

    def __call__(self, key: tuple):
        kind, instance_id, number = key
        try:
            pad = self._pad(instance_id)
            if pad is None:
                return None
            if kind == "button":
                return True if pad.get_button(number) else None
            if kind == "axis":
                return zone(pad.get_axis(number)) or None
            hat = tuple(pad.get_hat(number))
            return hat if hat != (0, 0) else None
        except (pygame.error, IndexError, ValueError, AttributeError):
            self.pads.pop(instance_id, None)  # quit or re-opened: look again next time
            return None

    def _pad(self, instance_id):
        if not pygame.joystick.get_init():
            return None
        if instance_id not in self.pads:
            for i in range(pygame.joystick.get_count()):
                pad = pygame.joystick.Joystick(i)
                self.pads[pad.get_instance_id()] = pad
        return self.pads.get(instance_id)


class IdleWatch:
    """Counts the seconds since the last input, from the events a game reads.

    `live`, if given, is asked about everything held on every call (see
    LivePads); held entries it no longer reports are dropped."""

    def __init__(self, timeout: float = TIMEOUT, clock=None, live=None):
        self.timeout = timeout
        self.clock = clock or time.monotonic
        self.live = live
        self.idle = 0.0
        self.played = 0.0  # seconds counted so far, the hold clock
        self.last: float | None = None
        # button/stick/hat -> (its non-neutral state, `played` when it went there)
        self.held: dict[tuple, tuple[object, float]] = {}

    def see(self, events) -> bool:
        """Take one batch of events; True once the game has been idle for `timeout`."""
        now = self.clock()
        if self.last is not None:
            step = min(max(now - self.last, 0.0), MAX_STEP)
            self.idle += step
            self.played += step
        self.last = now
        for event in events:
            if self._is_input(event):
                self.idle = 0.0
        if self.held and self.live is not None:
            self._confirm()
        if any(self.played - since < HOLD_LIMIT for _, since in self.held.values()):
            self.idle = 0.0
        return self.idle >= self.timeout

    def _confirm(self) -> None:
        for key, (state, since) in list(self.held.items()):
            now = self.live(key)
            if not now:
                del self.held[key]
            elif now != state:  # moved over without us seeing the event
                self.held[key] = (now, self.played)

    def _is_input(self, event) -> bool:
        kind = event.type
        if kind in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
            self._hold(("button", event.instance_id, event.button), kind == pygame.JOYBUTTONDOWN)
            return True
        if kind == pygame.JOYAXISMOTION:
            key = ("axis", event.instance_id, event.axis)
            side = zone(event.value)
            if self.held.get(key, (0,))[0] == side:
                return False
            self._hold(key, side)
            return True
        if kind == pygame.JOYHATMOTION:
            value = tuple(event.value)
            self._hold(("hat", event.instance_id, event.hat), value if value != (0, 0) else None)
            return True
        if kind == pygame.JOYDEVICEREMOVED:
            self.held = {k: v for k, v in self.held.items() if k[1] != event.instance_id}
            return False
        # Keys and mouse buttons: going down or up is input, holding isn't.
        return kind in (pygame.KEYDOWN, pygame.KEYUP, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP)

    def _hold(self, key: tuple, state) -> None:
        if state:
            self.held[key] = (state, self.played)
        else:
            self.held.pop(key, None)


def install(timeout: float = TIMEOUT):
    """Make the game exit after `timeout` seconds without input. Returns a
    function that undoes it (for tests)."""
    watch = IdleWatch(timeout, live=LivePads())
    original = pygame.event.get

    def get(*args, **kwargs):
        events = original(*args, **kwargs)
        if watch.see(events):
            raise SystemExit(0)
        return events

    pygame.event.get = get

    def restore() -> None:
        pygame.event.get = original

    return restore
