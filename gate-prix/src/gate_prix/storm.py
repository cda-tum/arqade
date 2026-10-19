"""The noise storm: a racer's own decoherence hazards on the final lap, set by its check.

Pure Python, no pygame. `storm()` lays out one racer's hazards over the final lap, from its
CIRCUIT CHECK (how many gates it got right) and a seeded RNG of its own:

- **How many:** STORM_BASE + STORM_PER_WRONG per wrong gate, at most STORM_MAX (a perfect
  circuit gets 4, 8/16 gets 20).
- **Where:** in waves spread evenly from STORM_START seconds (at top speed) after the line
  to STORM_END seconds before the finish, each wave jittered within its stretch. Past
  STORM_PAIRS_FROM hazards some waves are a pair, one either side of the clear line.
- **The clear line:** a lane STORM_GAP wide (more than a car) that no hazard's edge enters.
  Its centre wanders from wave to wave, never further than half stick (STORM_LANE_STEER),
  less what the curves on the way take to hold, can follow over the distance between them
  (in a curve that takes half stick or more, it stays put), and stays within STORM_LANE_MAX
  of the centre. No wave sits in a sharp curve, as no gate row does.
- **Each hazard** is a static cloud (wide and soft) or a bit-flip mine (small and sharp,
  STORM_MINES of them), all of it on the road, sat near the racing line so that it is in
  the way, but pushed out of the clear line.

A car hits a hazard when its body touches it as it passes the hazard's z: its centre within
`reach` (the hazard's radius and half a car).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from gate_prix import config

TOP = config.TOP_SPEED
PAIR_STAGGER = 3 * config.CAR_LENGTH  # the half of a pair that had to go on the other side


@dataclass(slots=True)
class Hazard:
    z: float  # race distance
    x: float  # its centre, in road half-widths
    kind: str  # "cloud" or "mine"
    alive: bool = True  # until a car drives into it

    @property
    def size(self) -> float:
        """Its radius as drawn, in road half-widths."""
        return config.HAZARD_SIZE[self.kind]

    @property
    def reach(self) -> float:
        """How near its centre a car's centre must pass to touch it."""
        return self.size + config.CAR_WIDTH / 2


def count(right: int) -> int:
    """How many hazards a racer with `right` of the check's gates right meets."""
    wrong = config.CHECK_SLOTS - max(0, min(config.CHECK_SLOTS, right))
    return min(config.STORM_MAX, config.STORM_BASE + config.STORM_PER_WRONG * wrong)


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _limit(size: float) -> float:
    """How far from the centre line a hazard's centre may be: all of it on the road."""
    return min(config.HAZARD_X_MAX, 1.0 - size)


def _beside(lane: float, size: float, side: int, extra: float = 0.0) -> float | None:
    """The centre of a hazard of this size just outside the lane on `side`, `extra`
    further out, or None when that is off the road."""
    x = lane + side * (config.STORM_GAP / 2 + size + extra)
    return x if abs(x) <= _limit(size) else None


def _lone(rng: random.Random, lane: float, size: float, near: float) -> float:
    """A lone hazard's centre: near `near`, pushed out of the lane. One side of the lane
    always has room (STORM_LANE_MAX keeps the lane off the road's edges)."""
    x = _clamp(near + rng.uniform(-0.3, 0.3), -_limit(size), _limit(size))
    if abs(x - lane) < config.STORM_GAP / 2 + size:
        side = (1 if x > lane else -1) if x != lane else rng.choice((-1, 1))
        x = _beside(lane, size, side)
        if x is None:
            x = _beside(lane, size, -side)
    assert x is not None  # the lane is never so far out that neither side has room
    return x


def _place(rng: random.Random, lane: float, kinds: list[str], near: float):
    """(centre, dz) for one wave's hazards, none of them in the lane: a lone hazard near
    `near`, a pair one either side of the lane. Where only one side has room for its half
    of the pair, that half goes on the other side a little further on (PAIR_STAGGER)."""
    sizes = [config.HAZARD_SIZE[k] for k in kinds]
    if len(kinds) == 1:
        return [(_lone(rng, lane, sizes[0], near), 0.0)]
    out = []
    for side, size in zip((-1, 1), sizes):
        x = _beside(lane, size, side, rng.uniform(0, 0.15))
        if x is None:
            x = _beside(lane, size, side)
        out.append((x, 0.0) if x is not None else (_beside(lane, size, -side), PAIR_STAGGER))
    return out


def _hold(course, z: float) -> float:
    """The share of full stick that holds a car against the curve at z, at top speed."""
    return config.CURVE_PUSH * abs(course.segment_at(z).curve) / config.STEER_RATE


def _calm(course, start: float, span: float, rng: random.Random) -> float:
    """A wave's z in its stretch [start, start + span): jittered about the middle, but never
    in a sharp curve (as no gate row is) when the stretch has room outside one."""
    for _ in range(12):
        z = start + span * rng.uniform(0.25, 0.75)
        if abs(course.segment_at(z).curve) <= config.SHARP_CURVE:
            return z
    calm = [start + span * f / 40 for f in range(4, 37)
            if abs(course.segment_at(start + span * f / 40).curve) <= config.SHARP_CURVE]
    return rng.choice(calm) if calm else start + span / 2


def storm(rng: random.Random, right: int, lap_start: float, lap_end: float,
          course) -> list[Hazard]:
    """One racer's hazards over the final lap (race distances lap_start to lap_end), sorted
    by z. `course` is the track, for the racing line."""
    n = count(right)
    pairs = max(0, (n - config.STORM_PAIRS_FROM) // 2)
    waves = n - pairs
    paired = set(rng.sample(range(waves), pairs))
    z0 = lap_start + config.STORM_START * TOP
    z1 = lap_end - config.STORM_END * TOP
    span = (z1 - z0) / waves
    lim = config.STORM_LANE_MAX
    lane = _clamp(course.segment_at(z0).line + rng.uniform(-0.3, 0.3), -lim, lim)
    z_prev = z0
    hazards: list[Hazard] = []
    for k in range(waves):
        z = _calm(course, z0 + span * k, span, rng)
        hold = max(_hold(course, zz) for zz in (z_prev, (z_prev + z) / 2, z))
        budget = max(0.0, config.STORM_LANE_STEER - hold)
        move = budget * config.STEER_RATE * (z - z_prev) / TOP
        lane = _clamp(lane + rng.uniform(-move, move), -lim, lim)
        z_prev = z
        size = 2 if k in paired else 1
        kinds = ["mine" if rng.random() < config.STORM_MINES else "cloud" for _ in range(size)]
        for kind, (x, dz) in zip(kinds, _place(rng, lane, kinds, course.segment_at(z).line)):
            hazards.append(Hazard(z + dz, round(x, 6), kind))
    hazards.sort(key=lambda h: h.z)
    return hazards
