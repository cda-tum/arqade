"""Match flow: title -> countdown -> round -> round result -> ... -> match
result. Pure (no pygame): it takes one FrameInput per frame and returns
events, so it is unit tested like rules.py.

On the title, pushing the stick left or right picks 2 or 4 players. Which
input steers which player is config.CONTROLS. The simulation ticks at the
current speed; steering is kept between ticks, so the latest direction
since the last tick wins and a quick tap between two ticks is not lost.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from qurves import config, rules

TITLE = "title"
COUNTDOWN = "countdown"
ROUND = "round"
ROUND_RESULT = "round_result"
MATCH_RESULT = "match_result"
PAUSE_ITEMS = ("RESUME", "QUIT TO TITLE")


@dataclass(frozen=True)
class Cue:
    """A match-level event for the sound and the renderer."""

    kind: str  # "beep", "go", "blip", "pause", "round_won", "draw" or "match_won"
    player: str | None = None


@dataclass
class FrameInput:
    stick: tuple = (None, None)  # per pad: the stick (or hat) direction held
    pad: tuple = (None, None)  # per pad: the four face buttons as a d-pad
    nav: rules.Vec | None = None  # a stick direction newly pushed this frame (menus)
    confirm: bool = False  # A or Start pressed this frame, either pad
    back: bool = False  # B pressed this frame, either pad
    pause: bool = False  # Start pressed this frame, either pad
    pick: bool = False  # A pressed this frame, either pad (picks a pause-menu item)
    activity: bool = False  # any input at all (for the idle timeout)


def speed_at(t: float) -> float:
    """Cells per second, t seconds into a round."""
    steps = int(t // config.SPEED_STEP_EVERY)
    return min(config.SPEED_MAX, config.SPEED_START + steps * config.SPEED_STEP)


def direction_for(mode: int, player: str, inp: FrameInput) -> rules.Vec | None:
    """The direction `player` is steering, from whichever of their inputs is in use."""
    for kind, pad in config.CONTROLS[mode][player]:
        d = getattr(inp, kind)[pad]
        if d is not None:
            return d
    return None


class Match:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.mode = config.MODES[0]
        self.state = TITLE
        self.t = 0.0  # seconds in the current state
        self.idle = 0.0
        self.scores = {p: 0 for p in self.players}
        self.round: rules.RoundState | None = None
        self.round_time = 0.0
        self.tick_accum = 0.0
        self.last_winner: str | None = None
        self.match_winner: str | None = None
        self._beeps = 0
        self._pending: dict = {}
        self.paused = False
        self.pause_index = 0

    @property
    def players(self) -> tuple[str, ...]:
        return config.PLAYERS_BY_MODE[self.mode]

    @property
    def tick_fraction(self) -> float:
        """How far the current tick has progressed, 0..1, for interpolation."""
        return min(1.0, self.tick_accum * speed_at(self.round_time))

    def update(self, dt: float, inp: FrameInput) -> list:
        self.idle = 0.0 if inp.activity else self.idle + dt
        if self.state != TITLE and self.idle >= config.IDLE_TIMEOUT:
            self._to_title()
            return []
        events: list = []
        if self.state == ROUND and (self.paused or inp.pause):
            self._on_pause(inp, events)
            return events
        self.t += dt
        if self.state == TITLE:
            if inp.nav in ((-1, 0), (1, 0)):
                step = 1 if inp.nav == (1, 0) else -1
                self.mode = config.MODES[(config.MODES.index(self.mode) + step) % len(config.MODES)]
                self.scores = {p: 0 for p in self.players}
                events.append(Cue("blip"))
            if inp.confirm:
                self._start_match(events)
        elif self.state == COUNTDOWN:
            if self.t >= config.COUNTDOWN:
                self._set_state(ROUND)
                self.round_time = 0.0
                self.tick_accum = 0.0
                self._pending = {}
                events.append(Cue("go"))
            elif int(self.t) >= self._beeps:
                self._beeps += 1
                events.append(Cue("beep"))
        elif self.state == ROUND:
            self._update_round(dt, inp, events)
        elif self.state == ROUND_RESULT:
            if self.t >= config.ROUND_RESULT_TIME:
                leader = max(self.scores, key=self.scores.get)
                if self.scores[leader] >= config.ROUNDS_TO_WIN:
                    self.match_winner = leader
                    self._set_state(MATCH_RESULT)
                    events.append(Cue("match_won", leader))
                else:
                    self._start_countdown(events)
        elif self.state == MATCH_RESULT:
            if self.t >= config.MATCH_RESULT_LOCK:
                if inp.confirm:
                    self._start_match(events)
                elif inp.back:
                    self._to_title()
        return events

    # --- transitions -------------------------------------------------------------------

    def _set_state(self, state: str) -> None:
        self.state = state
        self.t = 0.0

    def _to_title(self) -> None:
        self.round = None
        self.paused = False
        self._set_state(TITLE)

    def _on_pause(self, inp: FrameInput, events: list) -> None:
        """Start pauses a round (either pad). In the menu the stick moves, A
        picks, and Start or B resumes. Nothing in the round moves meanwhile."""
        if not self.paused:
            self.paused = True
            self.pause_index = 0
            events.append(Cue("pause"))
            return
        if inp.pause or inp.back:
            self.paused = False
            events.append(Cue("blip"))
            return
        if inp.nav in ((0, -1), (0, 1)):
            self.pause_index = (self.pause_index + inp.nav[1]) % len(PAUSE_ITEMS)
            events.append(Cue("blip"))
        if inp.pick:
            events.append(Cue("blip"))
            if PAUSE_ITEMS[self.pause_index] == "RESUME":
                self.paused = False
            else:
                self._to_title()

    def _start_match(self, events: list) -> None:
        self.scores = {p: 0 for p in self.players}
        self.match_winner = None
        self._start_countdown(events)

    def _start_countdown(self, events: list) -> None:
        self.round = rules.new_round(self.rng, self.players)
        self.round_time = 0.0
        self.tick_accum = 0.0
        self._set_state(COUNTDOWN)
        self._beeps = 1
        events.append(Cue("beep"))

    def _update_round(self, dt: float, inp: FrameInput, events: list) -> None:
        for p in self.players:
            d = direction_for(self.mode, p, inp)
            if d is not None:
                self._pending[p] = d
        self.round_time += dt
        self.tick_accum += dt
        rs = self.round
        while not rs.over:
            interval = 1.0 / speed_at(self.round_time)
            if self.tick_accum < interval:
                break
            self.tick_accum -= interval
            directions, self._pending = self._pending, {}
            events += rules.tick(rs, directions, self.rng)
        if not rs.over:
            events += rules.advance(rs, dt, self.rng)
        if rs.over:
            self.last_winner = rs.winner
            if rs.winner is None:
                events.append(Cue("draw"))
            else:
                self.scores[rs.winner] += 1
                events.append(Cue("round_won", rs.winner))
            self._set_state(ROUND_RESULT)
