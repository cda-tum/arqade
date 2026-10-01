"""Match flow: title -> countdown -> round -> round result -> ... -> match
result. Pure (no pygame): it takes one FrameInput per frame and returns
events, so it is unit tested like board.py.

Both boards get the same error layout and the same pill sequence each round.
Chains on one board send noise gates to the other. A round ends when a
board has no errors left, or when a board tops out.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from gate_drop import config, levels
from gate_drop.board import Board, Event, PlayerInput

PLAYERS = ("p1", "p2")
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


@dataclass(frozen=True)
class BoardEvent:
    player: str
    event: Event


def _idle() -> dict:
    return {p: PlayerInput() for p in PLAYERS}


@dataclass
class FrameInput:
    players: dict = field(default_factory=_idle)  # player -> board.PlayerInput
    confirm: bool = False  # A or Start pressed this frame, either pad
    back: bool = False  # B pressed this frame, either pad
    activity: bool = False  # any input at all (for the idle timeout)


def other(player: str) -> str:
    return "p2" if player == "p1" else "p1"


def fall_interval(t: float) -> float:
    """Seconds per row, t seconds into a round."""
    steps = int(t // config.FALL_SPEEDUP_EVERY)
    return max(config.FALL_MIN, config.FALL_START * config.FALL_SPEEDUP ** steps)


class Match:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.state = TITLE
        self.t = 0.0  # seconds in the current state
        self.idle = 0.0
        self.scores = {p: 0 for p in PLAYERS}
        self.boards: dict[str, Board] = {}
        self.round_no = 1
        self.round_time = 0.0
        self.last_winner: str | None = None
        self.match_winner: str | None = None
        self._beeps = 0

    @property
    def danger(self) -> bool:
        """A stack is close to the top (the music speeds up, the frame blinks)."""
        return self.state == ROUND and any(b.stack_top() < config.DANGER_ROWS for b in self.boards.values())

    def update(self, dt: float, inp: FrameInput) -> list:
        self.idle = 0.0 if inp.activity else self.idle + dt
        if self.state != TITLE and self.idle >= config.IDLE_TIMEOUT:
            self.boards = {}
            self._set_state(TITLE)
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
                    if self.last_winner is not None:  # a draw replays the same round
                        self.round_no += 1
                    self._start_countdown(events)
        elif self.state == MATCH_RESULT:
            if self.t >= config.MATCH_RESULT_LOCK:
                if inp.confirm:
                    self._start_match(events)
                elif inp.back:
                    self.boards = {}
                    self._set_state(TITLE)
        return events

    def _set_state(self, state: str) -> None:
        self.state = state
        self.t = 0.0

    def _start_match(self, events: list) -> None:
        self.scores = {p: 0 for p in PLAYERS}
        self.match_winner = None
        self.round_no = 1
        self._start_countdown(events)

    def _start_countdown(self, events: list) -> None:
        seed = self.rng.randrange(1 << 30)
        layout = levels.error_layout(random.Random(seed), levels.errors_for_round(self.round_no))
        self.boards = {p: Board(layout, seed) for p in PLAYERS}
        self.round_time = 0.0
        self._set_state(COUNTDOWN)
        self._beeps = 1
        events.append(Cue("beep"))

    def _update_round(self, dt: float, inp: FrameInput, events: list) -> None:
        self.round_time += dt
        interval = fall_interval(self.round_time)
        for p in PLAYERS:
            board = self.boards[p]
            board.fall_interval = interval
            events += [BoardEvent(p, e) for e in board.update(dt, inp.players.get(p, PlayerInput()))]
        for p in PLAYERS:
            board = self.boards[p]
            if board.outgoing:
                self.boards[other(p)].noise_queue += [self.rng.choice(config.PAULIS) for _ in range(board.outgoing)]
                board.outgoing = 0
        wins = {p for p in PLAYERS if self.boards[p].errors_left() == 0 or self.boards[other(p)].topped_out}
        if not wins:
            return
        if len(wins) == 2:
            self.last_winner = None
            events.append(Cue("draw"))
        else:
            winner = wins.pop()
            self.last_winner = winner
            self.scores[winner] += 1
            events.append(Cue("round_won", winner))
        self._set_state(ROUND_RESULT)
