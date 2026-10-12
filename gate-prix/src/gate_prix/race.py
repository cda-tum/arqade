"""The race: six cars on THE FRIDGE, their circuits, the gate rows, laps, the CIRCUIT CHECK,
places and the finish.

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
| "box" | the item a box gave ("SPLIT", "QEC"), or None for an empty box |
| "box_full" | the item still held: the box broke but gave nothing new |
| "item" | the item the car has just used |
| "split_end" | None: the car's clone is gone |

Rules decided here:
- The target has SLOTS (16) gates, one per gate row, and the rows stand on laps 1 and 2
  only: the final lap is a gate-free sprint (item boxes stay on every lap).
- A row is crossed when a car's z passes the row's z. The car's x at that moment (between
  where the frame started and ended) picks the arch: the nearest whose centre is within its
  `half_width` of it (ARCH_HALF_WIDTH for the right arch, the smaller DECOY_HALF_WIDTH for a
  decoy: each as wide as it is drawn), or none. Rows are crossed strictly in order, so row k
  of the race is always the car's slot k.
- A right gate gives `streak_boost(streak)`. The CIRCUIT CHECK, as a car crosses into the
  final lap, compares all 16 slots with the target, once per car (the CPUs too, by their
  own circuits). Its `check_boost(distance)` starts CHECK_FREEZE seconds later (cued
  "warp"): meanwhile a player's view is frozen on the comparison (the match's and the
  renderer's business) while the car drives on, losing no distance. No boost (all 16
  wrong), no warp. Boosts never cut each other short: the car runs at
  the strongest one running, and a weaker, longer one carries on after it (`Car.give_boost`),
  so a right gate never slows a car down.
- Places: finished cars in the order they finished, then the rest by laps and distance (the
  order of `racers`, players first, breaks a tie). The race is over once every player has finished; CPU cars still
  racing are placed where they are. An over race no longer changes. `finish_all` races on
  until every car has finished instead (the attract race, and the tests).
- Item boxes stand at the track's box lines, lap after lap; each box is one object, so a box
  taken on lap 1 is also gone for a car arriving on lap 2, until it respawns BOX_RESPAWN
  seconds later. A car crossing a box line takes the box within BOX_REACH of its x (the x
  is interpolated, as for the rows; a line the car was put past without driving through it
  doesn't count). The box breaks even when the car already holds an item;
  it only gives one (rolled by the car's place, `ITEM_ODDS`) to a car holding none, and
  cues "box_full" for a car that already holds one. Past its last gate row a box never
  gives a SPLIT (there is no second gate left to take): QEC or nothing.
- `Controls.item` uses the held item, before the frame's rows are crossed:
  - SPLIT: for the next SPLIT_ROWS rows a clone drives at -x. A row is right if the car or
    the clone takes the right arch; otherwise wrong if either takes a wrong one (the car's
    gate first), otherwise missed. Using another SPLIT starts the count again. The clone
    ends after its rows, or at the finish.
  - QEC: `Circuit.qec()`, repairing the most recent mistake (not the streak). With no
    mistake it does nothing, but the item is still used.
  - A SPLIT is over with the car's last gate row: a clone still out goes (cued
    "split_end") and a SPLIT still held is dropped, as no gate is left to take.
  A car that has finished can't use an item: an item still held at the line is dropped.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from typing import NamedTuple

from gate_prix import circuit, config, track
from gate_prix.car import Car, Controls, bump

CPU_COLOURS = tuple(config.CPU_COLORS)


class Event(NamedTuple):
    kind: str
    car: str  # the car's id
    value: object = None


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


def grid(players: int) -> list[tuple[float, float]]:
    """The (z, x) of each car on the grid, players first. Two lanes, the right lane half a
    row back; the players start side by side in the back row, P1 on the left and P2 on the
    right, so that neither starts ahead."""
    spots = []
    for k in range(config.CARS):
        row, lane = divmod(k, 2)
        z = -(config.GRID_FIRST + row * config.GRID_GAP + lane * config.GRID_GAP / 2)
        spots.append((z, config.GRID_LANES[lane]))
    back = config.CARS - 2
    rest = [s for k, s in enumerate(spots) if not back <= k < back + players]
    mine = [(spots[back][0], config.GRID_LANES[i]) for i in range(players)]
    return mine + rest


class Race:
    """A race of LAPS laps of the track for 1 or 2 players and the CPU racers."""

    def __init__(self, seed: int, players: int, rng: random.Random | None = None,
                 course: track.Track | None = None, finish_all: bool = False) -> None:
        if players not in (1, 2):
            raise ValueError(f"a race has 1 or 2 players, not {players}")
        self.seed = seed
        self.players = players
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
        ids = [f"p{i + 1}" for i in range(players)]
        ids += list(CPU_COLOURS[: config.CARS - players])
        self.racers: list[Racer] = []
        for i, (car_id, (z, x)) in enumerate(zip(ids, grid(players))):
            car = Car(car_id, car_id, x)
            car.z = car.prev_z = z
            self.racers.append(Racer(car, self.target, i < players))
        self._by_id = {r.car.id: r for r in self.racers}
        self.time = 0.0
        self.finish_order: list[str] = []
        self.over = False
        self._cooldown: dict[tuple[int, int], float] = {}
        self._place()

    def racer(self, car_id: str) -> Racer:
        return self._by_id[car_id]

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

    def roll_item(self, place: int, split: bool = True) -> str | None:
        """A box's item for a car in this place, from the race's own item stream. With
        `split` False (no gate row left) a SPLIT's share is dropped: QEC or nothing."""
        odds = config.ITEM_ODDS[max(1, min(len(config.ITEM_ODDS), place)) - 1]
        if not split:
            odds = (0, *odds[1:])
        return self.rng.choices(config.ITEMS + (None,), weights=odds)[0]

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
            c = controls.get(r.car.id, idle)
            if c.item and r.item is not None and not r.finished:
                self._use(r, events)
            r.car.update(dt, c.steer, c.brake, self.track.segment_at(r.car.z), c.pace)
        self._bumps(dt, events)
        self._place()  # boxes roll by the places as the cars are now
        for r in self.racers:
            self._warp(r, dt, events)
            self._rows(r, events)
            self._boxes(r, events)
            self._laps(r, events)
        self._place()
        if all(r.finished for r in self.racers if r.player or self.finish_all):
            self.over = True
        return events

    def _use(self, r: Racer, events: list[Event]) -> None:
        item, r.item = r.item, None
        if item == "SPLIT":
            r.split_rows = config.SPLIT_ROWS
        elif item == "QEC":
            r.circuit.qec()
        events.append(Event("item", r.car.id, item))

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
                                  else self.roll_item(r.place, split=False))
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
                if r.split_rows > 0:
                    r.split_rows = 0
                    events.append(Event("split_end", car.id))
                if r.item == "SPLIT":
                    r.item = None

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

    def _warp(self, r: Racer, dt: float, events: list[Event]) -> None:
        """The check's boost, once the freeze after the crossing is over."""
        if r.check_wait <= 0:
            return
        r.check_wait -= dt
        if r.check_wait > 1e-9:
            return
        r.check_wait = 0.0
        if r.check_boost and r.car.give_boost(*r.check_boost):
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
