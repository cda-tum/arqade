"""The roster: one racer from each arqade game that has a character to give.
Pure (no pygame), so it is tested.

Every racer has five ratings from 1 to 5 that add up to 15, so none is
better at everything: a heavy, fast racer pays for it in acceleration and
handling. stats() turns the ratings into the physics the race uses:

- SPEED: top speed.
- ACCEL: how fast it gets there.
- GRIP: how fast it can take a corner before it drifts (and leaks).
- WEIGHT: in bumps and pushes, the heavier racer gives less and can shove
  a lighter one; a light one bounces off a heavy one.
- HANDLING: how quickly it changes wires.

The models are in voxels.py, under the same key.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from qircuit import config

RATINGS = ("SPEED", "ACCEL", "GRIP", "WEIGHT", "HANDLING")
BUDGET = 15


@dataclass(frozen=True)
class Racer:
    key: str
    name: str
    game: str  # the arqade game it comes from
    speed: int
    accel: int
    grip: int
    weight: int
    handling: int

    @property
    def ratings(self) -> tuple[int, ...]:
        return (self.speed, self.accel, self.grip, self.weight, self.handling)

    def stats(self) -> config.CarStats:
        car = config.CAR
        return replace(
            car,
            max_speed=car.max_speed + config.STAT_SPEED * (self.speed - 3),
            accel=car.accel * (1 + config.STAT_ACCEL * (self.accel - 3)),
            grip=car.grip * (1 + config.STAT_GRIP * (self.grip - 3)),
            mass=1.0 + config.STAT_MASS * (self.weight - 3),
            switch_rate=car.switch_rate + config.STAT_HANDLING * (self.handling - 3),
        )


ROSTER = (
    Racer("chandelier", "CHANDELIER", "SUPERCONDUCTOR", speed=5, accel=1, grip=3, weight=4, handling=2),
    Racer("ion", "ION", "ION SURFER", speed=3, accel=4, grip=3, weight=1, handling=4),
    Racer("jelly", "PAULI JELLY", "PAULI INVADERS", speed=2, accel=4, grip=4, weight=2, handling=3),
    Racer("colorcode", "COLOR CODE", "PAULI INVADERS", speed=3, accel=3, grip=3, weight=3, handling=3),
    Racer("cycle", "LIGHT CYCLE", "QURVES", speed=5, accel=2, grip=2, weight=2, handling=4),
    Racer("paddle", "PADDLES", "QUANTUM PONG", speed=3, accel=2, grip=4, weight=3, handling=3),
    Racer("chef", "CHEF", "OVERQUQED", speed=2, accel=5, grip=3, weight=3, handling=2),
    Racer("rook", "TOWER", "QLIMBERS", speed=3, accel=3, grip=3, weight=5, handling=1),
    Racer("photon", "PHOTON", "QLINKO", speed=4, accel=4, grip=2, weight=1, handling=4),
)
BY_KEY = {r.key: r for r in ROSTER}
