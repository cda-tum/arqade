"""Gate pickups: spawning and deterministic per-ball effects.

Gates never expire on their own -- they stay until a ball touches them -- and
never overlap each other. Each one is announced GATE_WARNING_SECONDS before it
appears: it is already in the list, at its final spot, but its `spawned_at`
lies in the future, and until then balls pass straight through it (the game
draws it as a dashed outline). The spawn rate and the on-screen cap both ramp
up over a match (`spawn_interval`, `gate_cap`).

No probability: each gate applies a fixed transform to whichever ball touches
it, consuming the gate. H is the only one that changes the ball count -- it
splits one ball into two (one keeps going, one reverses horizontal direction)
and is a no-op past MAX_BALLS_ON_SCREEN (the gate is not consumed, in case
the count drops again later and it becomes touchable again).

Randomness is injected via a `random.Random` instance so spawn placement stays
deterministic and testable.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from quantum_pong.config import (
    GATE_CAP_STEP_SECONDS,
    GATE_MIN_GAP,
    GATE_RADIUS,
    GATE_SPAWN_CANDIDATES,
    GATE_SPAWN_INTERVAL,
    GATE_SPAWN_INTERVAL_MIN,
    GATE_SPAWN_MARGIN_X,
    GATE_SPAWN_MARGIN_Y,
    GATE_SPAWN_RAMP_SECONDS,
    GATE_WARNING_SECONDS,
    GATE_WEIGHTS,
    INTERNAL_HEIGHT,
    INTERNAL_WIDTH,
    MAX_BALLS_ON_SCREEN,
    MAX_GATES_ON_SCREEN,
    MAX_GATES_ON_SCREEN_LATE,
)
from quantum_pong.pong import Ball

# Bounded sampling budget for finding GATE_SPAWN_CANDIDATES non-overlapping spots.
_POSITION_ATTEMPTS = 50


@dataclass(frozen=True)
class Gate:
    kind: str
    x: float
    y: float
    spawned_at: float  # when it appears; announced (dashed, inert) before that


def is_live(gate: Gate, now: float) -> bool:
    """Whether `gate` has appeared yet -- before that it is only announced."""
    return now >= gate.spawned_at


def spawn_interval(match_time: float) -> float:
    """Seconds between spawn attempts, `match_time` seconds into a match:
    shrinks linearly from GATE_SPAWN_INTERVAL to GATE_SPAWN_INTERVAL_MIN."""
    t = max(0.0, min(1.0, match_time / GATE_SPAWN_RAMP_SECONDS))
    return GATE_SPAWN_INTERVAL + t * (GATE_SPAWN_INTERVAL_MIN - GATE_SPAWN_INTERVAL)


def gate_cap(match_time: float) -> int:
    """How many gates (announced ones included) may be on the field: one
    more every GATE_CAP_STEP_SECONDS, up to MAX_GATES_ON_SCREEN_LATE."""
    extra = int(max(0.0, match_time) // GATE_CAP_STEP_SECONDS)
    return min(MAX_GATES_ON_SCREEN + extra, MAX_GATES_ON_SCREEN_LATE)


def _pick_kind(rng: random.Random, weights: dict[str, int]) -> str:
    kinds = list(weights.keys())
    return rng.choices(kinds, weights=[weights[k] for k in kinds])[0]


def _overlaps(x: float, y: float, gate: Gate) -> bool:
    """Whether a gate square centered at (x, y) would overlap `gate`'s square
    or come within GATE_MIN_GAP of it. Gates are axis-aligned squares, so this
    is a Chebyshev (max-axis) distance check, not a circular one."""
    min_center_distance = 2 * GATE_RADIUS + GATE_MIN_GAP
    return max(abs(x - gate.x), abs(y - gate.y)) < min_center_distance


def _pick_position(rng: random.Random, existing_gates) -> tuple[float, float] | None:
    """A random non-overlapping spot in the spawn area, biased away from the
    existing gates: sample up to GATE_SPAWN_CANDIDATES valid spots and keep the
    one whose nearest existing gate is farthest away (best-candidate sampling).
    Returns None if no valid spot turned up -- the caller skips the spawn."""
    best: tuple[float, float] | None = None
    best_score = -1.0
    found = 0
    for _ in range(_POSITION_ATTEMPTS):
        x = rng.uniform(GATE_SPAWN_MARGIN_X, INTERNAL_WIDTH - GATE_SPAWN_MARGIN_X)
        y = rng.uniform(GATE_SPAWN_MARGIN_Y, INTERNAL_HEIGHT - GATE_SPAWN_MARGIN_Y)
        if any(_overlaps(x, y, g) for g in existing_gates):
            continue
        score = min((math.hypot(x - g.x, y - g.y) for g in existing_gates), default=0.0)
        if score > best_score:
            best, best_score = (x, y), score
        found += 1
        if found >= GATE_SPAWN_CANDIDATES:
            break
    return best


def spawn_gate(
    rng: random.Random,
    now: float,
    existing_gates=(),
    weights: dict[str, int] | None = None,
) -> Gate | None:
    """A gate at a random spot in the middle of the field, away from the
    paddles and spread out from (never overlapping) the gates already there.
    None if the field has no room left for one."""
    position = _pick_position(rng, existing_gates)
    if position is None:
        return None
    x, y = position
    return Gate(
        kind=_pick_kind(rng, weights if weights is not None else GATE_WEIGHTS),
        x=x,
        y=y,
        spawned_at=now,
    )


def maybe_spawn_gate(
    gates: list[Gate], now: float, last_spawn_at: float, rng: random.Random
) -> tuple[list[Gate], float]:
    """Announce one gate if under the on-screen cap and the spawn interval
    has elapsed (both ramp with `now`, the match clock). The new gate is
    placed and typed right away and appears GATE_WARNING_SECONDS later."""
    if len(gates) >= gate_cap(now):
        return gates, last_spawn_at
    if now - last_spawn_at < spawn_interval(now):
        return gates, last_spawn_at
    gate = spawn_gate(rng, now + GATE_WARNING_SECONDS, existing_gates=gates)
    if gate is None:
        return gates, now  # no room right now -- try again next interval
    return [*gates, gate], now


def apply_h(ball: Ball) -> list[Ball]:
    """Split into two: one keeps going, one reverses horizontal direction."""
    return [ball, Ball(x=ball.x, y=ball.y, vx=-ball.vx, vy=ball.vy)]


def apply_x(ball: Ball) -> Ball:
    """Bounce as if off a vertical wall: reverse horizontal direction."""
    return Ball(x=ball.x, y=ball.y, vx=-ball.vx, vy=ball.vy)


def apply_z(ball: Ball) -> Ball:
    """Bounce as if off a horizontal wall: reverse vertical direction."""
    return Ball(x=ball.x, y=ball.y, vx=ball.vx, vy=-ball.vy)


def apply_swap(ball: Ball) -> Ball:
    """Teleport to the mirrored spot across the field and reverse horizontal
    momentum, so the ball keeps moving deeper into the side it just landed on."""
    return Ball(x=INTERNAL_WIDTH - ball.x, y=ball.y, vx=-ball.vx, vy=ball.vy)


def _touches(ball: Ball, gate: Gate, ball_radius: float) -> bool:
    dx = ball.x - gate.x
    dy = ball.y - gate.y
    return dx * dx + dy * dy <= (ball_radius + GATE_RADIUS) ** 2


def check_gate_collisions(
    balls: list[Ball], gates: list[Gate], ball_radius: float, now: float = math.inf
) -> tuple[list[Ball], list[Gate]]:
    """If any ball touches a gate that has appeared by `now`, apply it and
    consume the gate (announced gates are ignored). At most one gate is
    consumed per call. An H touch while at the ball cap does nothing (gate
    stays, ball is untouched)."""
    for gate in gates:
        if not is_live(gate, now):
            continue
        for i, ball in enumerate(balls):
            if not _touches(ball, gate, ball_radius):
                continue

            if gate.kind == "H":
                if len(balls) >= MAX_BALLS_ON_SCREEN:
                    continue
                new_balls = balls[:i] + apply_h(ball) + balls[i + 1 :]
            elif gate.kind == "X":
                new_balls = balls[:i] + [apply_x(ball)] + balls[i + 1 :]
            elif gate.kind == "Z":
                new_balls = balls[:i] + [apply_z(ball)] + balls[i + 1 :]
            else:  # SWAP
                new_balls = balls[:i] + [apply_swap(ball)] + balls[i + 1 :]

            remaining_gates = [g for g in gates if g is not gate]
            return new_balls, remaining_gates

    return balls, gates
