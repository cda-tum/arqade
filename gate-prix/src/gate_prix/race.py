"""The race: up to six cars on THE FRIDGE (1 or 2 players, cars "p1" and "p2", and up to
CARS of them in all bots, "cpu1" to "cpu5" in config.CPU_COLORS' order), their circuits, the
gate rows, laps, the CIRCUIT CHECK, places and the finish.

Pure Python, no pygame. `Race.update(dt, controls)` steps every car, resolves bumps and the
rows each car crossed, counts laps, and returns the frame's cues as `Event`s:

| kind | value |
|---|---|
| "right" | the car's streak after this gate |
| "wrong", "miss" | the slot that was filled wrong or left empty |
| "lap" | the lap the car has just started (2, 3) |
| "check" | the CIRCUIT CHECK's Hamming distance, as the car crosses into the final lap |
| "warp" | the check's boost (strength, seconds), as it starts CHECK_FREEZE later |
| "finish" | the car's finishing place |
| "bump" | the other car (each bump cues both cars) |
| "box" | the item a box gave (one of ITEMS: a box is never empty) |
| "box_full" | the item still held: the box broke but gave nothing new |
| "item" | the item the car has just used |
| "split_end" | None: the car's clone is gone, or a SPLIT it held ran out of rows |
| "drift" | the drift's charge level just reached (1, 2) |
| "turbo" | the level of the mini-turbo the car just got from letting go of a drift |
| "hazard" | the kind of the car's own storm hazard it drove into ("cloud", "mine") |
| "collapse" | the car that MEASUREd this car (each hit cues the shooter's id as value) |
| "fizzle" | None: the car's MEASURE had nobody ahead in range |
| "decohered" | the car that dropped the DECOHERENCE cloud this car drove through |
| "immune" | what a tunnelling car just passed through: "shot", "cloud", "mine", "deco" |
| "tunnel_end" | None: the car's TUNNEL is over |

Rules decided here:
- The target has SLOTS (16) gates, one per gate row, and the rows stand on laps 1 and 2
  only: the final lap is a gate-free sprint (item boxes stay on every lap).
- A row is crossed when a car's z passes the row's z. The car's x at that moment (between
  where the frame started and ended) picks the arch: the nearest whose centre is within its
  `half_width` of it (ARCH_HALF_WIDTH for the right arch, the smaller DECOY_HALF_WIDTH for a
  decoy: each as wide as it is drawn), or none. Rows are crossed strictly in order, so row k
  of the race is always the car's slot k.
- A right gate gives `streak_boost(streak)`. The CIRCUIT CHECK, as a car crosses into the
  final lap, compares all 16 slots with the target, once per car (the bots too, by their
  own circuits). Its `check_boost(distance)` starts CHECK_FREEZE seconds later (cued
  "warp"): meanwhile a player's view is frozen on the comparison (the match's and the
  renderer's business) while the car drives on, losing no distance. No boost (all 16
  wrong), no warp. Boosts never cut each other short: the car runs at
  the strongest one running, and a weaker, longer one carries on after it (`Car.give_boost`),
  so a right gate never slows a car down.
- Places: finished cars in the order they finished, then the rest by laps and distance (the
  order of `racers`, players first, breaks a tie). The race is over once every player has finished; bots still
  racing are placed where they are. An over race no longer changes. `finish_all` races on
  until every car has finished instead (the attract race, and the tests).
- Item boxes stand at the track's box lines, lap after lap; each box is one object, so a box
  taken on lap 1 is also gone for a car arriving on lap 2, until it respawns BOX_RESPAWN
  seconds later. A car crossing a box line takes the box within BOX_REACH of its x (the x
  is interpolated, as for the rows; a line the car was put past without driving through it
  doesn't count). The box breaks even when the car already holds an item;
  it only gives one (rolled by the car's place, `ITEM_ODDS`; never nothing) to a car
  holding none, and cues "box_full" for a car that already holds one. Past its last gate
  row a box never gives SPLIT or QEC (no gate is left to take or fix for the check): the
  other three share the odds.
- `Controls.item` uses the held item, before the frame's cars move:
  - SPLIT: for the next SPLIT_ROWS rows a clone drives at -x. A row is right if the car or
    the clone takes the right arch; otherwise wrong if either takes a wrong one (the car's
    gate first), otherwise missed. Using another SPLIT starts the count again. The clone
    ends after its rows, or at the finish.
  - QEC: `Circuit.qec()`, repairing the most recent mistake (not the streak). With no
    mistake it does nothing, but the item is still used.
  - A SPLIT is over with the car's last gate row: a clone still out goes and a SPLIT still
    held is dropped, as no gate is left to take (either cues "split_end", once).
  - MEASURE: a shot (`shots`) homes on the nearest car ahead in the race (not finished)
    within MEASURE_RANGE at the moment it is fired, flying MEASURE_FLIGHT seconds (and, on
    a car frozen on its CIRCUIT CHECK, waiting on it until the freeze is over). It then
    **collapses** that car: a spin-out, its streak reset, its boosts cleared. With
    nobody in range it fizzles. A car tunnelling when the shot arrives is immune.
  - TUNNEL: TUNNEL_TIME seconds through cars (no bumps either way), off-road at full
    speed, and immune to its storm, clouds and MEASURE.
  - DECOHERENCE: a cloud (`clouds`) dropped DECO_BEHIND behind the car, for DECO_TIME or
    until a car drives through it (within DECO_SIZE and half a car of it). It is a world
    object: any car can hit it, the dropper too, though it is behind the dropper and gone
    long before the dropper comes round again. On laps 1-2 the car loses its boosts and is
    `blind` for BLIND_TIME (its NEXT GATE badge and right-arch marker go blank); on the
    final lap it takes a storm cloud's slowdown instead. A tunnelling car passes through
    and leaves it.
  A car that has finished can't use an item: an item still held at the line is dropped.
- **Drifting** is the car's (from steer and brake: `Car`); a bump ends a drift with no
  turbo, and so does any hit.
- **The noise storm:** as a car starts the final lap, its own hazards are laid out from its
  check (`storm.storm`, with an RNG of the race's seed and the car's id), visible and
  active for that car only (`hazards_for`). A static cloud takes its boosts and caps it at
  CLOUD_CAP for CLOUD_TIME; a bit-flip mine spins it out (and resets its streak). A hit
  hazard is used up. The check's warp still comes, on top.
- **The check's display:** `Racer.check_right` is how many of the 16 were right, and a
  boost under CHECK_SHOW_MIN is `check_boost_none`: NO BOOST, and no warp is given.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import NamedTuple

from gate_prix import circuit, config, storm, track
from gate_prix.car import Car, Controls, bump

CPU_COLOURS = tuple(config.CPU_COLORS)  # cpu1's colour first


def label(car_id: str) -> str:
    """A car's name on screen: P1, P2, CPU1, CPU2 ..."""
    return car_id.upper()


class Event(NamedTuple):
    kind: str
    car: str  # the car's id
    value: object = None


@dataclass(slots=True)
class Shot:
    """A MEASURE in flight, from its owner's car to its target's."""

    owner: str
    target: str
    t: float = 0.0  # seconds it has flown

    @property
    def progress(self) -> float:
        """0 as it leaves its owner, 1 as it hits."""
        return min(1.0, self.t / config.MEASURE_FLIGHT)


@dataclass(slots=True)
class Cloud:
    """A DECOHERENCE cloud on the road."""

    id: int
    z: float  # race distance (the same place on every lap)
    x: float
    owner: str  # the car that dropped it
    time: float  # seconds it has left

    @property
    def reach(self) -> float:
        return config.DECO_SIZE + config.CAR_WIDTH / 2


class Racer:
    """One car in the race, with its circuit, its next row, laps and place."""

    def __init__(self, car: Car, target: list[str], player: bool) -> None:
        self.car = car
        self.circuit = circuit.Circuit(target)
        self.player = player
        self.next_row = 0  # the index of the next gate row it will cross
        self.laps = 0  # laps completed
        self.check: int | None = None  # the CIRCUIT CHECK's distance, once it has had it
        self.check_boost: tuple[float, float] | None = None
        self.check_wait = 0.0  # seconds until the check's boost starts (the freeze)
        self.warp_time: float | None = None  # the race time the check's boost started
        self.finish_time: float | None = None
        self.place = 0
        self.item: str | None = None  # the held item, one of config.ITEMS
        self.split_rows = 0  # rows the SPLIT clone still has
        self.next_box = 0  # the index of the next box line it will cross
        self.hazards: list[storm.Hazard] = []  # its own noise storm, from its check
        self.next_hazard = 0
        self.blind_time = 0.0  # seconds its NEXT GATE badge and arch marker stay blank

    @property
    def label(self) -> str:
        """Its name on screen: P1, P2, CPU1 ..."""
        return label(self.car.id)

    @property
    def check_right(self) -> int | None:
        """How many of the check's slots were right, once it has had it."""
        return None if self.check is None else config.CHECK_SLOTS - self.check

    @property
    def check_boost_none(self) -> bool:
        """Whether its check's boost was too small to give: NO BOOST."""
        return self.check_boost is not None and self.check_boost[0] < config.CHECK_SHOW_MIN

    @property
    def blind(self) -> bool:
        return self.blind_time > 0

    @property
    def effects(self) -> dict[str, float]:
        """What is running on it now, as seconds left: "tunnel", "spin", "slow", "blind"."""
        car = self.car
        now = {"tunnel": car.tunnel_time, "spin": car.spin_time, "slow": car.slow_time,
               "blind": self.blind_time}
        return {k: t for k, t in now.items() if t > 0}

    @property
    def split(self) -> bool:
        """Whether its SPLIT clone is out."""
        return self.split_rows > 0

    @property
    def clone_x(self) -> float | None:
        """The clone's x, mirrored across the centre line, while it is out."""
        return -self.car.x if self.split_rows > 0 else None

    @property
    def lap(self) -> int:
        """The lap it is on, 1 to LAPS (LAPS once finished)."""
        return min(self.laps + 1, config.LAPS)

    @property
    def finished(self) -> bool:
        return self.laps >= config.LAPS


def _x_at(car: Car, z: float) -> float:
    """The car's x as it passed race distance z during its last update."""
    span = car.z - car.prev_z
    f = (z - car.prev_z) / span if span > 0 else 1.0
    f = min(1.0, max(0.0, f))
    return car.prev_x + (car.x - car.prev_x) * f


def arch_at(row: track.GateRow, x: float) -> track.Arch | None:
    """The arch a car at x goes through, if any: the nearest within its own half-width."""
    best = None
    for arch in row.arches:
        d = abs(x - arch.offset)
        if d <= arch.half_width and (best is None or d < abs(x - best.offset)):
            best = arch
    return best


def grid(players: int, cars: int = config.CARS) -> list[tuple[float, float]]:
    """The (z, x) of each of `cars` cars on the grid, players first. Two lanes, the right
    lane half a row back; the players start side by side in the back row, P1 on the left
    and P2 on the right, so that neither starts ahead, and the bots fill the rows ahead (and
    the back row's right lane, behind a lone player)."""
    spots = []
    for k in range(max(cars, 1)):
        row, lane = divmod(k, 2)
        z = -(config.GRID_FIRST + row * config.GRID_GAP + lane * config.GRID_GAP / 2)
        spots.append((z, config.GRID_LANES[lane]))
    back = 2 * ((cars - 1) // 2) if players else len(spots)
    rest = [s for k, s in enumerate(spots) if not back <= k < back + players]
    mine = [(spots[back][0], config.GRID_LANES[i]) for i in range(players)]
    return (mine + rest)[:cars]


class Race:
    """A race of LAPS laps of the track for 1 or 2 players and `bots` bots (by default as
    many as fill the field: CARS in all). 1 player and no bots is a time trial, 2 and none a
    duel. A race of no players and only bots is for the tests and tools."""

    def __init__(self, seed: int, players: int, rng: random.Random | None = None,
                 course: track.Track | None = None, finish_all: bool = False,
                 bots: int | None = None) -> None:
        if players not in (0, 1, 2):
            raise ValueError(f"a race has 1 or 2 players, not {players}")
        bots = config.CARS - players if bots is None else bots
        if not 0 <= bots <= config.CARS - players or players + bots == 0:
            raise ValueError(f"{players} players and {bots} bots: at most {config.CARS} cars")
        self.seed = seed
        self.players = players
        self.bots = bots
        # for the items (Task 4): a stream of its own, not a copy of the target's
        self.rng = rng if rng is not None else random.Random(f"{seed}:items")
        self.track = course if course is not None else track.fridge()
        self.lap_length = self.track.lap_length()
        self.target = circuit.random_target(random.Random(seed), config.SLOTS)
        self.rows = track.gate_rows(self.track, self.target, seed)
        self.finish_all = finish_all
        # the box lines of the whole race, in order: (race distance, line index on the lap)
        self.box_lines = sorted((n * self.lap_length + z, k) for n in range(config.LAPS)
                                for k, (z, _) in enumerate(self.track.boxes))
        self._box_back: dict[tuple[int, int], float] = {}  # a taken box: when it is back
        ids = [(f"p{i + 1}", f"p{i + 1}") for i in range(players)]
        ids += list(zip(config.CPU_IDS, CPU_COLOURS))[:bots]
        self.racers: list[Racer] = []
        for i, ((car_id, colour), (z, x)) in enumerate(zip(ids, grid(players, len(ids)))):
            car = Car(car_id, colour, x)
            car.z = car.prev_z = z
            self.racers.append(Racer(car, self.target, i < players))
        self._by_id = {r.car.id: r for r in self.racers}
        self.time = 0.0
        self.finish_order: list[str] = []
        self.over = False
        self._cooldown: dict[tuple[int, int], float] = {}
        self.shots: list[Shot] = []  # MEASUREs in flight
        self.clouds: list[Cloud] = []  # DECOHERENCE clouds on the road
        self._clouds_dropped = 0
        self._place()

    def racer(self, car_id: str) -> Racer:
        return self._by_id[car_id]

    def hazards_for(self, car_id: str) -> list[tuple[float, float, str, bool]]:
        """The renderer's (z, x, kind, alive) for a car's own storm hazards: only that car
        sees them (none before its final lap)."""
        return [(h.z, h.x, h.kind, h.alive) for h in self._by_id[car_id].hazards]

    def shot_objects(self) -> list[tuple[float, float, str]]:
        """The renderer's (z, x, "shot") for every MEASURE in flight: on the way from its
        owner's car to its target's (the beam runs from the first to here)."""
        out = []
        for s in self.shots:
            a, b = self._by_id[s.owner].car, self._by_id[s.target].car
            f = s.progress
            out.append((a.z + (b.z - a.z) * f, a.x + (b.x - a.x) * f, "shot"))
        return out

    def deco_objects(self) -> list[tuple[float, float, str]]:
        """The renderer's (z, x, "deco") for every DECOHERENCE cloud, a lap either side too
        (a cloud is a place on the track, for a car on any lap)."""
        lap = self.lap_length
        return [(c.z + k * lap, c.x, "deco") for c in self.clouds for k in (-1, 0, 1)]

    def measure_target(self, car_id: str) -> Racer | None:
        """The car a MEASURE fired by this car now would home on: the nearest ahead in the
        race (not finished) within MEASURE_RANGE, or None."""
        me = self._by_id[car_id].car
        ahead = [(r.car.z - me.z, r) for r in self.racers
                 if r.car is not me and not r.finished
                 and 0 < r.car.z - me.z <= config.MEASURE_RANGE]
        return min(ahead, key=lambda a: a[0])[1] if ahead else None

    def obstacles(self, car_id: str, ahead: float) -> list[tuple[tuple, float, float, float]]:
        """What lies within `ahead` in front of this car to steer round: its own live storm
        hazards and every cloud, as (key, z, x, reach) by z. The key is the same for the
        same obstacle frame after frame (for the bots' memory)."""
        r = self._by_id[car_id]
        car = r.car
        out = []
        for i in range(r.next_hazard, len(r.hazards)):
            h = r.hazards[i]
            if h.z - car.z > ahead:
                break
            if h.alive and h.z >= car.z:
                out.append((("hazard", i), h.z, h.x, h.reach))
        for c in self.clouds:
            d = (c.z - car.z) % self.lap_length
            if d <= ahead:
                out.append((("cloud", c.id), car.z + d, c.x, c.reach))
        return sorted(out, key=lambda o: o[1])

    def car_objects(self) -> list[tuple[float, float, str]]:
        """The renderer's (z, x, kind) for every car."""
        return [(r.car.z, r.car.x, r.car.kind) for r in self.racers]

    def clone_objects(self) -> list[tuple[float, float, str]]:
        """The renderer's (z, x, "clone") for every SPLIT clone that is out."""
        return [(r.car.z, -r.car.x, "clone") for r in self.racers if r.split]

    def box_present(self, k: int, j: int) -> bool:
        """Whether box j of box line k is there (not taken, or respawned)."""
        back = self._box_back.get((k, j))
        return back is None or self.time >= back

    def box_objects(self) -> list[tuple[float, float, str]]:
        """The renderer's (z, x, "box") for every box that is there, lap after lap."""
        return [(z, x, "box") for z, k in self.box_lines
                for j, x in enumerate(self.track.boxes[k][1]) if self.box_present(k, j)]

    def box_index(self, z: float) -> int:
        """The index of the first box line beyond race distance z."""
        return next((i for i, (bz, _) in enumerate(self.box_lines) if bz > z),
                    len(self.box_lines))

    def roll_item(self, place: int, gates_left: bool = True) -> str:
        """A box's item for a car in this place, from the race's own item stream. With no
        gate row left (`gates_left` False) SPLIT and QEC are left out and the rest share
        their odds."""
        odds = config.ITEM_ODDS[max(1, min(len(config.ITEM_ODDS), place)) - 1]
        if not gates_left:
            odds = tuple(0 if item in config.GATE_ITEMS else w
                         for item, w in zip(config.ITEMS, odds))
        return self.rng.choices(config.ITEMS, weights=odds)[0]

    # --- A frame ----------------------------------------------------------------------------

    def update(self, dt: float, controls: Mapping[str, Controls]) -> list[Event]:
        """Step the race by dt. `controls` maps car ids to their input; a car without any
        drives straight on."""
        if self.over:
            return []
        self.time += dt
        events: list[Event] = []
        idle = Controls()
        for r in self.racers:
            r.blind_time = max(0.0, r.blind_time - dt)
            if r.blind_time < 1e-9:
                r.blind_time = 0.0
            c = controls.get(r.car.id, idle)
            if c.item and r.item is not None and not r.finished:
                self._use(r, events)
            r.car.update(dt, c.steer, c.brake, self.track.segment_at(r.car.z), c.pace)
            events += [Event(kind, r.car.id, value) for kind, value in r.car.cues]
        self._bumps(dt, events)
        self._shots(dt, events)
        self._place()  # boxes roll by the places as the cars are now
        for r in self.racers:
            self._warp(r, dt, events)
            self._rows(r, events)
            self._boxes(r, events)
            self._hazards(r, events)
            self._clouds(r, events)
            self._laps(r, events)
        for c in self.clouds:
            c.time -= dt
        self.clouds = [c for c in self.clouds if c.time > 1e-9]
        self._place()
        if all(r.finished for r in self.racers
               if r.player or self.finish_all or not self.players):
            self.over = True
        return events

    def _use(self, r: Racer, events: list[Event]) -> None:
        item, r.item = r.item, None
        car = r.car
        events.append(Event("item", car.id, item))
        if item == "SPLIT":
            r.split_rows = config.SPLIT_ROWS
        elif item == "QEC":
            r.circuit.qec()
        elif item == "MEASURE":
            target = self.measure_target(car.id)
            if target is None:
                events.append(Event("fizzle", car.id))
            else:
                self.shots.append(Shot(car.id, target.car.id))
        elif item == "TUNNEL":
            car.tunnel(config.TUNNEL_TIME)
        elif item == "DECOHERENCE":
            x = max(-config.HAZARD_X_MAX, min(config.HAZARD_X_MAX, car.x))
            self.clouds.append(Cloud(self._clouds_dropped, car.z - config.DECO_BEHIND, x,
                                     car.id, config.DECO_TIME))
            self._clouds_dropped += 1

    def _shots(self, dt: float, events: list[Event]) -> None:
        """Fly the MEASUREs; one that has flown its time hits its target."""
        flying = []
        for shot in self.shots:
            shot.t += dt
            if shot.t < config.MEASURE_FLIGHT - 1e-9:
                flying.append(shot)
                continue
            target = self._by_id[shot.target]
            if target.finished:
                continue  # over the line first: nothing to collapse
            if target.check_wait > 0:
                flying.append(shot)  # frozen on the CIRCUIT CHECK: it waits for the freeze
                continue
            if target.car.tunnelling:
                events.append(Event("immune", target.car.id, "shot"))
                continue
            target.car.clear_boosts()
            target.car.spin()
            target.circuit.streak = 0
            events.append(Event("collapse", target.car.id, shot.owner))
        self.shots = flying

    def _hazards(self, r: Racer, events: list[Event]) -> None:
        """The car's own storm hazards it passed this frame."""
        car = r.car
        while r.next_hazard < len(r.hazards) and car.z >= r.hazards[r.next_hazard].z:
            h = r.hazards[r.next_hazard]
            r.next_hazard += 1
            if not h.alive or h.z < car.prev_z or r.finished:
                continue
            if abs(_x_at(car, h.z) - h.x) >= h.reach:
                continue
            if car.tunnelling:
                events.append(Event("immune", car.id, h.kind))
                continue
            h.alive = False
            if h.kind == "cloud":
                self._cloud_hit(car)
            else:
                car.spin()
                r.circuit.streak = 0
            events.append(Event("hazard", car.id, h.kind))

    @staticmethod
    def _cloud_hit(car: Car) -> None:
        car.clear_boosts()
        car.slow(config.CLOUD_CAP, config.CLOUD_TIME)

    def _clouds(self, r: Racer, events: list[Event]) -> None:
        """The DECOHERENCE clouds the car drove through this frame."""
        car = r.car
        step = car.z - car.prev_z
        if step <= 0 or r.finished or not self.clouds:
            return
        for c in list(self.clouds):
            d = (c.z - car.prev_z) % self.lap_length  # where it is ahead of the frame's start
            if not 0 < d <= step or abs(_x_at(car, car.prev_z + d) - c.x) >= c.reach:
                continue
            if car.tunnelling:
                events.append(Event("immune", car.id, "deco"))
                continue
            self.clouds.remove(c)
            if r.lap >= config.LAPS:
                self._cloud_hit(car)
            else:
                car.clear_boosts()
                car.end_drift()
                r.blind_time = config.BLIND_TIME
            events.append(Event("decohered", car.id, c.owner))

    def _boxes(self, r: Racer, events: list[Event]) -> None:
        car = r.car
        while r.next_box < len(self.box_lines) and car.z >= self.box_lines[r.next_box][0]:
            z, k = self.box_lines[r.next_box]
            r.next_box += 1
            if z < car.prev_z:
                continue  # put past it (a test's teleport), not driven through it
            x = _x_at(car, z)
            for j, offset in enumerate(self.track.boxes[k][1]):
                if abs(x - offset) <= config.BOX_REACH and self.box_present(k, j):
                    self._box_back[(k, j)] = self.time + config.BOX_RESPAWN
                    if r.item is None:
                        rows_left = r.next_row < len(self.rows)
                        r.item = (self.roll_item(r.place) if rows_left
                                  else self.roll_item(r.place, gates_left=False))
                        events.append(Event("box", car.id, r.item))
                    else:
                        events.append(Event("box_full", car.id, r.item))
                    break

    def _bumps(self, dt: float, events: list[Event]) -> None:
        for key in list(self._cooldown):
            self._cooldown[key] -= dt
            if self._cooldown[key] <= 0:
                del self._cooldown[key]
        cars = [r.car for r in self.racers]
        for i, a in enumerate(cars):
            for j in range(i + 1, len(cars)):
                b = cars[j]
                if a.tunnelling or b.tunnelling:
                    continue  # tunnelling through
                if bump(a, b, self.lap_length) and (i, j) not in self._cooldown:
                    self._cooldown[(i, j)] = config.BUMP_COOLDOWN
                    events.append(Event("bump", a.id, b.id))
                    events.append(Event("bump", b.id, a.id))

    def _rows(self, r: Racer, events: list[Event]) -> None:
        car = r.car
        while r.next_row < len(self.rows) and car.z >= self.rows[r.next_row].z:
            row = self.rows[r.next_row]
            x = _x_at(car, row.z)
            arch = arch_at(row, x)
            if r.split_rows > 0:
                clone = arch_at(row, -x)
                if clone is not None and (arch is None or (clone.right and not arch.right)):
                    arch = clone
                r.split_rows -= 1
                if r.split_rows == 0:
                    events.append(Event("split_end", car.id))
            right = r.circuit.take(row.slot, arch.gate if arch else None)
            if right:
                car.give_boost(*config.streak_boost(r.circuit.streak))
                events.append(Event("right", car.id, r.circuit.streak))
            else:
                events.append(Event("wrong" if arch else "miss", car.id, row.slot))
            r.next_row += 1
            if r.next_row == len(self.rows):  # no gate left: no second gate to take
                ended = r.split_rows > 0 or r.item == "SPLIT"
                r.split_rows = 0
                if r.item == "SPLIT":
                    r.item = None
                if ended:
                    events.append(Event("split_end", car.id))

    def _laps(self, r: Racer, events: list[Event]) -> None:
        car = r.car
        while not r.finished and car.z >= (r.laps + 1) * self.lap_length:
            r.laps += 1
            if r.finished:
                r.finish_time = self.time
                self.finish_order.append(car.id)
                events.append(Event("finish", car.id, len(self.finish_order)))
                r.item = None  # no item after the line: a QEC would change the results
                if r.split_rows > 0:
                    r.split_rows = 0
                    events.append(Event("split_end", car.id))
                continue
            events.append(Event("lap", car.id, r.lap))
            if r.lap == config.LAPS:  # laps only grow, so this comes once per car
                r.check = circuit.hamming(r.circuit.slots, self.target, config.CHECK_SLOTS)
                r.check_boost = config.check_boost(r.check)
                r.check_wait = config.CHECK_FREEZE
                events.append(Event("check", car.id, r.check))
                rng = random.Random(f"{self.seed}:storm:{car.id}")
                start = (config.LAPS - 1) * self.lap_length
                r.hazards = storm.storm(rng, r.check_right, start, start + self.lap_length,
                                        self.track)
                r.next_hazard = 0

    def _warp(self, r: Racer, dt: float, events: list[Event]) -> None:
        """The check's boost, once the freeze after the crossing is over."""
        if r.check_wait <= 0:
            return
        r.check_wait -= dt
        if r.check_wait > 1e-9:
            return
        r.check_wait = 0.0
        if r.check_boost and not r.check_boost_none and r.car.give_boost(*r.check_boost):
            r.warp_time = self.time
            events.append(Event("warp", r.car.id, r.check_boost))

    # --- Places -----------------------------------------------------------------------------

    def places(self) -> list[str]:
        """Car ids from first to last. Ties keep the order of `racers` (players first)."""
        done = [self._by_id[i] for i in self.finish_order]
        rest = sorted((r for r in self.racers if not r.finished),
                      key=lambda r: (-r.laps, -r.car.z))
        return [r.car.id for r in done + rest]

    def results(self) -> list[str]:
        """The final order once the race is over (the current order before that)."""
        return self.places()

    def _place(self) -> None:
        for n, car_id in enumerate(self.places(), 1):
            self._by_id[car_id].place = n
