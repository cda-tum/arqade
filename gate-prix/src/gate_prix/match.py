"""The match flow: title, countdown, race, pause and result. Pure (no pygame).

`Match.update(dt, FrameInput)` steps it and returns the frame's cues: `Cue`s for the menus
and the countdown, plus the race's own `race.Event`s for the players' cars and the bots'
bumps and hits a player can see (the sound and the HUD use them).

    TITLE --A/Start--> HOWTO --any button--> COUNTDOWN (3-2-1-GO) --> RACE --> RESULT
      ^  \\_ 3 s untouched: an attract race of 5 bots plays behind the title      |
      |                                     A/Start rematches (no HOWTO card) |
      +----------------- B, QUIT TO TITLE, or 60 s untouched ------------------+

- **The title:** four rows (config.TITLE_ITEMS, `title_index`): PLAYERS (`mode`: 1 or 2
  people), BOTS (`bot_count`: 0 up to CARS - people; a lone person gets the full field of 5
  by default, and 1 person with none is a time trial, 2 with none a duel), LEVEL (`level`,
  EASY / TOUGH / BRUTAL, one for every bot) and QUIT. Up and down move between the rows one
  row per push (a held stick's auto-repeats don't count, so a push for LEVEL never runs on
  to QUIT), clamped at both ends (no wrap); left and right change the highlighted row's
  value, one step per push, clamped too, and only on a push straight sideways (a diagonal
  moves the row, never a value). Only the first pad whose stick is pushed counts, so when
  the pads disagree P1's wins. Changing PLAYERS keeps a full field full (5 bots alone, 4
  with two) and otherwise clamps BOTS. The rows start at 1 player, 5 bots, EASY (a level
  a first-time visitor can beat), and go back to that whenever an attract race starts (a
  new visitor is coming); when it is stopped too the highlight is on PLAYERS, so the
  visitor who stops it never finds QUIT under A. A begins
  the race with the rows' settings, or on QUIT quits at once (`quit_requested`, the main
  loop's clean exit). Start always begins, never quits. B does nothing.
  After ATTRACT_DELAY seconds untouched an attract race plays behind it:
  `Race(seed, 0, bots=ATTRACT_BOTS, finish_all=True)`, bots only (neutral colours, CPU
  names, nobody outlined) at ATTRACT_LEVEL, its two split views following two of them
  (`viewed`), silently (the AI drives, it never touches the menu). Any input stops it (and that
  frame's stick changes nothing); A or Start still begins at once.
- **The HOW TO PLAY card** (HOWTO) comes before every match begun from the title, never
  before a rematch. Its first HOWTO_GUARD seconds ignore the buttons; after that any button
  of either pad (the stick doesn't count) goes on to the countdown, and that press does
  nothing else. The idle timeout runs on it; Start + Select quits, as everywhere.
  At launch, and reached through QUIT TO TITLE or B, the title waits for every button to be
  let go, so a button held as the game starts, or the press that left the race, doesn't
  start the next one.
- **Driving:** each player's stick steers and pulled back brakes; A *pressed* uses the held
  item (never A held, or a held button would fire the next item the moment a box gives it).
  With 1 player either pad drives P1. The bots are `ai.field` drivers at the title's LEVEL.
  A player past the line is driven on by the AI (AUTOPILOT_LEVEL) and the pad no longer
  counts.
- **The CIRCUIT CHECK freeze:** for CHECK_FREEZE seconds after a player crosses into the
  final lap (`frozen(p)`, the race's `check_wait`) their view shows the comparison and their
  pad does nothing: the car drives straight on (the line is on the start straight) and loses
  no distance. The race, and any other player, runs on.
- **Events:** a player gets the race's events of its own car, and those aimed at another car
  from its own (`AIMED`: its bumps, its MEASURE hitting, its cloud driven through). What
  happens to a bot sounds as it does for a person: a bump or a MEASURE hit (`HEARD`)
  between two bots is passed on too when a player can see it (the bot within HEAR_AHEAD
  ahead of a player's car or HEAR_BEHIND behind it). The bots' continuous and personal cues
  (their drifts and turbos, streaks, boxes, items, laps, checks) never reach the sound or
  the HUD.
- **Banners**, per player, for the HUD: "gate" flashes each row's outcome for FLASH_TIME
  (value ("right", streak), ("wrong", slot) or ("miss", slot); one at a time), "tip" says how
  to use an item on its first pickup (value the item; once per item and player each
  session, a session ending when the idle timeout sends the cabinet back to the title),
  "lap" (LAP 2/3), "final" (FINAL LAP and STORM AHEAD, shown once the check's freeze is
  over), "reveal" (the item a box just gave, popping up over the car) and "finish" (the
  place, until the result).
- **Pause:** Start (either pad) pauses the countdown or the race: RESUME / QUIT TO TITLE.
  The stick moves, A picks, B or Start resumes. Nothing moves meanwhile.
- **The end:** once every player has finished (or, with 2 players, FINISH_GRACE seconds
  after the first one did) the race is frozen into `results`; FINISH_DELAY later the result
  screen shows it. A or Start rematches (after RESULT_LOCK), B goes to the title.
- **Idle:** IDLE_TIMEOUT seconds untouched anywhere but the title (paused too) returns to
  the title and resets its rows: 1 player, 5 bots, TOUGH. Start + Select quitting is the
  main loop's.
- All the races are `finish_all=True`, so the bots drive on behind the finish banner;
  the match decides when the race is over, and freezes the places at that moment.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

from gate_prix import ai, config
from gate_prix.car import Controls, _wrapped
from gate_prix.race import Event, Race

PLAYERS = ("p1", "p2")
TITLE = "title"
COUNTDOWN = "countdown"
HOWTO = "howto"
RACE = "race"
PAUSED = "paused"
RESULT = "result"
# race events whose value is another car, cued to that car's player too: the other side of
# a bump, the shooter of a MEASURE that hit, the dropper of a cloud that was driven through
AIMED = ("bump", "collapse", "decohered")
# what happens to a bot that a player hears when they can see it: a bump, a MEASURE hit
HEARD = ("bump", "collapse")


@dataclass(frozen=True)
class Cue:
    """A match-level event: blip, select, count (3, 2, 1), go, pause, resume, title,
    finish (the race is over), result, quit (QUIT picked on the title)."""

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
    button: bool = False  # any button at all pressed this frame (X, Y, L and R too)
    held: bool = False  # any of A, B, Start or Select held down


def _players() -> dict[str, PlayerInput]:
    return {p: PlayerInput() for p in PLAYERS}


@dataclass
class FrameInput:
    players: dict[str, PlayerInput] = field(default_factory=_players)
    activity: bool = False  # anything touched at all (for the idle timeout and the attract)

    def held_only(self) -> FrameInput:
        """The same input without its presses: for a second logic step in one frame."""
        still = {"nav": (0, 0), "a": False, "b": False, "start": False, "select": False,
                 "button": False}
        return FrameInput({p: replace(i, **still) for p, i in self.players.items()},
                          self.activity)

    def any(self, name: str) -> bool:
        return any(getattr(i, name) for i in self.players.values())

    def pressed(self) -> bool:
        """Whether any button of any pad went down this frame."""
        return any(i.button or i.a or i.b or i.start or i.select for i in self.players.values())

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
    label: str  # P1, CPU1 ...
    colour: str  # its key of config.CAR_COLORS
    time: float | None  # its finishing time, None when it was still racing
    right: int  # right slots of its circuit
    check: int | None  # its CIRCUIT CHECK distance
    slots: tuple = ()  # its circuit's gates (None: an empty slot), frozen at the finish
    results: tuple = ()  # and each slot's right (True), wrong (False) or undecided (None)
    check_right: int | None = None  # how many of its check's slots were right ("CHECK 12/16")


class Match:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.state = TITLE
        self.mode = 1  # PLAYERS: 1 or 2 people
        self.bot_count = config.CARS - 1  # BOTS
        self.level = config.DEFAULT_LEVEL  # LEVEL
        self.title_index = 0  # the title's highlighted row (config.TITLE_ITEMS)
        self._title_push = 0  # the up/down direction the title's stick is held in now
        self._title_push_x = 0  # and the left/right one
        self.quit_requested = False  # QUIT picked on the title: the main loop exits
        self.t = 0.0  # seconds in the current state
        self.idle = 0.0
        self.race: Race | None = None
        self.drivers: dict[str, ai.Driver] = {}  # the AI's cars: the bots, and players past the line
        self.seed = 0
        self.attract = False
        self.attract_view: tuple[str, ...] = ()  # the two bots the attract race's views follow
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
    def viewed(self) -> tuple[str, ...]:
        """The cars the split views follow: the players', or in the attract race two bots."""
        if self.race is not None and self.attract:
            return self.attract_view
        return self.players

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
            self._title_defaults()
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

    def _title_defaults(self) -> None:
        self.mode, self.bot_count, self.level = 1, config.CARS - 1, config.DEFAULT_LEVEL
        self.title_index = 0

    def _to_title(self, wait: bool) -> None:
        self._set(TITLE)
        self.race = None
        self.drivers = {}
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
            self.race, self.drivers, self.attract = None, {}, False
            self.title_index = 0  # never QUIT under the A that stopped it
        step, change = self._title_steps(inp)
        index = max(0, min(len(config.TITLE_ITEMS) - 1, self.title_index + step))
        row = config.TITLE_ITEMS[index]
        if not stopped and index != self.title_index:
            self.title_index = index
            events.append(Cue("blip"))
        elif not stopped and change and self._change(row, change):
            events.append(Cue("blip"))
        quitting = row == "QUIT"
        if inp.any("a") and quitting:
            self.quit_requested = True
            events.append(Cue("quit"))
            return
        if inp.any("a") or inp.any("start"):
            if quitting:  # Start never quits: it races, with the rows as they are
                self.title_index = 0
            events.append(Cue("select"))
            self._set(HOWTO)
            self.race, self.drivers, self.attract = None, {}, False
            return
        if self.attract:
            if self.race.over:
                self._attract()
            else:
                self.race.update(dt, ai.drive(self.race, self.drivers))  # silent
        elif self.idle >= config.ATTRACT_DELAY:
            self._attract()

    def max_bots(self) -> int:
        """The most bots beside the people: the field is CARS cars at most."""
        return config.CARS - self.mode

    def _change(self, row: str, step: int) -> bool:
        """Step a row's value (clamped); whether it changed."""
        before = (self.mode, self.bot_count, self.level)
        if row == "PLAYERS":
            full = self.bot_count == self.max_bots()
            self.mode = max(1, min(config.MAX_PLAYERS, self.mode + step))
            self.bot_count = self.max_bots() if full else min(self.bot_count, self.max_bots())
        elif row == "BOTS":
            self.bot_count = max(0, min(self.max_bots(), self.bot_count + step))
        elif row == "LEVEL":
            i = config.LEVELS.index(self.level) + step
            self.level = config.LEVELS[max(0, min(len(config.LEVELS) - 1, i))]
        return (self.mode, self.bot_count, self.level) != before

    def _title_steps(self, inp: FrameInput) -> tuple[int, int]:
        """The title's (up/down, left/right) steps, each -1, 0 or 1: one per push of the
        first pad (P1 first) whose stick is pushed, on the frame the push begins (or a
        tap's one step), never its auto-repeats. Left/right counts only on a push straight
        sideways: a diagonal moves the row, never a value. Another pad is ignored."""
        for p in PLAYERS:
            i = inp.players[p]
            dx, dy = i.stick[0] or i.nav[0], i.stick[1] or i.nav[1]
            if dx or dy:
                step = dy if dy and dy != self._title_push else 0
                change = dx if dx and not dy and dx != self._title_push_x else 0
                # a tap holds nothing: the next tap counts
                self._title_push, self._title_push_x = i.stick[1], i.stick[0]
                return step, change
        self._title_push = self._title_push_x = 0
        return 0, 0

    # --- The HOW TO PLAY card ----------------------------------------------------------------

    def _on_howto(self, dt: float, inp: FrameInput, events: list) -> None:
        if self.t - dt >= config.HOWTO_GUARD and inp.pressed():
            self._new_race(events)

    def _attract(self) -> None:
        self._title_defaults()  # a new visitor: the rows as they find them, PLAYERS under A
        self.seed = self.rng.randrange(1 << 30)
        self.race = Race(self.seed, 0, finish_all=True, bots=config.ATTRACT_BOTS)
        self.drivers = ai.field(self.race, self.seed, config.ATTRACT_LEVEL)
        ids = [r.car.id for r in self.race.racers]
        self.attract_view = tuple(sorted(self.rng.sample(ids, 2), key=ids.index))
        self.attract = True

    def _new_race(self, events: list) -> None:
        self.seed = self.rng.randrange(1 << 30)
        self.race = Race(self.seed, self.mode, finish_all=True, bots=self.bot_count)
        self.drivers = ai.field(self.race, self.seed, self.level)
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
        controls = ai.drive(race, self.drivers)
        pads = inp.players
        for p in self.players:
            if p in self.drivers:  # past the line: the autopilot drives
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
            if e.car in mine or (e.kind in AIMED and e.value in mine):
                events.append(e)
            elif e.kind in HEARD and self._seen(e.car):
                events.append(e)  # between two bots, in sight of a player
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

    def _seen(self, car_id: str) -> bool:
        """Whether a player can see this car: within HEAR_AHEAD ahead of a player's car or
        HEAR_BEHIND behind it (a lap apart counts: the same place on the track)."""
        race = self.race
        z = race.racer(car_id).car.z
        for p in self.players:
            dz = _wrapped(z - race.racer(p).car.z, race.lap_length)
            if -config.HEAR_BEHIND <= dz <= config.HEAR_AHEAD:
                return True
        return False

    def _on_event(self, e: Event) -> None:
        banners = self.banners[e.car]
        if e.kind in ("right", "wrong", "miss"):
            banners[:] = [b for b in banners if b.kind != "gate"]
            banners.append(Banner("gate", (e.kind, e.value), config.FLASH_TIME))
        elif e.kind == "box" and e.value is not None:
            banners[:] = [b for b in banners if b.kind != "reveal"]
            banners.append(Banner("reveal", e.value, config.REVEAL_TIME))
            if e.value not in self.tips_seen[e.car]:
                self.tips_seen[e.car].add(e.value)
                banners[:] = [b for b in banners if b.kind != "tip"]
                banners.append(Banner("tip", e.value, config.TIP_TIME))
        elif e.kind == "check":
            banners[:] = [b for b in banners if b.kind not in ("lap", "gate")]
        elif e.kind == "lap" and e.value != config.LAPS:
            banners.append(Banner("lap", e.value, config.LAP_BANNER))
        elif e.kind == "lap":  # the final lap: shown after the check's freeze
            banners.append(Banner("final", e.value, config.CHECK_FREEZE + config.FINAL_BANNER))
        elif e.kind == "finish":
            banners[:] = [Banner("finish", e.value, None)]
            self.drivers[e.car] = ai.Driver(e.car, config.AUTOPILOT_LEVEL, self.seed)

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
            rows.append(ResultRow(car_id, place, r.player, r.label, r.car.colour, r.finish_time,
                                  sum(1 for ok in c.results if ok), r.check,
                                  tuple(c.slots), tuple(c.results), r.check_right))
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
