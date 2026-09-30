"""Gate pickups: spawning, expiry, and deterministic per-ball effects.

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
    GATE_LIFETIME,
    GATE_MIN_SPACING,
    GATE_RADIUS,
    GATE_SPAWN_INTERVAL,
    GATE_SPAWN_MARGIN_X,
    GATE_SPAWN_MARGIN_Y,
    GATE_WEIGHTS,
    INTERNAL_HEIGHT,
    INTERNAL_WIDTH,
    MAX_BALLS_ON_SCREEN,
    MAX_GATES_ON_SCREEN,
)
from quantum_pong.pong import Ball

_POSITION_ATTEMPTS = 20  # bounded retries to find a spot away from other gates


@dataclass(frozen=True)
class Gate:
    kind: str
    x: float
    y: float
    spawned_at: float


def _pick_kind(rng: random.Random, weights: dict[str, int]) -> str:
    kinds = list(weights.keys())
    return rng.choices(kinds, weights=[weights[k] for k in kinds])[0]


def _far_enough(x: float, y: float, existing_gates, min_spacing: float) -> bool:
    return all(math.hypot(x - g.x, y - g.y) >= min_spacing for g in existing_gates)


def _pick_position(rng: random.Random, existing_gates) -> tuple[float, float]:
    """A random spot in the spawn area, kept at least GATE_MIN_SPACING from
    every existing gate when the field still has room for that; otherwise
    falls back to the last candidate tried rather than spawning nowhere."""
    candidate = (0.0, 0.0)
    for _ in range(_POSITION_ATTEMPTS):
        candidate = (
            rng.uniform(GATE_SPAWN_MARGIN_X, INTERNAL_WIDTH - GATE_SPAWN_MARGIN_X),
            rng.uniform(GATE_SPAWN_MARGIN_Y, INTERNAL_HEIGHT - GATE_SPAWN_MARGIN_Y),
        )
        if _far_enough(*candidate, existing_gates, GATE_MIN_SPACING):
            return candidate
    return candidate


def spawn_gate(
    rng: random.Random,
    now: float,
    existing_gates=(),
    weights: dict[str, int] | None = None,
) -> Gate:
    """A gate at a random spot in the middle of the field, away from the
    paddles and (space permitting) away from other gates already there."""
    x, y = _pick_position(rng, existing_gates)
    return Gate(
        kind=_pick_kind(rng, weights if weights is not None else GATE_WEIGHTS),
        x=x,
        y=y,
        spawned_at=now,
    )


def expire_gates(gates: list[Gate], now: float) -> list[Gate]:
    return [g for g in gates if now - g.spawned_at < GATE_LIFETIME]


def maybe_spawn_gate(
    gates: list[Gate], now: float, last_spawn_at: float, rng: random.Random
) -> tuple[list[Gate], float]:
    """Spawn one gate if under the on-screen cap and the spawn interval has elapsed."""
    if len(gates) >= MAX_GATES_ON_SCREEN:
        return gates, last_spawn_at
    if now - last_spawn_at < GATE_SPAWN_INTERVAL:
        return gates, last_spawn_at
    return [*gates, spawn_gate(rng, now, existing_gates=gates)], now


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
    balls: list[Ball], gates: list[Gate], ball_radius: float
) -> tuple[list[Ball], list[Gate]]:
    """If any ball touches a gate, apply it and consume the gate. At most one
    gate is consumed per call. An H touch while at the ball cap does nothing
    (gate stays, ball is untouched)."""
    for gate in gates:
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
