"""Match flow: title -> racer select -> how to play -> countdown -> race ->
match result.
Pure (no pygame): it takes one FrameInput per frame and returns cues, so it
is unit tested.

On the title the stick moves between PLAYERS, BOTS, LEVEL, TRACK and LEAD
(up/down) and changes the one picked (left/right); Start (on any row) or A
goes on to the racer select. The last row is QUIT: A there leaves the game
(back to the cabinet's menu), Start still starts. Bots (ai.py) take the places people leave free, up to
config.MAX_RACERS racers, each on a racer of its own. Behind the menu,
four bots race the chosen track as a demo.

The racer select works like Mario Kart's: every person moves their own
cursor over the roster with their own stick, or their buttons if that is
all they have (cursor_sources). With one or two people, each locks in with
A on their pad (B unlocks), and the race starts
once everyone has; with three or four (whose button players have no A to
spare: it steers them), Start starts with whatever everyone is on. Start
always starts at once. B, with nobody locked in, goes back to the title.

Then the HOW TO PLAY card (tutorial.py) until any button, and the
countdown. A rematch from the match result skips the card: the same people
just played.

The camera (camera.Director) follows the leader, as in BlazeRush, and the
leader scores: every second in front counts, and the first to the target
(30, 60 or 90 s) wins the match. A racer off the screen for OUT_DELAY is
put back in at the back of the pack, already moving (a copy from a CNOT
that is still on the screen saves its player the trip).

Start pauses a countdown or the race; the pause menu offers RESUME and QUIT
TO TITLE.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from qarrera import config, racers, tracks, tutorial
from qarrera.ai import Driver
from qarrera.camera import Director
from qarrera.race import Body, Controls, Cue, Race
from qarrera.track import Track

TITLE = "title"
SELECT = "select"
TUTORIAL = "tutorial"
COUNTDOWN = "countdown"
RACE = "race"
MATCH_END = "match_end"
MENU_ROWS = ("PLAYERS", "BOTS", "LEVEL", "TRACK", "LEAD", "QUIT")
SETTINGS_ROWS = MENU_ROWS[:-1]
DEMO_LEVELS = {"cpu1": "BRUTAL", "cpu2": "TOUGH", "cpu3": "TOUGH", "cpu4": "EASY"}
PAUSE_ITEMS = ("RESUME", "QUIT TO TITLE")
SELECT_COLS = 5  # the roster as a 5 x 2 grid
SELECT_GO = 0.6  # seconds after the last person locks in
STEPS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}


@dataclass
class FrameInput:
    # per input source, ("stick", pad) or ("pad", pad): the directions held
    # this frame and the ones newly pressed ("up", "down", "left", "right")
    held: dict = field(default_factory=dict)
    pressed: dict = field(default_factory=dict)
    nav: tuple[int, int] | None = None  # a stick direction newly pushed this frame (menus)
    confirm: bool = False  # A or Start pressed this frame, either pad
    back: bool = False  # B pressed this frame, either pad
    pause: bool = False  # Start pressed this frame, either pad
    pick: bool = False  # A pressed this frame, either pad (picks a pause-menu item)
    activity: bool = False  # any input at all (for the idle timeout)
    pad_a: tuple[bool, bool] = (False, False)  # A pressed this frame, per pad
    pad_b: tuple[bool, bool] = (False, False)  # B pressed this frame, per pad
    any_button: bool = False  # any button at all pressed this frame, either pad (or, in dev, any key)


def controls_for(humans: int, player: str, inp: FrameInput) -> Controls:
    """A person's controls, from whichever of their inputs they use. Up is
    faster, down slower (the cruise control, race.py), left/right a wire
    change, all relative to the racer."""
    c = Controls()
    for source in config.CONTROLS[humans][player]:
        held = inp.held.get(source, ())
        pressed = inp.pressed.get(source, ())
        c.throttle |= "up" in held
        c.brake |= "down" in held
        c.left |= "left" in pressed
        c.right |= "right" in pressed
    return c


def pads_of(humans: int, player: str) -> set[int]:
    """The pads whose A and B are this person's own in the racer select:
    alone, both; with two, their own; with more, none (Start starts)."""
    if humans == 1:
        return {0, 1}
    if humans == 2:
        return {0} if player == "p1" else {1}
    return set()


def cursor_sources(humans: int, player: str) -> tuple:
    """The inputs that move a person's cursor in the racer select: their
    sources from config.CONTROLS, but not the face buttons of a pad whose A
    and B lock them in and out (pads_of). Those buttons steer like W A S D
    in a race, A being "right", so an A meant to lock in moved the cursor
    one racer to the right first. With three or four people the button
    players have no A to lock with, and their buttons do move them."""
    lockers = pads_of(humans, player)
    return tuple(src for src in config.CONTROLS[humans][player] if not (src[0] == "pad" and src[1] in lockers))


class Pack:
    """A race, the camera on its leader, who leads and for how long, and
    putting whoever falls off the screen back in at the back of the pack.
    The match and the title's demo each use one."""

    def __init__(self, race: Race) -> None:
        self.race = race
        self.camera = Director()
        self.off: dict[int, float] = {}  # body id -> seconds off the screen
        self.holder: str | None = None  # who has the lead (nobody, off the grid)
        self.lead_time = {p: 0.0 for p in race.players}
        lead = race.leader()
        x, y, h = race.pose(lead)
        self.camera.snap(x, y, lead.z, h)

    def update(self, dt: float, controls: dict[str, Controls]) -> list[Cue]:
        race = self.race
        events = race.update(dt, controls)
        self._lead(dt, events)
        lead = self.lead_body()
        x, y, h = race.pose(lead)
        self.camera.update(dt, x, y, race.track.height(race.s_of(lead.p)), h)
        self._resets(dt, events)
        return events

    def lead_body(self) -> Body:
        return self.race.front(self.holder) if self.holder else self.race.leader()

    def _lead(self, dt: float, events: list) -> None:
        """The lead changes hands only once the challenger is LEAD_MARGIN
        clear, so two racers side by side don't swap it every frame."""
        race = self.race
        best = race.leader()
        if best.player != self.holder:
            if self.holder is not None:
                rival = race.front(self.holder).p
            else:
                rival = max((b.p for b in race.bodies if b.player != best.player), default=-math.inf)
            if best.p > rival + config.LEAD_MARGIN:
                self.holder = best.player
                events.append(race._cue("lead", best))
        if self.holder is not None:
            self.lead_time[self.holder] += dt

    def _resets(self, dt: float, events: list) -> None:
        race, cam = self.race, self.camera
        for player in race.players:
            mine = race.bodies_of(player)
            for b in mine:
                x, y, _ = race.pose(b)
                if b.ghost > 0 or cam.on_screen(x, y, b.z):
                    self.off.pop(b.id, None)
                else:
                    self.off[b.id] = self.off.get(b.id, 0.0) + dt
            gone = [b for b in mine if self.off.get(b.id, 0.0) >= config.OUT_DELAY]
            if not gone:
                continue
            if len(gone) < len(mine):  # another copy is still on the screen
                for b in gone:
                    race.drop_copy(b, events)
                    self.off.pop(b.id, None)
            elif player != self.holder:
                p, v = self._back_of_pack(player)
                for b in mine:
                    self.off.pop(b.id, None)
                race.reset(player, p, v, events)

    def _back_of_pack(self, player: str) -> tuple[float, float]:
        """Where and how fast a racer comes back: RESET_BEHIND behind the last
        racer still on the screen, but well inside it, and a good part of the
        leader's speed."""
        race, cam = self.race, self.camera
        lead = self.lead_body()

        def seen(p: float, margin: float) -> bool:
            x, y, _ = race.track.pose((config.LANES - 1) / 2, race.s_of(p))
            return cam.on_screen(x, y, race.track.height(race.s_of(p)), margin)

        others = [b.p for b in race.bodies if b.player != player and b.ghost <= 0
                  and seen(b.p, config.OUT_MARGIN)]
        p = min(others, default=lead.p) - config.RESET_BEHIND
        while p < lead.p - 2 * config.CAR_LEN and not seen(p, -config.RESET_INSET):
            p += 8.0
        p = min(p, lead.p - 2 * config.CAR_LEN)
        top = race.racers[player].stats.max_speed
        v = min(top, max(config.RESET_MIN * top, config.RESET_SPEED * lead.v))
        return p, v


class Match:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.tracks = [Track(d) for d in tracks.ALL]
        self.humans = config.DEFAULT_HUMANS
        self.bots = config.DEFAULT_BOTS
        self.level = config.DEFAULT_LEVEL
        self.track_index = 0
        self.target = config.TARGET_DEFAULT  # seconds in the lead to win
        self.row = 0
        self.state = TITLE
        self.t = 0.0  # seconds in the current state
        self.idle = 0.0
        self.pack: Pack | None = None
        self.drivers: dict[str, Driver] = {}
        self.demo: Pack | None = None  # the bots racing behind the title menu
        self.demo_drivers: dict[str, Driver] = {}
        self.picks: dict[str, int] = {}  # each person's racer, as an index into the roster
        self.locked: set[str] = set()
        self.all_locked_at: float | None = None
        self.racer_of: dict[str, str] = {}  # the racer key per player, bots included
        self.winner: str | None = None
        self.paused = False
        self.pause_index = 0
        self._beeps = 0
        self.tutorial: tutorial.Demo | None = None  # the HOW TO PLAY card's demo, while it shows
        self.quit = False  # QUIT picked on the title: the game loop ends

    @property
    def people(self) -> tuple[str, ...]:
        return config.HUMANS[self.humans]

    @property
    def players(self) -> tuple[str, ...]:
        return self.people + config.BOTS[:self.bots]

    @property
    def track(self) -> Track:
        return self.tracks[self.track_index]

    @property
    def race(self) -> Race | None:
        return self.pack.race if self.pack is not None else None

    @property
    def lead_time(self) -> dict[str, float]:
        return self.pack.lead_time if self.pack is not None else {}

    def update(self, dt: float, inp: FrameInput) -> list[Cue]:
        self.idle = 0.0 if inp.activity else self.idle + dt
        if self.state != TITLE and self.idle >= config.IDLE_TIMEOUT:
            self._to_title()
            return []
        events: list[Cue] = []
        if self.state in (COUNTDOWN, RACE) and (self.paused or inp.pause):
            self._on_pause(inp, events)
            return events
        self.t += dt
        if self.state == TITLE:
            self._on_title(inp, events)
            if self.state == TITLE:
                self._update_demo(dt)
        elif self.state == SELECT:
            self._on_select(inp, events)
        elif self.state == TUTORIAL:
            self._on_tutorial(dt, inp, events)
        elif self.state == COUNTDOWN:
            if self.t >= config.COUNTDOWN:
                self._set_state(RACE)
                events.append(Cue("go"))
            elif int(self.t) >= self._beeps:
                self._beeps += 1
                events.append(Cue("beep"))
        elif self.state == RACE:
            controls = {p: controls_for(self.humans, p, inp) for p in self.people}
            controls.update({p: d.controls(self.race, dt) for p, d in self.drivers.items()})
            events += self.pack.update(dt, controls)
            self._score(dt, events)
        elif self.state == MATCH_END:
            if self.t >= config.RESULT_LOCK:
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
        self.pack = None
        self.tutorial = None
        self.paused = False
        self._set_state(TITLE)

    def back_to_title(self) -> None:
        """Back on the title after a quit that had nowhere to go (the browser),
        with the settings kept and QUIT no longer picked."""
        self.quit = False
        self.row = 0
        self._to_title()

    def _on_title(self, inp: FrameInput, events: list) -> None:
        if inp.nav in ((0, -1), (0, 1)):
            self.row = (self.row + inp.nav[1]) % len(MENU_ROWS)
            events.append(Cue("blip"))
        elif inp.nav in ((-1, 0), (1, 0)) and MENU_ROWS[self.row] != "QUIT":
            self._change(MENU_ROWS[self.row], inp.nav[0])
            events.append(Cue("blip"))
        if inp.pick and not inp.pause and MENU_ROWS[self.row] == "QUIT":
            self.quit = True  # A on QUIT; Start always starts
        elif inp.confirm or inp.pause:
            self._to_select(events)

    def _bots_range(self) -> tuple[int, int]:
        """Alone, at least one bot: alone, you would lead the whole way."""
        return (1 if self.humans == 1 else 0), config.MAX_RACERS - self.humans

    def _change(self, row: str, step: int) -> None:
        if row == "PLAYERS":
            counts = config.HUMAN_COUNTS
            self.humans = counts[(counts.index(self.humans) + step) % len(counts)]
            lo, hi = self._bots_range()
            self.bots = max(lo, min(self.bots, hi))
        elif row == "BOTS":
            lo, hi = self._bots_range()
            self.bots = lo + (self.bots - lo + step) % (hi - lo + 1)
        elif row == "LEVEL":
            self.level = config.LEVELS[(config.LEVELS.index(self.level) + step) % len(config.LEVELS)]
        elif row == "TRACK":
            self.track_index = (self.track_index + step) % len(self.tracks)
        elif row == "LEAD":
            i = config.TARGET_CHOICES.index(self.target)
            self.target = config.TARGET_CHOICES[(i + step) % len(config.TARGET_CHOICES)]

    def _update_demo(self, dt: float) -> None:
        if self.demo is None or self.demo.race.track is not self.track:
            rng = random.Random(self.track_index)
            keys = rng.sample([r.key for r in racers.ROSTER], len(DEMO_LEVELS))
            racer_keys = dict(zip(DEMO_LEVELS, keys))
            stats = {p: racers.BY_KEY[k].stats() for p, k in racer_keys.items()}
            race = Race(self.track, tuple(DEMO_LEVELS), rng, stats=stats)
            race.racer_keys = racer_keys
            self.demo = Pack(race)
            self.demo_drivers = {p: Driver(p, level, rng) for p, level in DEMO_LEVELS.items()}
        race = self.demo.race
        self.demo.update(dt, {p: d.controls(race, dt) for p, d in self.demo_drivers.items()})

    # --- the racer select -------------------------------------------------------------------

    def _to_select(self, events: list) -> None:
        for i, p in enumerate(self.people):  # keep earlier picks, spread out new ones
            self.picks.setdefault(p, (i * 2) % len(racers.ROSTER))
        self.locked = set()
        self.all_locked_at = None
        self._set_state(SELECT)
        events.append(Cue("confirm"))

    def _on_select(self, inp: FrameInput, events: list) -> None:
        n = len(racers.ROSTER)
        rows = (n + SELECT_COLS - 1) // SELECT_COLS
        for p in self.people:
            if p in self.locked:
                continue
            for source in cursor_sources(self.humans, p):
                for name in inp.pressed.get(source, ()):
                    dx, dy = STEPS[name]
                    col, row = self.picks[p] % SELECT_COLS, self.picks[p] // SELECT_COLS
                    col, row = (col + dx) % SELECT_COLS, (row + dy) % rows
                    self.picks[p] = min(n - 1, row * SELECT_COLS + col)
                    events.append(Cue("blip", p))
        unlocked = False
        for p in self.people:
            mine = pads_of(self.humans, p)
            if p not in self.locked and any(inp.pad_a[i] for i in mine):
                self.locked.add(p)
                events.append(Cue("lock", p))
            elif p in self.locked and any(inp.pad_b[i] for i in mine):
                self.locked.discard(p)
                self.all_locked_at = None
                unlocked = True
                events.append(Cue("blip", p))
        if inp.pause:
            self._start_match(events, card=True)
            return
        if inp.back and not self.locked and not unlocked:
            self._to_title()
            events.append(Cue("blip"))
            return
        if self.humans <= 2 and len(self.locked) == len(self.people):
            if self.all_locked_at is None:
                self.all_locked_at = self.t
            elif self.t - self.all_locked_at >= SELECT_GO:
                self._start_match(events, card=True)

    def _bot_racers(self) -> dict[str, str]:
        """Each bot on a racer nobody else is on, as long as there are any."""
        taken = {racers.ROSTER[self.picks[p]].key for p in self.people}
        free = [r.key for r in racers.ROSTER if r.key not in taken]
        self.rng.shuffle(free)
        out = {}
        for p in config.BOTS[:self.bots]:
            if not free:
                free = [r.key for r in racers.ROSTER]
                self.rng.shuffle(free)
            out[p] = free.pop()
        return out

    # --- pause and the match ------------------------------------------------------------------

    def _on_pause(self, inp: FrameInput, events: list) -> None:
        """Start pauses (either pad). In the menu the stick moves, A picks,
        and Start or B resumes. Nothing in the race moves meanwhile."""
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

    def _start_match(self, events: list, card: bool = False) -> None:
        """From the select, with everyone's pick and fresh bot racers, and the
        HOW TO PLAY card first (card); from the match result, the same racers
        again, straight to the countdown."""
        self.demo = None
        for i, p in enumerate(self.people):
            self.picks.setdefault(p, (i * 2) % len(racers.ROSTER))
        if self.state != MATCH_END or set(self.racer_of) != set(self.players):
            self.racer_of = {p: racers.ROSTER[self.picks[p]].key for p in self.people}
            self.racer_of.update(self._bot_racers())
        self.winner = None
        stats = {p: racers.BY_KEY[k].stats() for p, k in self.racer_of.items()}
        race = Race(self.track, self.players, self.rng, humans=self.people, stats=stats)
        race.racer_keys = dict(self.racer_of)
        self.pack = Pack(race)
        self.drivers = {p: Driver(p, self.level, self.rng) for p in self.players if p not in self.people}
        self.paused = False
        if card:
            bot = next((self.racer_of[p] for p in self.players if p not in self.people),
                       racers.ROSTER[(self.picks["p1"] + 4) % len(racers.ROSTER)].key)
            self.tutorial = tutorial.Demo(self.track, {"p1": self.racer_of["p1"], "cpu1": bot})
            self._set_state(TUTORIAL)
            events.append(Cue("confirm"))
            return
        self._to_countdown(events)

    def _to_countdown(self, events: list) -> None:
        self._set_state(COUNTDOWN)
        self._beeps = 1
        events.append(Cue("beep"))

    def _on_tutorial(self, dt: float, inp: FrameInput, events: list) -> None:
        """The card's demo plays until any button, pressed after the first
        tutorial.LOCK seconds (so the press that started the match, or its
        bounce, doesn't skip it unseen). The stick does nothing. The
        countdown only reads new presses, so the dismissing one does
        nothing else."""
        self.tutorial.update(dt)
        if inp.any_button and self.t >= tutorial.LOCK:
            self.tutorial = None
            events.append(Cue("confirm"))
            self._to_countdown(events)

    def _score(self, dt: float, events: list) -> None:
        """The leader's seconds tick for the last FINAL_TICKS before the
        target; at the target it has won."""
        holder = self.pack.holder
        if holder is None:
            return
        now = self.pack.lead_time[holder]
        if self.target - config.FINAL_TICKS <= int(now) < self.target and int(now) > int(now - dt):
            events.append(Cue("tick", holder))
        if now >= self.target:
            self.winner = holder
            self._set_state(MATCH_END)
            events.append(Cue("match_won", holder))

    def table(self) -> list[str]:
        """The players by seconds in the lead, most first (who is ahead now
        breaks ties)."""
        now = self.race.standings() if self.race is not None else list(self.players)
        return sorted(self.players, key=lambda p: (-self.lead_time.get(p, 0.0), now.index(p) if p in now else 99))
