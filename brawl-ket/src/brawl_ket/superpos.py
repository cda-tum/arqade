"""SUPERposition's bar: one per player, a green half (Z) and a purple half (X); full when both are.

Pure logic, no pygame. The fight fills it where damage is applied (fight.py, _fill): damage
dealt fills the half of the basis the attacker is in when it lands, damage taken the half of the
basis the one hit is in, at half the rate. DOS can't switch, so his dealt damage fills the half
of the hit's colour instead (the basis of the one it hurt). A super's own damage fills nothing.
The match keeps one per player for a whole match, so it carries over from round to round
(docs/superpowers/specs/2026-10-22-brawl-ket-superposition-design.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import basis
from .config import SUPER_HALF

FULL = 2 * SUPER_HALF   # a half, in half points: damage taken fills at half the rate


@dataclass
class Meter:
    fill: dict[str, int] = field(default_factory=lambda: {basis.Z_BASIS: 0, basis.X_BASIS: 0})

    def dealt(self, b: str, damage: int) -> list[str]:
        """Damage dealt in basis b: its half fills point for point."""
        return self._add(b, 2 * damage)

    def taken(self, b: str, damage: int) -> list[str]:
        """Damage taken in basis b: its half fills at half the rate."""
        return self._add(b, damage)

    def _add(self, b: str, half_points: int) -> list[str]:
        """Fill b's half (the overflow is lost). Returns what just happened: "half" if that
        filled it, and then "full" if the whole bar is now full."""
        before = self.fill[b]
        self.fill[b] = min(FULL, before + half_points)
        if before >= FULL or self.fill[b] < FULL:
            return []
        return ["half", "full"] if self.full else ["half"]

    @property
    def full(self) -> bool:
        return all(v >= FULL for v in self.fill.values())

    def share(self, b: str) -> float:
        """How full b's half is, 0 to 1."""
        return self.fill[b] / FULL

    def empty(self) -> None:
        for b in self.fill:
            self.fill[b] = 0
