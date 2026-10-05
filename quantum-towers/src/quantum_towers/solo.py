"""Solo time trial, pure logic: the equal-difficulty tower generator and a
pausable run timer. No pygame, no I/O.

Every solo run is a fresh random tower, but its total of minimum presses is
always the same number (config.SOLO_TOTAL_PRESSES), so fastest-clear times
are comparable without anyone memorising a tower.
"""

from __future__ import annotations

import math
import random

from quantum_towers import config
from quantum_towers.quantum import State, zero_state
from quantum_towers.search import minimum_steps
from quantum_towers.targets import MAX_WALK_LENGTH, generate_target

# A target is a walk of at most MAX_WALK_LENGTH actions from its predecessor, so
# no floor's true minimum can exceed that; and a floor is never a no-op, so none
# is below 1. These bound what is still reachable mid-build.
MIN_FLOOR_STEPS = 1
MAX_FLOOR_STEPS = MAX_WALK_LENGTH

_REDRAWS_PER_FLOOR = 40  # candidates tried for one floor before the attempt restarts
_MAX_ATTEMPTS = 10_000

# Only 16 states are reachable, so there are only a few hundred (prev, target)
# pairs. The BFS result is a pure function of the pair; cache it.
_steps_cache: dict[tuple[tuple[float, ...], tuple[float, ...]], int] = {}


def _key(state: State) -> tuple[float, ...]:
    return tuple(round(part, 6) + 0.0 for c in state for part in (c.real, c.imag))


def _steps(prev: State, target: State) -> int:
    key = (_key(prev), _key(target))
    steps = _steps_cache.get(key)
    if steps is None:
        steps = minimum_steps(prev, target, config.SEARCH_MAX_DEPTH)
        if steps is None:
            raise ValueError("target not reachable within the search depth")
        _steps_cache[key] = steps
    return steps


def minimum_total(targets: list[State]) -> int:
    """Sum over floors of the true minimum presses from the previous floor's
    target (|0> for the first floor) to this one's."""
    previous = zero_state()
    total = 0
    for target in targets:
        total += _steps(previous, target)
        previous = target
    return total


def equal_difficulty_tower(
    rng: random.Random, floors: int, total: int, extra: int = 2
) -> list[State]:
    """`floors + extra` targets, each reachable from the one before, whose first
    `floors` have minimum_total == total. The extra targets are unconstrained
    (the top floor still needs a "next target" to look up). Deterministic per
    rng.

    Built floor by floor from targets.generate_target. A candidate is redrawn
    when it would leave a remaining total that the remaining floors cannot hit
    (each floor costs between MIN_FLOOR_STEPS and MAX_FLOOR_STEPS), and the
    attempt restarts if a floor cannot be filled."""
    if not floors * MIN_FLOOR_STEPS <= total <= floors * MAX_FLOOR_STEPS:
        raise ValueError(f"{floors} floors cannot total {total} minimum presses")

    for _ in range(_MAX_ATTEMPTS):
        tower = _try_build(rng, floors, total)
        if tower is not None:
            previous = tower[-1] if tower else zero_state()
            for _ in range(extra):
                previous = generate_target(rng, previous)
                tower.append(previous)
            return tower
    raise RuntimeError("could not build an equal-difficulty tower")


def _try_build(rng: random.Random, floors: int, total: int) -> list[State] | None:
    tower: list[State] = []
    previous = zero_state()
    remaining = total
    for floor in range(floors):
        left_after = floors - floor - 1
        low = left_after * MIN_FLOOR_STEPS
        high = left_after * MAX_FLOOR_STEPS
        for _ in range(_REDRAWS_PER_FLOOR):
            candidate = generate_target(rng, previous)
            steps = _steps(previous, candidate)
            if low <= remaining - steps <= high:
                break
        else:
            return None
        tower.append(candidate)
        previous = candidate
        remaining -= steps
    return tower if remaining == 0 else None


class Timer:
    """The run clock. Counts up with update(dt); frozen while `paused`."""

    def __init__(self) -> None:
        self.seconds = 0.0
        self.paused = False

    def update(self, dt: float) -> None:
        if not self.paused:
            self.seconds += dt

    def format(self) -> str:
        return format_time(self.seconds)


def format_time(seconds: float) -> str:
    """m:ss.cc, truncated to hundredths."""
    hundredths = max(0, math.floor(seconds * 100 + 1e-6))
    minutes, hundredths = divmod(hundredths, 6000)
    return f"{minutes}:{hundredths // 100:02d}.{hundredths % 100:02d}"
