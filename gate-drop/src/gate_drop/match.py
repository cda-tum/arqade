"""Match flow. Pure (no pygame): it takes one FrameInput per frame and
returns events, so it is unit tested like board.py.

  title -> setup -> how to play -> countdown -> round (Start pauses: resume / quit to title) -> ...
    versus:  round result -> countdown ... -> match result -> rematch (no how to play) or title
    single:  level clear -> countdown (next level) ... game over
             -> initials (if it's a high score) -> high scores -> title

The title is a short menu: 1 PLAYER, 2 PLAYERS and QUIT. Start always
plays (with the mode last picked), A picks the row, and A on QUIT leaves
the game (the loop sees quit_requested). Every match started from the setup
screen first shows the HOW TO PLAY card, until any button is pressed.

On the setup screen each player picks a level (2n + 2 errors) and a speed;
with two players, each sets their own as a handicap. Players on the same
level get the same layout, and both boards always get the same pills.
Chains on one board drop T gates on the other.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from arqade_common import web

from gate_drop import config, levels
from gate_drop.board import Board, Event, PlayerInput
from gate_drop.hiscores import Hiscores

PLAYERS = ("p1", "p2")
TITLE = "title"
SETUP = "setup"
TUTORIAL = "tutorial"
COUNTDOWN = "countdown"
ROUND = "round"
ROUND_RESULT = "round_result"
MATCH_RESULT = "match_result"
LEVEL_CLEAR = "level_clear"
GAME_OVER = "game_over"
NAME_ENTRY = "name_entry"
HISCORES = "hiscores"
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PAUSE_ITEMS = ("RESUME", "QUIT TO TITLE")
TITLE_ITEMS = ("1 PLAYER", "2 PLAYERS", "QUIT")  # the first two rows are the modes
QUIT_ROW = TITLE_ITEMS.index("QUIT")


@dataclass(frozen=True)
class Cue:
    """A match-level event for the sound and the renderer."""

    kind: str  # beep, go, blip, confirm, back, pause, round_won, draw, match_won, level_clear, game_over
    player: str | None = None


@dataclass(frozen=True)
class BoardEvent:
    player: str
    event: Event


def _per_player(make):
    return lambda: {p: make() for p in PLAYERS}


@dataclass
class FrameInput:
    players: dict = field(default_factory=_per_player(PlayerInput))  # in game, per pad
    nav: dict = field(default_factory=_per_player(lambda: (0, 0)))  # menus: stick presses, auto-repeated
    confirms: dict = field(default_factory=_per_player(bool))  # A or Start pressed this frame
    backs: dict = field(default_factory=_per_player(bool))  # B pressed this frame
    pauses: dict = field(default_factory=_per_player(bool))  # Start pressed this frame
    any_button: bool = False  # any pad button (or, in dev, any key) newly pressed this frame
    activity: bool = False  # any input at all (for the idle timeout)

    @property
    def confirm(self) -> bool:
        return any(self.confirms.values())

    @property
    def back(self) -> bool:
        return any(self.backs.values())

    @property
    def pause(self) -> bool:
        return any(self.pauses.values())


def other(player: str) -> str:
    return "p2" if player == "p1" else "p1"


def fall_interval(t: float, speed: str = config.DEFAULT_SPEED) -> float:
    """Seconds per row, t seconds into a round, at a speed setting."""
    start, floor = config.SPEED_FALL[speed]
    return max(floor, start * config.FALL_SPEEDUP ** int(t // config.FALL_SPEEDUP_EVERY))


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


@dataclass
class Setup:
    """One player's choices on the setup screen: row 0 is the level, row 1 the speed."""

    level: int = config.DEFAULT_LEVEL
    speed: str = config.DEFAULT_SPEED
    row: int = 0
    ready: bool = False

    def update(self, dx: int, dy: int, confirm: bool, back: bool) -> str | None:
        """Returns "back" (leave the screen), "ready", "changed" or None."""
        if self.ready:
            if back:
                self.ready = False
                return "changed"
            return None
        if back:
            return "back"
        if confirm:
            self.ready = True
            return "ready"
        changed = False
        if dy:
            self.row = (self.row + dy) % 2
            changed = True
        if dx and self.row == 0:
            level = _clamp(self.level + dx, config.LEVEL_MIN, config.LEVEL_MAX)
            changed |= level != self.level
            self.level = level
        elif dx:
            i = _clamp(config.SPEEDS.index(self.speed) + dx, 0, len(config.SPEEDS) - 1)
            changed |= config.SPEEDS[i] != self.speed
            self.speed = config.SPEEDS[i]
        return "changed" if changed else None


class NameEntry:
    """Three initials: the stick changes the letter (up = next) and moves the
    cursor, A moves on and finishes on the last letter, B steps back."""

    def __init__(self) -> None:
        self.letters = [0, 0, 0]
        self.pos = 0
        self.done = False

    @property
    def name(self) -> str:
        return "".join(LETTERS[i] for i in self.letters)

    def update(self, dx: int, dy: int, confirm: bool, back: bool) -> bool:
        if dy:
            self.letters[self.pos] = (self.letters[self.pos] - dy) % len(LETTERS)
        if dx:
            self.pos = _clamp(self.pos + dx, 0, 2)
        if confirm:
            if self.pos < 2:
                self.pos += 1
            else:
                self.done = True
        if back:
            self.pos = max(0, self.pos - 1)
        return bool(dx or dy or confirm or back)


class Match:
    def __init__(self, rng: random.Random | None = None, hiscores: Hiscores | None = None) -> None:
        self.rng = rng or random.Random()
        self.hiscores = hiscores if hiscores is not None else Hiscores(None)
        self.mode = 2  # 1 or 2 players
        self.title_index = self.mode - 1  # the title menu's selected row
        self.quit_requested = False  # QUIT picked on the title: the game loop exits
        self.state = TITLE
        self.t = 0.0  # seconds in the current state
        self.idle = 0.0
        self.setups = {p: Setup() for p in PLAYERS}  # remembered from game to game
        self.scores = {p: 0 for p in PLAYERS}  # round wins (versus)
        self.boards: dict[str, Board] = {}
        self.round_no = 1
        self.round_time = 0.0
        self.last_winner: str | None = None
        self.match_winner: str | None = None
        self.level = config.DEFAULT_LEVEL  # single player
        self.score = 0
        self.last_bonus = 0
        self.name_entry: NameEntry | None = None
        self.new_rank: int | None = None
        self.paused = False
        self.pause_index = 0
        self._beeps = 0

    @property
    def players(self) -> tuple[str, ...]:
        return ("p1",) if self.mode == 1 else PLAYERS

    # --- input helpers --------------------------------------------------------------------

    def _menu(self, inp: FrameInput, player: str) -> tuple[int, int, bool, bool]:
        """(dx, dy, confirm, back) for a player; in single player either pad counts."""
        pads = PLAYERS if self.mode == 1 else (player,)
        dx = next((inp.nav[p][0] for p in pads if inp.nav[p][0]), 0)
        dy = next((inp.nav[p][1] for p in pads if inp.nav[p][1]), 0)
        return dx, dy, any(inp.confirms[p] for p in pads), any(inp.backs[p] for p in pads)

    def _board_input(self, inp: FrameInput, player: str) -> PlayerInput:
        if self.mode == 2:
            return inp.players[player]
        a, b = inp.players["p1"], inp.players["p2"]
        return PlayerInput(a.move or b.move, a.cw or b.cw, a.ccw or b.ccw, a.soft or b.soft)

    # --- the state machine ------------------------------------------------------------------

    def update(self, dt: float, inp: FrameInput) -> list:
        self.idle = 0.0 if inp.activity else self.idle + dt
        if self.state != TITLE and self.idle >= config.IDLE_TIMEOUT:
            if self.state == NAME_ENTRY:
                self._save_name()
            self._to_title()
            return []
        events: list = []
        if self.state == ROUND and (self.paused or inp.pause):
            self._on_pause(inp, events)
            return events
        self.t += dt
        getattr(self, f"_on_{self.state}")(dt, inp, events)
        return events

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
        dy = next((d[1] for d in inp.nav.values() if d[1]), 0)
        if dy:
            self.pause_index = (self.pause_index + dy) % len(PAUSE_ITEMS)
            events.append(Cue("blip"))
        if any(inp.confirms[p] and not inp.pauses[p] for p in PLAYERS):  # A, not Start
            events.append(Cue("blip"))
            if PAUSE_ITEMS[self.pause_index] == "RESUME":
                self.paused = False
            else:
                self._to_title()

    def _on_title(self, dt: float, inp: FrameInput, events: list) -> None:
        """Up and down move through 1 PLAYER, 2 PLAYERS and QUIT; left and
        right flip between the two modes. Start plays whatever row is lit,
        A picks the row, and B does nothing here."""
        dx = next((d[0] for d in inp.nav.values() if d[0]), 0)
        dy = next((d[1] for d in inp.nav.values() if d[1]), 0)
        if dy:
            self.title_index = (self.title_index + dy) % len(TITLE_ITEMS)
            events.append(Cue("blip"))
        elif dx and self.title_index != QUIT_ROW:
            self.title_index = 1 - self.title_index
            events.append(Cue("blip"))
        if self.title_index != QUIT_ROW:
            self.mode = self.title_index + 1
        if inp.pause or (inp.confirm and self.title_index != QUIT_ROW):
            for s in self.setups.values():
                s.ready, s.row = False, 0
            self._set_state(SETUP)
            events.append(Cue("confirm"))
        elif inp.confirm:  # A on QUIT: no confirm dialog
            self.quit_requested = True

    def _on_setup(self, dt: float, inp: FrameInput, events: list) -> None:
        for p in self.players:
            result = self.setups[p].update(*self._menu(inp, p))
            if result == "back":
                self._to_title()
                events.append(Cue("back"))
                return
            if result:
                events.append(Cue("confirm" if result == "ready" else "blip"))
        if all(self.setups[p].ready for p in self.players):
            self._set_state(TUTORIAL)

    def _on_tutorial(self, dt: float, inp: FrameInput, events: list) -> None:
        """The HOW TO PLAY card: any button starts the match, once it has been
        up for TUTORIAL_LOCK (so the A that readied up can't skip it unseen).
        Input is edge-based, so the dismissing press is spent here and can't
        rotate or pause anything in the round."""
        if self.t < config.TUTORIAL_LOCK:
            return
        if inp.any_button or inp.confirm or inp.back or inp.pause:
            events.append(Cue("confirm"))
            self._start_match(events)

    def _on_countdown(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.t >= config.COUNTDOWN:
            self._set_state(ROUND)
            self.round_time = 0.0
            events.append(Cue("go"))
        elif int(self.t) >= self._beeps:
            self._beeps += 1
            events.append(Cue("beep"))

    def _on_round(self, dt: float, inp: FrameInput, events: list) -> None:
        self.round_time += dt
        for p in self.players:
            board = self.boards[p]
            board.fall_interval = fall_interval(self.round_time, self.setups[p].speed)
            board_events = board.update(dt, self._board_input(inp, p))
            events += [BoardEvent(p, e) for e in board_events]
            if self.mode == 1:
                self.score_events(board_events)
        if self.mode == 1:
            self._check_solo(events)
        else:
            self._check_versus(events)

    def score_events(self, board_events: list[Event]) -> None:
        """Single player: each error cleared scores ERROR_POINTS x speed,
        doubled for every chain step after the first (capped)."""
        mult = config.SPEED_SCORE[self.setups["p1"].speed]
        chain = 1
        for e in board_events:
            if e.kind == "clear":
                chain = max(1, e.value)
            elif e.kind == "errors":
                self.score += e.value * config.ERROR_POINTS * mult * min(config.CHAIN_MULT_CAP, 2 ** (chain - 1))

    def _check_solo(self, events: list) -> None:
        board = self.boards["p1"]
        if board.errors_left() == 0:
            self.last_bonus = config.LEVEL_CLEAR_BONUS * self.level * config.SPEED_SCORE[self.setups["p1"].speed]
            self.score += self.last_bonus
            events.append(Cue("level_clear"))
            self._set_state(LEVEL_CLEAR)
        elif board.topped_out:
            events.append(Cue("game_over"))
            self._set_state(GAME_OVER)

    def _check_versus(self, events: list) -> None:
        for p in PLAYERS:
            board = self.boards[p]
            if board.outgoing:
                self.boards[other(p)].noise_queue += [config.NOISE_KIND] * board.outgoing
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

    def _on_round_result(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.t < config.ROUND_RESULT_TIME:
            return
        leader = max(self.scores, key=self.scores.get)
        if self.scores[leader] >= config.ROUNDS_TO_WIN:
            self.match_winner = leader
            self._set_state(MATCH_RESULT)
            events.append(Cue("match_won", leader))
        else:
            if self.last_winner is not None:  # a draw replays the round
                self.round_no += 1
            self._start_countdown(events)

    def _on_match_result(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.t >= config.MATCH_RESULT_LOCK:
            if inp.confirm:
                self._start_match(events)
            elif inp.back:
                self._to_title()

    def _on_level_clear(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.t >= config.LEVEL_CLEAR_TIME:
            self.level = min(config.LEVEL_MAX, self.level + 1)
            self.round_no += 1
            self._start_countdown(events)

    def _on_game_over(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.t >= config.GAME_OVER_TIME:
            if self.hiscores.qualifies(self.score):
                self.name_entry = NameEntry()
                self._set_state(NAME_ENTRY)
            else:
                self.new_rank = None
                self._set_state(HISCORES)

    def _on_name_entry(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.name_entry.update(*self._menu(inp, "p1")):
            events.append(Cue("blip"))
        if self.name_entry.done:
            self._save_name()
            self._set_state(HISCORES)

    def _on_hiscores(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.t >= config.HISCORES_TIME or (self.t >= config.MATCH_RESULT_LOCK and (inp.confirm or inp.back)):
            self._to_title()

    # --- transitions -----------------------------------------------------------------------

    def _set_state(self, state: str) -> None:
        self.state = state
        self.t = 0.0

    def back_to_title(self) -> None:
        """Leave whatever is going on for the title (the browser's way of quitting)."""
        if self.state == NAME_ENTRY:
            self._save_name()
        self._to_title()

    def _to_title(self) -> None:
        self.boards = {}
        self.paused = False
        self.title_index = self.mode - 1  # never back onto QUIT
        self._set_state(TITLE)

    def _save_name(self) -> None:
        if self.name_entry is not None:
            rank = self.hiscores.add(self.name_entry.name, self.score, self.level)
            self.new_rank = rank if rank >= 0 else None
            if rank >= 0:
                web.post_score("gate-drop", "default", self.score, self.name_entry.name)
            self.name_entry = None

    def _start_match(self, events: list) -> None:
        self.scores = {p: 0 for p in PLAYERS}
        self.match_winner = None
        self.round_no = 1
        self.level = self.setups["p1"].level
        self.score = 0
        self.new_rank = None
        self._start_countdown(events)

    def _level_of(self, player: str) -> int:
        return self.level if self.mode == 1 else self.setups[player].level

    def _start_countdown(self, events: list) -> None:
        seed = self.rng.randrange(1 << 30)
        self.boards = {}
        for p in self.players:
            level = self._level_of(p)
            layout = levels.error_layout(random.Random(seed * 16 + level), levels.errors_for_level(level))
            self.boards[p] = Board(layout, seed)
        self.round_time = 0.0
        self._set_state(COUNTDOWN)
        self._beeps = 1
        events.append(Cue("beep"))
