"""The race: six cars on THE FRIDGE, their circuits, the gate rows, laps, the CIRCUIT CHECK,
places and the finish.

Pure Python, no pygame. `Race.update(dt, controls)` steps every car, resolves bumps and the
rows each car crossed, counts laps, and returns the frame's cues as `Event`s:

| kind | value |
|---|---|
| "right" | the car's streak after this gate |
| "wrong", "miss" | the slot that was filled wrong or left empty |
| "lap" | the lap the car has just started (2, 3) |
| "check" | the CIRCUIT CHECK's Hamming distance, at the start of the final lap |
| "finish" | the car's finishing place |
| "bump" | the other car (each bump cues both cars) |

Task 4 adds "box" and "item".

Rules decided here:
- A row is crossed when a car's z passes the row's z. The car's x at that moment (between
  where the frame started and ended) picks the arch: the one whose centre is within
  ARCH_HALF_WIDTH of it, or none. Rows are crossed strictly in order, so row k of the race is
  always the car's slot k.
- A right gate gives `streak_boost(streak)`; the CIRCUIT CHECK gives
  `check_boost(distance)`, once per car. Boosts never cut each other short: the car runs at
  the strongest one running, and a weaker, longer one carries on after it (`Car.give_boost`),
  so a right gate never slows a car down.
- Places: finished cars in the order they finished, then the rest by laps and distance (the
  order of `racers`, players first, breaks a tie). The race is over once every player has finished; CPU cars still
  racing are placed where they are. An over race no longer changes.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from typing import NamedTuple

from gate_prix import circuit, config, track
from gate_prix.car import Car, Controls, bump

CPU_COLOURS = ("green", "silver", "gold", "violet", "lime")


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
        self.finish_time: float | None = None
        self.place = 0

    @property
    def lap(self) -> int:
        """The lap it is on, 1 to LAPS (LAPS once finished)."""
        return min(self.laps + 1, config.LAPS)

    @property
    def finished(self) -> bool:
        return self.laps >= config.LAPS


def arch_at(row: track.GateRow, x: float) -> track.Arch | None:
    """The arch a car at x goes through, if any: the nearest within an arch's half-width."""
    best = None
    for arch in row.arches:
        d = abs(x - arch.offset)
        if d <= config.ARCH_HALF_WIDTH and (best is None or d < abs(x - best.offset)):
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
                 course: track.Track | None = None) -> None:
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
            r.car.update(dt, c.steer, c.brake, self.track.segment_at(r.car.z))
        self._bumps(dt, events)
        for r in self.racers:
            self._rows(r, events)
            self._laps(r, events)
        self._place()
        if all(r.finished for r in self.racers if r.player):
            self.over = True
        return events

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
            span = car.z - car.prev_z
            f = (row.z - car.prev_z) / span if span > 0 else 1.0
            f = min(1.0, max(0.0, f))
            arch = arch_at(row, car.prev_x + (car.x - car.prev_x) * f)
            right = r.circuit.take(row.slot, arch.gate if arch else None)
            if right:
                car.give_boost(*config.streak_boost(r.circuit.streak))
                events.append(Event("right", car.id, r.circuit.streak))
            else:
                events.append(Event("wrong" if arch else "miss", car.id, row.slot))
            r.next_row += 1

    def _laps(self, r: Racer, events: list[Event]) -> None:
        car = r.car
        while not r.finished and car.z >= (r.laps + 1) * self.lap_length:
            r.laps += 1
            if r.finished:
                r.finish_time = self.time
                self.finish_order.append(car.id)
                events.append(Event("finish", car.id, len(self.finish_order)))
                continue
            events.append(Event("lap", car.id, r.lap))
            if r.lap == config.LAPS:  # laps only grow, so this comes once per car
                r.check = circuit.hamming(r.circuit.slots, self.target, config.CHECK_SLOTS)
                r.check_boost = config.check_boost(r.check)
                car.give_boost(*r.check_boost)
                events.append(Event("check", car.id, r.check))

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
