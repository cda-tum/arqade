"""Match flow: title -> countdown -> round -> round result -> ... -> match
result. Pure (no pygame): it takes one FrameInput per frame and returns
events, so it is unit tested like rules.py.

The simulation ticks at the current speed. Steering and split presses are
kept between ticks: the latest stick direction since the last tick wins,
so a quick tap between two ticks is not lost.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from qurves import config, rules

TITLE = "title"
COUNTDOWN = "countdown"
ROUND = "round"
ROUND_RESULT = "round_result"
MATCH_RESULT = "match_result"


@dataclass(frozen=True)
class Cue:
    """A match-level event for the sound and the renderer."""

    kind: str  # "beep", "go", "round_won", "draw" or "match_won"
    player: str | None = None


def _per_player(value):
    return lambda: {p: value for p in rules.PLAYERS}


@dataclass
class FrameInput:
    direction: dict = field(default_factory=_per_player(None))  # held stick direction
    split: dict = field(default_factory=_per_player(False))  # A pressed this frame
    confirm: bool = False  # A or Start pressed this frame, either pad
    back: bool = False  # B pressed this frame, either pad
    activity: bool = False  # any input at all (for the idle timeout)


def speed_at(t: float) -> float:
    """Cells per second, t seconds into a round."""
    steps = int(t // config.SPEED_STEP_EVERY)
    return min(config.SPEED_MAX, config.SPEED_START + steps * config.SPEED_STEP)


class Match:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.state = TITLE
        self.t = 0.0  # seconds in the current state
        self.idle = 0.0
        self.scores = {p: 0 for p in rules.PLAYERS}
        self.round: rules.RoundState | None = None
        self.round_time = 0.0
        self.tick_accum = 0.0
        self.last_winner: str | None = None
        self.match_winner: str | None = None
        self._beeps = 0
        self._reset_pending()

    @property
    def tick_fraction(self) -> float:
        """How far the current tick has progressed, 0..1, for interpolation."""
        return min(1.0, self.tick_accum * speed_at(self.round_time))

    def update(self, dt: float, inp: FrameInput) -> list:
        self.idle = 0.0 if inp.activity else self.idle + dt
        if self.state != TITLE and self.idle >= config.IDLE_TIMEOUT:
            self._to_title()
            return []
        self.t += dt
        events: list = []
        if self.state == TITLE:
            if inp.confirm:
                self._start_match(events)
        elif self.state == COUNTDOWN:
            if self.t >= config.COUNTDOWN:
                self._set_state(ROUND)
                self.round_time = 0.0
                self.tick_accum = 0.0
                self._reset_pending()
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
        self._set_state(TITLE)

    def _start_match(self, events: list) -> None:
        self.scores = {p: 0 for p in rules.PLAYERS}
        self.match_winner = None
        self._start_countdown(events)

    def _start_countdown(self, events: list) -> None:
        self.round = rules.new_round(self.rng)
        self.round_time = 0.0
        self.tick_accum = 0.0
        self._set_state(COUNTDOWN)
        self._beeps = 1
        events.append(Cue("beep"))

    def _reset_pending(self) -> None:
        self._dir = {p: None for p in rules.PLAYERS}
        self._split = {p: False for p in rules.PLAYERS}

    def _update_round(self, dt: float, inp: FrameInput, events: list) -> None:
        for p in rules.PLAYERS:
            if inp.direction.get(p) is not None:
                self._dir[p] = inp.direction[p]
            if inp.split.get(p):
                self._split[p] = True
        self.round_time += dt
        self.tick_accum += dt
        rs = self.round
        while not rs.over:
            interval = 1.0 / speed_at(self.round_time)
            if self.tick_accum < interval:
                break
            self.tick_accum -= interval
            inputs = {p: rules.PlayerInput(self._dir[p], self._split[p]) for p in rules.PLAYERS}
            self._reset_pending()
            events += rules.tick(rs, inputs, self.rng)
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
