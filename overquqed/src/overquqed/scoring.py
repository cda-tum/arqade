"""Points, the 0.8 acceptance threshold and stars. Pure functions.

The threshold is a deliberate nod to the fault-tolerance threshold theorem:
below it, error correction makes things worse, so the guest refuses.
"""

from __future__ import annotations

from typing import Callable, Sequence, TypeVar

from overquqed.recipes import TIER_POINTS

THRESHOLD = 0.8
REFUSE_PENALTY = -10
LEAVE_PENALTY = -20
MAX_TIP = 20  # at F = 1
MAX_SPEED_BONUS = 10  # served the instant the ticket appeared

T = TypeVar("T")


def fidelity_tip(fidelity: float, tip_mult: float = 1.0) -> int:
    """0 at the threshold, MAX_TIP * tip_mult at perfect fidelity."""
    frac = (fidelity - THRESHOLD) / (1 - THRESHOLD)
    return round(MAX_TIP * tip_mult * min(1.0, max(0.0, frac)))


def delivery_points(tier: int, fidelity: float, patience_frac: float, tip_mult: float = 1.0) -> tuple[int, int, int]:
    """(base, tip, speed bonus) for an accepted delivery."""
    base = TIER_POINTS[tier]
    speed = round(MAX_SPEED_BONUS * min(1.0, max(0.0, patience_frac)))
    return base, fidelity_tip(fidelity, tip_mult), speed


def choose_order(orders: Sequence[T], fidelity_of: Callable[[T], float]) -> tuple[T, float]:
    """Best fidelity wins; ties (within 1e-6) go to the earliest in `orders`,
    which is kept oldest-first."""
    best, best_f = orders[0], fidelity_of(orders[0])
    for order in orders[1:]:
        f = fidelity_of(order)
        if f > best_f + 1e-6:
            best, best_f = order, f
    return best, best_f


def stars(score: int, thresholds: tuple[int, int, int]) -> int:
    return sum(score >= t for t in thresholds)
