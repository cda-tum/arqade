"""Session flow. Pure (no pygame): it takes one FrameInput per frame and
returns cues, so it is unit tested like the microgames.

  title (bots play an attract demo after 3 s untouched)
    -> intro -> play -> result -> [speed up every 4 microgames]
       -> [BOSS! after every 12 wins -> intro -> boss -> result] -> intro ...
       (Start pauses any of these: resume / quit to title)
    single:  out of lives -> game over -> initials (if it's a high score)
             -> high scores -> title
    versus:  someone out of lives -> match result -> rematch or title

In versus both players get their own instance of the same microgame from
the same seed, at the same moment. A success scores 1, and if both succeed
the one who finished first scores 1 more. A failure costs a life. The match
ends when anyone is out of lives: the last player standing wins; if both go
out together, the higher score wins, and equal scores are a draw.

After every 12 wins (in versus: microgames anyone won) comes a boss: one
long game in phases, worth 3 points (plus the first-finish bonus), costing a
life if lost like any microgame. It ends as soon as everyone is done.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from planck_time import config
from planck_time.hiscores import Hiscores
from planck_time.microgames import BOSSES, REGISTRY, Microgame, PlayerInput, play_time

PLAYERS = ("p1", "p2")
TITLE = "title"
INTRO = "intro"
PLAY = "play"
RESULT = "result"
SPEED_UP = "speed_up"
BOSS_CARD = "boss_card"
GAME_OVER = "game_over"
NAME_ENTRY = "name_entry"
HISCORES = "hiscores"
MATCH_RESULT = "match_result"
PAUSABLE = (INTRO, PLAY, RESULT, SPEED_UP, BOSS_CARD)
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PAUSE_ITEMS = ("RESUME", "QUIT TO TITLE")
ATTRACT_LINGER = 1.0  # seconds an attract microgame stays up after its time runs out


@dataclass(frozen=True)
class Cue:
    """A session event for the sound and the renderer."""

    kind: str  # blip, start, pause, intro, win, fail, speed_up, boss, game_over, match_won, draw
    player: str | None = None


def _per_player(make):
    return lambda: {p: make() for p in PLAYERS}


@dataclass
class FrameInput:
    players: dict = field(default_factory=_per_player(PlayerInput))  # in a microgame, per pad
    nav: dict = field(default_factory=_per_player(lambda: (0, 0)))  # menus: stick presses, auto-repeated
    confirms: dict = field(default_factory=_per_player(bool))  # A or Start pressed this frame
    backs: dict = field(default_factory=_per_player(bool))  # B pressed this frame
    pauses: dict = field(default_factory=_per_player(bool))  # Start pressed this frame
    activity: bool = False  # any input at all (for the idle timeout and the attract demo)

    @property
    def confirm(self) -> bool:
        return any(self.confirms.values())

    @property
    def back(self) -> bool:
        return any(self.backs.values())

    @property
    def pause(self) -> bool:
        return any(self.pauses.values())


def merge(a: PlayerInput, b: PlayerInput) -> PlayerInput:
    """Both pads as one, for single player: the stronger stick, any press."""
    stick = a.stick if abs(a.stick[0]) + abs(a.stick[1]) >= abs(b.stick[0]) + abs(b.stick[1]) else b.stick
    step = a.step if a.step != (0, 0) else b.step
    return PlayerInput(stick, step, a.a or b.a, a.a_held or b.a_held)


class Deck:
    """The order of microgames: a shuffled deck of all of them, so none comes
    up again until every one has, and never the same one twice in a row
    (across a reshuffle)."""

    def __init__(self, games: list, rng: random.Random) -> None:
        self.games = list(games)
        self.rng = rng
        self.pile: list = []
        self.last = None

    def draw(self):
        if not self.pile:
            self.pile = self.games[:]
            self.rng.shuffle(self.pile)
            if len(self.pile) > 1 and self.pile[-1] is self.last:
                self.pile[0], self.pile[-1] = self.pile[-1], self.pile[0]
        self.last = self.pile.pop()
        return self.last


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
            self.pos = max(0, min(2, self.pos + dx))
        if confirm:
            if self.pos < 2:
                self.pos += 1
            else:
                self.done = True
        if back:
            self.pos = max(0, self.pos - 1)
        return bool(dx or dy or confirm or back)


class Session:
    def __init__(
        self,
        rng: random.Random | None = None,
        hiscores: Hiscores | None = None,
        registry: list[type[Microgame]] | None = None,
        bosses: list[type[Microgame]] | None = None,
    ) -> None:
        self.rng = rng or random.Random()
        self.hiscores = hiscores if hiscores is not None else Hiscores(None)
        self.registry = list(registry if registry is not None else REGISTRY)
        self.bosses = list(bosses if bosses is not None else BOSSES)
        self.boss_index = 0  # bosses come round in order
        self.toward_boss = 0  # wins since the last boss
        self.mode = 1  # 1 or 2 players
        self.state = TITLE
        self.t = 0.0  # seconds in the current state
        self.idle = 0.0
        self.deck = Deck(self.registry, self.rng)
        self.game_cls: type[Microgame] | None = None
        self.seed = 0
        self.games: dict[str, Microgame] = {}
        self.first_time = False  # this microgame's first appearance in the session (the intro demo)
        self.seen: set[str] = set()
        self.played = 0
        self.lives = {p: config.LIVES for p in PLAYERS}
        self.scores = {p: 0 for p in PLAYERS}
        self.gained = {p: 0 for p in PLAYERS}  # points from the last microgame, for the result card
        self.first = None  # who finished first, when both succeeded
        self.winner: str | None = None  # versus: None with match_over is a draw
        self.name_entry: NameEntry | None = None
        self.new_rank: int | None = None
        self.paused = False
        self.pause_index = 0
        self.attract: dict[str, Microgame] = {}
        self._cued: set[str] = set()

    @property
    def players(self) -> tuple[str, ...]:
        return ("p1",) if self.mode == 1 else PLAYERS

    @property
    def level(self) -> int:
        return self.played // config.GAMES_PER_LEVEL

    @property
    def duration(self) -> float:
        if self.game_cls is not None:
            return self.game_cls.duration_for(self.level)
        return play_time(self.level)

    @property
    def boss(self) -> bool:
        """The current game is a boss."""
        return self.game_cls is not None and self.game_cls.BOSS

    @property
    def score(self) -> int:
        """The single-player score: microgames cleared."""
        return self.scores["p1"]

    @property
    def time_left(self) -> float:
        """0..1 of the play time remaining (the timer bar)."""
        if self.state == PLAY:
            return max(0.0, 1.0 - self.t / self.duration)
        return 1.0 if self.state == INTRO else 0.0

    # --- the state machine ------------------------------------------------------------------

    def update(self, dt: float, inp: FrameInput) -> list:
        self.idle = 0.0 if inp.activity else self.idle + dt
        if self.state != TITLE and self.idle >= config.IDLE_TIMEOUT:
            if self.state == NAME_ENTRY:
                self._save_name()
            self._to_title()
            return []
        events: list = []
        if self.state in PAUSABLE and (self.paused or inp.pause):
            self._on_pause(inp, events)
            return events
        self.t += dt
        getattr(self, f"_on_{self.state}")(dt, inp, events)
        return events

    def _on_pause(self, inp: FrameInput, events: list) -> None:
        """Start pauses (either pad). In the menu the stick moves, A picks, and
        Start or B resumes. Nothing moves meanwhile, the timer included."""
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
        if inp.activity:
            self.attract = {}
        if any(d != (0, 0) for d in inp.nav.values()):
            self.mode = 3 - self.mode
            events.append(Cue("blip"))
        if inp.confirm:
            self._start_session(events)
            return
        if self.idle >= config.ATTRACT_DELAY:
            self._run_attract(dt)

    def _run_attract(self, dt: float) -> None:
        """Bots play random microgames on both screens, each its own."""
        if not self.attract or all(g.t >= g.duration + ATTRACT_LINGER for g in self.attract.values()):
            level = self.rng.randrange(4)
            picks = self.rng.sample(self.registry, min(2, len(self.registry)))
            self.attract = {
                p: picks[i % len(picks)](self.rng.randrange(1 << 30), level, play_time(level))
                for i, p in enumerate(PLAYERS)
            }
        for g in self.attract.values():
            if g.t < g.duration:
                g.update(dt, g.bot())
            else:
                if g.result is None:
                    g.timeout()
                g.update(dt, PlayerInput())

    def _on_intro(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.t >= config.INTRO_TIME:
            self.seen.add(self.game_cls.__name__)
            self._set_state(PLAY)

    def _on_play(self, dt: float, inp: FrameInput, events: list) -> None:
        for p, g in self.games.items():
            g.update(dt, self._input_for(inp, p))
            if g.result is not None and p not in self._cued:
                self._cued.add(p)
                events.append(Cue("win" if g.result else "fail", p))
        everyone_failed = all(g.result is False for g in self.games.values())
        # a boss is long: once everyone is done, don't make them wait out the timer
        boss_done = self.boss and all(
            g.result is not None and g.since_end >= config.BOSS_LINGER for g in self.games.values())
        if self.t >= self.duration or everyone_failed or boss_done:
            self._end_play(events)

    def _end_play(self, events: list) -> None:
        for p, g in self.games.items():
            if g.result is None:
                g.timeout()
            if p not in self._cued:
                self._cued.add(p)
                events.append(Cue("win" if g.result else "fail", p))
        self.gained = {p: 0 for p in PLAYERS}
        for p, g in self.games.items():
            if g.result:
                self.gained[p] += self.game_cls.POINTS
            else:
                self.lives[p] -= 1
        winners = [p for p, g in self.games.items() if g.result]
        self.first = None
        if len(winners) == 2:
            a, b = (self.games[p].won_at for p in winners)
            if a != b:
                self.first = winners[0] if a < b else winners[1]
                self.gained[self.first] += 1
        for p in PLAYERS:
            self.scores[p] += self.gained[p]
        self._set_state(RESULT)

    def _on_result(self, dt: float, inp: FrameInput, events: list) -> None:
        for g in self.games.values():  # keep the win and fail animations going
            g.update(dt, PlayerInput())
        if self.t < config.RESULT_TIME:
            return
        out = [p for p in self.players if self.lives[p] <= 0]
        if self.mode == 1 and out:
            self._set_state(GAME_OVER)
            events.append(Cue("game_over"))
        elif out:
            self._end_match(out, events)
        elif self.boss:
            self._next_microgame(events)
        else:
            self.played += 1
            if any(g.result for g in self.games.values()):
                self.toward_boss += 1
            if self.played % config.GAMES_PER_LEVEL == 0:
                self._set_state(SPEED_UP)
                events.append(Cue("speed_up"))
            else:
                self._after_cards(events)

    def _after_cards(self, events: list) -> None:
        """After a result (and any SPEED UP!): the boss if one is due, else the
        next microgame."""
        if self.bosses and self.toward_boss >= config.BOSS_EVERY:
            self.toward_boss = 0
            self._set_state(BOSS_CARD)
            events.append(Cue("boss"))
        else:
            self._next_microgame(events)

    def _end_match(self, out: list, events: list) -> None:
        if len(out) == 1:
            self.winner = "p2" if out[0] == "p1" else "p1"
        elif self.scores["p1"] != self.scores["p2"]:
            self.winner = max(PLAYERS, key=self.scores.get)
        else:
            self.winner = None
        self._set_state(MATCH_RESULT)
        events.append(Cue("match_won", self.winner) if self.winner else Cue("draw"))

    def _on_speed_up(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.t >= config.SPEED_UP_TIME:
            self._after_cards(events)

    def _on_boss_card(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.t >= config.BOSS_CARD_TIME:
            boss = self.bosses[self.boss_index % len(self.bosses)]
            self.boss_index += 1
            self._next_microgame(events, boss)

    def _on_game_over(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.t >= config.GAME_OVER_TIME:
            if self.hiscores.qualifies(self.score):
                self.name_entry = NameEntry()
                self._set_state(NAME_ENTRY)
            else:
                self.new_rank = None
                self._set_state(HISCORES)

    def _on_name_entry(self, dt: float, inp: FrameInput, events: list) -> None:
        pads = PLAYERS  # single player: either pad types
        dx = next((inp.nav[p][0] for p in pads if inp.nav[p][0]), 0)
        dy = next((inp.nav[p][1] for p in pads if inp.nav[p][1]), 0)
        if self.name_entry.update(dx, dy, inp.confirm, inp.back):
            events.append(Cue("blip"))
        if self.name_entry.done:
            self._save_name()
            self._set_state(HISCORES)

    def _on_hiscores(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.t >= config.HISCORES_TIME or (self.t >= config.MATCH_RESULT_LOCK and (inp.confirm or inp.back)):
            self._to_title()

    def _on_match_result(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.t >= config.MATCH_RESULT_LOCK:
            if inp.confirm:
                self._start_session(events)
            elif inp.back:
                self._to_title()

    # --- helpers and transitions -------------------------------------------------------------

    def _input_for(self, inp: FrameInput, player: str) -> PlayerInput:
        if self.mode == 2:
            return inp.players[player]
        return merge(inp.players["p1"], inp.players["p2"])

    def _set_state(self, state: str) -> None:
        self.state = state
        self.t = 0.0

    def _to_title(self) -> None:
        self.games = {}
        self.attract = {}
        self.paused = False
        self._set_state(TITLE)

    def _save_name(self) -> None:
        if self.name_entry is not None:
            rank = self.hiscores.add(self.name_entry.name, self.score, self.level)
            self.new_rank = rank if rank >= 0 else None
            self.name_entry = None

    def _start_session(self, events: list) -> None:
        self.lives = {p: config.LIVES for p in PLAYERS}
        self.scores = {p: 0 for p in PLAYERS}
        self.gained = {p: 0 for p in PLAYERS}
        self.played = 0
        self.toward_boss = 0
        self.boss_index = 0
        self.seen = set()
        self.deck = Deck(self.registry, self.rng)
        self.winner = None
        self.new_rank = None
        self.attract = {}
        events.append(Cue("start"))
        self._next_microgame(events)

    def _next_microgame(self, events: list, cls: type[Microgame] | None = None) -> None:
        self.game_cls = cls or self.deck.draw()
        self.seed = self.rng.randrange(1 << 30)
        self.games = {p: self.game_cls(self.seed, self.level, self.duration) for p in self.players}
        self.first_time = self.game_cls.__name__ not in self.seen
        self._cued = set()
        self._set_state(INTRO)
        events.append(Cue("intro"))
