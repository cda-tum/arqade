"""The HOW TO PLAY card, shown once the racers are chosen and before the
countdown, every time a match is started from the title (not on a rematch).

Pure (no pygame, no GL), so it is tested: the words on the card, and its
demo, a scripted little race that loops. Two racers on the chosen track,
on a stretch with no kicker: the person's own racer (P1, on its ring)
tucks in behind a bot on the same wire, builds a slipstream, pulls out onto
the next wire, passes and takes the lead, and its seconds in front start to
count. It is the game's own Race and Pack (leader, lead time, camera)
driven by fixed controls, drawn by the renderer in a box on the card
(hud.tutorial_box) through a narrower camera than the race's.

Any button dismisses the card (match.py), but only after LOCK seconds, so
the press that started the match does not skip it unseen. The stick does
not.
"""

from __future__ import annotations

import dataclasses
import math
import random

from qarrera import config
from qarrera.camera import Director
from qarrera.race import Controls, Cue, Race
from qarrera.track import Track

LOCK = 0.3  # seconds before a button press dismisses the card
LOOP = 5.0  # seconds of the demo before it starts over
VIEW = 260.0  # world units across the demo's box (the race's camera shows CAM_VIEW)
ASPECT = 16 / 9  # the demo's box
PLAYERS = ("p1", "cpu1")
WIRES = ((1, 0), (2, 3), (1, 2), (2, 1))  # both start on the first, P1 pulls out onto the second
START_GAP = 50.0  # the bot starts this far ahead
PULL_AT = 1.6  # P1 pulls out after this long in the slipstream ...
PULL_GAP = 20.0  # ... or once it is this close
SPEED = {"p1": 128.0, "cpu1": 120.0}  # top speeds: P1 is a little quicker
STRETCH = 800.0  # how much track the demo covers, at most
PASS_ROOM = 450.0  # the pass happens on this first part of it: straight, best
CAPTIONS = {
    "draft": "TUCK IN BEHIND: SLIPSTREAM",
    "pass": "CHANGE WIRE AND PASS",
    "lead": "LEAD: YOUR SECONDS COUNT",
}

# The controls, next to a drawing of the stick and of the buttons. Speed is
# a cruise control (race.py): up and down set it, and it holds.
STICK_LINES = ("UP: FASTER", "DOWN: SLOWER", "LET GO: KEEPS ITS SPEED", "LEFT/RIGHT: CHANGE WIRE")
BUTTON_LINES = ("X: FASTER   B: SLOWER", "Y / A: WIRE LEFT / RIGHT")

_starts: dict[str, tuple[float, int, int]] = {}


def goal_lines(target: int) -> tuple[str, ...]:
    return ("BE IN FRONT: EVERY SECOND IN THE",
            f"LEAD COUNTS. FIRST TO {target} S WINS.",
            "FALL OFF THE SCREEN: BACK IN LAST.")


def pad_lines(humans: int) -> tuple[tuple[tuple[str, str | None], ...], ...]:
    """Who drives with which pad, as lines of (text, player whose colour it
    is in, or None for plain): the same split as config.CONTROLS."""
    if humans == 1:
        return ((("EITHER PAD: ", None), ("P1", "p1")),)
    if humans == 2:
        return ((("LEFT PAD: ", None), ("P1", "p1"), ("  RIGHT PAD: ", None), ("P2", "p2")),)
    right = ((("RIGHT PAD: ", None), ("P2", "p2")) if humans == 3 else
             (("RIGHT STICK: ", None), ("P2", "p2"), (" BUTTONS: ", None), ("P4", "p4")))
    return ((("LEFT STICK: ", None), ("P1", "p1"), (" BUTTONS: ", None), ("P3", "p3")), right)


def demo_start(track: Track) -> tuple[float, int, int]:
    """Where the demo begins: (station, the wire both start on, the one P1
    pulls out onto). The stretch ahead that bends least on those two wires,
    where P1 can change between them and its new wire is not the longer,
    outer one, with no kicker on it, and no boost pad if it can be helped."""
    if track.name not in _starts:
        best, best_start = math.inf, (0.0, 1, 0)
        s = 0.0
        while s < track.length:
            if any((lip - s) % track.length < STRETCH for lip in track.d.kickers):
                s += 25.0
                continue
            for lane, to in WIRES:
                if not all(track.can_switch(s + d, lane, to) for d in range(0, int(PASS_ROOM), 25)):
                    continue
                worst = 0.0
                for d in range(0, int(STRETCH), 10):
                    bend = max(abs(track.curvature(w, s + d)) for w in (lane, to))
                    longer = max(0.0, track.factor(to, s + d) - track.factor(lane, s + d))
                    worst = max(worst, bend * (1.0 if d < PASS_ROOM else 0.3) + 0.1 * longer)
                worst += sum(1.0 for at, lanes in track.d.boosts
                             if (at - s) % track.length < STRETCH and {lane, to} & set(lanes))
                if worst < best:
                    best, best_start = worst, (s, lane, to)
            s += 25.0
        _starts[track.name] = best_start
    return _starts[track.name]


class Demo:
    """The card's looping scene. racer_keys: which racer each of PLAYERS
    drives, for drawing (P1's own pick, and a bot's)."""

    def __init__(self, track: Track, racer_keys: dict[str, str]) -> None:
        self.track = track
        self.racer_keys = dict(racer_keys)
        self.events: list[Cue] = []  # the last frame's, for the renderer's popups
        self._start()

    def _start(self) -> None:
        from qarrera.match import Pack  # match.py imports this module

        stats = {p: dataclasses.replace(config.CAR, max_speed=v) for p, v in SPEED.items()}
        race = Race(self.track, PLAYERS, random.Random(1), humans=("p1",), stats=stats)
        race.racer_keys = dict(self.racer_keys)
        race.gates, race.items, race.gate_due, race.item_due = [], [], [], []  # nothing in the way
        s0, lane, self.to = demo_start(self.track)
        p0 = race.p_of(s0)
        for b, p in zip(race.bodies, (p0, p0 + START_GAP)):
            b.p = b.reach = p
            b.lane, b.u = lane, float(lane)
            b.v = SPEED["cpu1"]
            b.z = self.track.height(race.s_of(p))
        self.pack = Pack(race)
        self.pack.camera = Director(ASPECT, VIEW)
        me = race.front("p1")
        x, y, h = race.pose(me)
        self.pack.camera.snap(x, y, me.z, h)
        self.t = 0.0
        self.pulled_out = False

    @property
    def race(self) -> Race:
        return self.pack.race

    @property
    def phase(self) -> str:
        if self.pack.holder == "p1":
            return "lead"
        return "pass" if self.pulled_out else "draft"

    @property
    def caption(self) -> str:
        return CAPTIONS[self.phase]

    def update(self, dt: float) -> None:
        self.t += dt
        if self.t >= LOOP:
            self._start()
        race = self.race
        me, bot = race.front("p1"), race.front("cpu1")
        mine = Controls(throttle=True)
        if not self.pulled_out and (self.t >= PULL_AT or race.gap(bot.p, me.p) < PULL_GAP):
            self.pulled_out = True
            mine.left, mine.right = self.to < me.lane, self.to > me.lane
        self.events = self.pack.update(dt, {"p1": mine, "cpu1": Controls(throttle=True)})
        # the camera stays on the person's racer, not the leader
        x, y, h = race.pose(me)
        self.pack.camera.snap(x, y, me.z, h)
