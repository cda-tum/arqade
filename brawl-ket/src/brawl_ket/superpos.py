"""SUPERposition's bar: one per player, a green half (Z) and a purple half (X); full when both are.

Pure logic, no pygame. The fight fills it where damage is applied (fight.py, _fill): damage
dealt fills the half of the basis the attacker is in when it lands, damage taken the half of the
basis the one hit is in, at half the rate. DOS can't switch: his bar is one green bar, which
everything he deals or takes fills (Meter.one_colour). A super's own damage fills nothing.
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

    @property
    def halves(self) -> tuple[str, ...]:
        """The bar's halves, green first: both, or DOS's one green bar."""
        return tuple(self.fill)

    @property
    def cap(self) -> int:
        """What a half holds, in half points: FULL; a one-colour bar's one half holds both halves'
        worth (the user's ruling, 2026-10-23: DOS's supers come as often as anyone's)."""
        return FULL if len(self.fill) > 1 else 2 * FULL

    def one_colour(self, b: str) -> None:
        """A bar of one colour (DOS, who is always green: section 9 of the spec): everything he
        deals or takes fills it, and it is full when it holds as much as a whole two-half bar."""
        self.fill = {b: self.fill.get(b, 0)}

    def _add(self, b: str, half_points: int) -> list[str]:
        """Fill b's half (the overflow is lost). Returns what just happened: "half" if that
        filled it, and then "full" if the whole bar is now full."""
        if b not in self.fill:          # a one-colour bar: every hit fills it
            b = self.halves[0]
        before, cap = self.fill[b], self.cap
        self.fill[b] = min(cap, before + half_points)
        if before >= cap or self.fill[b] < cap:
            return []
        return ["half", "full"] if self.full else ["half"]

    @property
    def full(self) -> bool:
        return all(v >= self.cap for v in self.fill.values())

    def share(self, b: str) -> float:
        """How full b's half is, 0 to 1."""
        return self.fill[b] / self.cap

    def empty(self) -> None:
        for b in self.fill:
            self.fill[b] = 0
