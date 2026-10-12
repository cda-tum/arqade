"""The match flow: title, countdown, race, pause and result. Pure (no pygame).

`Match.update(dt, FrameInput)` steps it and returns the frame's cues: `Cue`s for the menus
and the countdown, plus the race's own `race.Event`s for the players' cars (the sound and
the HUD use both).

    TITLE --A/Start--> COUNTDOWN (3-2-1-GO) --> RACE --all players finished--> RESULT
      ^  \\_ 3 s untouched: an attract race of 6 bots plays behind the title      |
      |                                                      A/Start rematches  |
      +----------------- B, QUIT TO TITLE, or 60 s untouched ------------------+

- **The title:** the stick's up/down picks 1 or 2 PLAYERS (as the menu stands), from the
  direction it is held in, not its repeated steps: a held stick, a diagonal too, stays on
  its choice. Sideways does nothing. When the pads disagree P1's wins. A or Start begins. After ATTRACT_DELAY
  seconds untouched an attract race plays behind it: `Race(seed, 2, finish_all=True)`, all
  six cars driven by bots, silently. Any input stops it (and that frame's stick changes
  nothing); A or Start still begins at once.
  At launch, and reached through QUIT TO TITLE or B, the title waits for every button to be
  let go, so a button held as the game starts, or the press that left the race, doesn't
  start the next one.
- **Driving:** each player's stick steers and pulled back brakes; A *pressed* uses the held
  item (never A held, or a held button would fire the next item the moment a box gives it).
  With 1 PLAYER either pad drives P1. A player past the line is driven on by a bot and the
  pad no longer counts.
- **The CIRCUIT CHECK freeze:** for CHECK_FREEZE seconds after a player crosses into the
  final lap (`frozen(p)`, the race's `check_wait`) their view shows the comparison and their
  pad does nothing: the car drives straight on (the line is on the start straight) and loses
  no distance. The race, and any other player, runs on.
- **Banners**, per player, for the HUD: "gate" flashes each row's outcome for FLASH_TIME
  (value ("right", streak), ("wrong", slot) or ("miss", slot); one at a time), "tip" says how
  to use an item on its first pickup (value the item; once per item and player each
  session, a session ending when the idle timeout sends the cabinet back to the title),
  "lap" (LAP 2) and "finish" (the place, until the result).
- **Pause:** Start (either pad) pauses the countdown or the race: RESUME / QUIT TO TITLE.
  The stick moves, A picks, B or Start resumes. Nothing moves meanwhile.
- **The end:** once every player has finished (or, with 2 players, FINISH_GRACE seconds
  after the first one did) the race is frozen into `results`; FINISH_DELAY later the result
  screen shows it. A or Start rematches (after RESULT_LOCK), B goes to the title.
- **Idle:** IDLE_TIMEOUT seconds untouched anywhere but the title (paused too) returns to
  the title and resets it to 1 PLAYER. Start + Select quitting is the main loop's.
- All the races are `finish_all=True`, so the CPU cars drive on behind the finish banner;
  the match decides when the race is over, and freezes the places at that moment.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

from gate_prix import bot, config
from gate_prix.car import Controls
from gate_prix.race import Event, Race

PLAYERS = ("p1", "p2")
TITLE = "title"
COUNTDOWN = "countdown"
RACE = "race"
PAUSED = "paused"
RESULT = "result"


@dataclass(frozen=True)
class Cue:
    """A match-level event: blip, select, count (3, 2, 1), go, pause, resume, title,
    finish (the race is over), result."""

    kind: str
    player: str | None = None
    value: object = None


@dataclass(frozen=True)
class PlayerInput:
    """One pad (merged with its dev keys) for one frame."""

    steer: float = 0.0  # -1 (left) to 1, deadzoned
    brake: float = 0.0  # 0 to 1: the stick pulled back
    nav: tuple[int, int] = (0, 0)  # menu steps, auto-repeated: (x, y), y positive is down
    stick: tuple[int, int] = (0, 0)  # the direction held now (past half way), not repeated
    a: bool = False  # pressed this frame
    b: bool = False
    start: bool = False
    select: bool = False  # (only the main loop's Start + Select quit uses Select)
    held: bool = False  # any of A, B, Start or Select held down


def _players() -> dict[str, PlayerInput]:
    return {p: PlayerInput() for p in PLAYERS}


@dataclass
class FrameInput:
    players: dict[str, PlayerInput] = field(default_factory=_players)
    activity: bool = False  # anything touched at all (for the idle timeout and the attract)

    def held_only(self) -> FrameInput:
        """The same input without its presses: for a second logic step in one frame."""
        still = {"nav": (0, 0), "a": False, "b": False, "start": False, "select": False}
        return FrameInput({p: replace(i, **still) for p, i in self.players.items()},
                          self.activity)

    def any(self, name: str) -> bool:
        return any(getattr(i, name) for i in self.players.values())

    def nav(self) -> tuple[int, int]:
        """The first stick step of any pad."""
        return next((i.nav for i in self.players.values() if i.nav != (0, 0)), (0, 0))


@dataclass
class Banner:
    kind: str  # "gate", "tip", "lap" (value: the lap), "finish" (the place): see the top
    value: object
    time: float | None  # seconds left; None for one that stays until the result


@dataclass(frozen=True)
class ResultRow:
    car: str
    place: int
    player: bool
    time: float | None  # its finishing time, None when it was still racing
    right: int  # right slots of its circuit
    check: int | None  # its CIRCUIT CHECK distance
    slots: tuple = ()  # its circuit's gates (None: an empty slot), frozen at the finish
    results: tuple = ()  # and each slot's right (True), wrong (False) or undecided (None)


class Match:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.state = TITLE
        self.mode = 1  # 1 or 2 PLAYERS
        self.t = 0.0  # seconds in the current state
        self.idle = 0.0
        self.race: Race | None = None
        self.bots: dict[str, bot.Bot] = {}
        self.seed = 0
        self.attract = False
        self.title_wait = True  # the title waits for every button to be let go (at launch too)
        self.pause_index = 0
        self.paused_from = RACE
        self.banners: dict[str, list[Banner]] = {p: [] for p in PLAYERS}
        self.results: list[ResultRow] | None = None
        self.first_finish: float | None = None  # race time the first player finished
        self.over_time: float | None = None  # seconds since the race was frozen
        self.tips_seen: dict[str, set[str]] = {p: set() for p in PLAYERS}  # this session's
        self._count = 0

    # --- Queries for the renderer ------------------------------------------------------------

    @property
    def players(self) -> tuple[str, ...]:
        """The cars driven by people (the attract race has none)."""
        if self.race is None or self.attract:
            return ()
        return PLAYERS[: self.race.players]

    @property
    def countdown(self) -> int:
        """3, 2 or 1 during the countdown, 0 once it is GO."""
        if self.state == COUNTDOWN or (self.state == PAUSED and self.paused_from == COUNTDOWN):
            return max(1, 3 - int(self.t))
        return 0

    def banner(self, player: str, kind: str) -> Banner | None:
        return next((b for b in self.banners[player] if b.kind == kind), None)

    def frozen(self, player: str) -> bool:
        """Whether a player's view is frozen on the CIRCUIT CHECK's comparison now."""
        return (self.race is not None and player in self.players
                and self.race.racer(player).check_wait > 0)

    # --- The state machine -------------------------------------------------------------------

    def update(self, dt: float, inp: FrameInput) -> list:
        self.idle = 0.0 if inp.activity else self.idle + dt
        if self.state != TITLE and self.idle >= config.IDLE_TIMEOUT:
            self._to_title(wait=False)
            self.mode = 1
            self.tips_seen = {p: set() for p in PLAYERS}  # someone new: tips again
            return [Cue("title")]
        events: list = []
        if self.state in (RACE, COUNTDOWN) and inp.any("start"):
            self.paused_from = self.state
            self.state = PAUSED
            self.pause_index = 0
            return [Cue("pause")]
        if self.state != PAUSED:
            self.t += dt
        getattr(self, f"_on_{self.state}")(dt, inp, events)
        return events

    def _set(self, state: str) -> None:
        self.state = state
        self.t = 0.0

    def _to_title(self, wait: bool) -> None:
        self._set(TITLE)
        self.race = None
        self.bots = {}
        self.attract = False
        self.results = None
        self.title_wait = wait
        self.idle = 0.0

    # --- The title ---------------------------------------------------------------------------

    def _on_title(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.title_wait:
            if any(i.held for i in inp.players.values()):
                return
            self.title_wait = False
        stopped = inp.activity and self.attract
        if stopped:
            self.race, self.bots, self.attract = None, {}, False
        choice = self._title_choice(inp)
        if choice is not None and not stopped and choice != self.mode:
            self.mode = choice
            events.append(Cue("blip"))
        if inp.any("a") or inp.any("start"):
            events.append(Cue("select"))
            self._new_race(events)
            return
        if self.attract:
            if self.race.over:
                self._attract()
            else:
                self.race.update(dt, bot.drive(self.race, self.bots))  # silent
        elif self.idle >= config.ATTRACT_DELAY:
            self._attract()

    @staticmethod
    def _title_choice(inp: FrameInput) -> int | None:
        """1 or 2 PLAYERS from the first pad (P1 first) whose stick is up or down: the
        direction held (or a tap's step), never the sideways axis, whose repeats run on
        their own timer and would make a diagonal flicker."""
        for p in PLAYERS:
            i = inp.players[p]
            dy = i.stick[1] or i.nav[1]
            if dy:
                return 1 if dy < 0 else 2
        return None

    def _attract(self) -> None:
        self.seed = self.rng.randrange(1 << 30)
        self.race = Race(self.seed, 2, finish_all=True)
        self.bots = bot.field(self.race, self.seed, players=config.ATTRACT_SKILL)
        self.attract = True

    def _new_race(self, events: list) -> None:
        self.seed = self.rng.randrange(1 << 30)
        self.race = Race(self.seed, self.mode, finish_all=True)
        self.bots = bot.cpu_bots(self.race, self.seed)
        self.attract = False
        self.banners = {p: [] for p in PLAYERS}
        self.results = None
        self.first_finish = None
        self.over_time = None
        self._set(COUNTDOWN)
        self._count = 3
        events.append(Cue("count", value=3))

    # --- The countdown and the race ----------------------------------------------------------

    def _on_countdown(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.t >= config.COUNTDOWN:
            self._set(RACE)
            events.append(Cue("go"))
            return
        n = 3 - int(self.t)
        if n < self._count:
            self._count = n
            events.append(Cue("count", value=n))

    def _controls(self, inp: FrameInput) -> dict[str, Controls]:
        race = self.race
        controls = bot.drive(race, self.bots)
        pads = inp.players
        for p in self.players:
            if p in self.bots:  # past the line: the autopilot drives
                continue
            if race.players == 1:  # either pad drives P1
                a, b = pads["p1"], pads["p2"]
                steer = a.steer if a.steer else b.steer
                brake = max(a.brake, b.brake)
                item = a.a or b.a
            else:
                steer, brake, item = pads[p].steer, pads[p].brake, pads[p].a
            if race.racer(p).check_wait > 0:  # frozen on the check: straight on, blind
                steer, brake, item = 0.0, 0.0, False
            controls[p] = Controls(steer, brake, item)
        return controls

    def _on_race(self, dt: float, inp: FrameInput, events: list) -> None:
        race = self.race
        mine = set(self.players)
        for e in race.update(dt, self._controls(inp)):
            if e.car in mine or (e.kind == "bump" and e.value in mine):
                events.append(e)
            if e.car in mine:
                self._on_event(e)
        self._tick_banners(dt)
        if self.over_time is not None:
            self.over_time += dt
            if self.over_time >= config.FINISH_DELAY:
                self._set(RESULT)
                events.append(Cue("result"))
            return
        racers = [race.racer(p) for p in self.players]
        if self.first_finish is None and any(r.finished for r in racers):
            self.first_finish = race.time
        late = (self.first_finish is not None
                and race.time - self.first_finish >= config.FINISH_GRACE)
        if all(r.finished for r in racers) or late:
            self._freeze()
            events.append(Cue("finish"))

    def _on_event(self, e: Event) -> None:
        banners = self.banners[e.car]
        if e.kind in ("right", "wrong", "miss"):
            banners[:] = [b for b in banners if b.kind != "gate"]
            banners.append(Banner("gate", (e.kind, e.value), config.FLASH_TIME))
        elif e.kind == "box" and e.value is not None and e.value not in self.tips_seen[e.car]:
            self.tips_seen[e.car].add(e.value)
            banners[:] = [b for b in banners if b.kind != "tip"]
            banners.append(Banner("tip", e.value, config.TIP_TIME))
        elif e.kind == "check":
            banners[:] = [b for b in banners if b.kind not in ("lap", "gate")]
        elif e.kind == "lap" and e.value != config.LAPS:  # the final lap has the check's
            banners.append(Banner("lap", e.value, config.LAP_BANNER))
        elif e.kind == "finish":
            banners[:] = [Banner("finish", e.value, None)]
            self.bots[e.car] = bot.Bot(e.car, config.AUTOPILOT_SKILL, self.seed)

    def _tick_banners(self, dt: float) -> None:
        for p, banners in self.banners.items():
            for b in banners:
                if b.time is not None:
                    b.time -= dt
            self.banners[p] = [b for b in banners if b.time is None or b.time > 0]

    def _freeze(self) -> None:
        race = self.race
        rows = []
        for place, car_id in enumerate(race.places(), 1):
            r = race.racer(car_id)
            c = r.circuit
            rows.append(ResultRow(car_id, place, r.player, r.finish_time,
                                  sum(1 for ok in c.results if ok), r.check,
                                  tuple(c.slots), tuple(c.results)))
        self.results = rows
        self.over_time = 0.0

    # --- Pause and the result ----------------------------------------------------------------

    def _on_paused(self, dt: float, inp: FrameInput, events: list) -> None:
        if inp.any("start") or inp.any("b"):
            self.state = self.paused_from
            events.append(Cue("resume"))
            return
        dy = inp.nav()[1]
        if dy:
            self.pause_index = (self.pause_index + dy) % len(config.PAUSE_ITEMS)
            events.append(Cue("blip"))
        if inp.any("a"):
            if config.PAUSE_ITEMS[self.pause_index] == "RESUME":
                self.state = self.paused_from
                events.append(Cue("resume"))
            else:
                self._to_title(wait=True)
                events.append(Cue("title"))

    def _on_result(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.t < config.RESULT_LOCK:
            return
        if inp.any("a") or inp.any("start"):
            events.append(Cue("select"))
            self._new_race(events)
        elif inp.any("b"):
            self._to_title(wait=True)
            events.append(Cue("title"))
