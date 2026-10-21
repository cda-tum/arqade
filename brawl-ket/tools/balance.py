"""Bot-against-bot win rates for every pairing of fighters, from both sides.

    cd brawl-ket && uv run python tools/balance.py [SEEDS]

For each pair, the share of the decided rounds each fighter won, over SEEDS seeds from each
side (200 by default). The bar (docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md,
section 6): no fighter wins more than about 60% against another. tests/test_balance.py holds
every pairing with ERWIN or DOS to it; the older three's pairings are only reported here.
"""

from __future__ import annotations

import itertools
import sys

from brawl_ket.bot import Bot
from brawl_ket.config import ROUND_FRAMES
from brawl_ket.fight import Fight
from brawl_ket.moves import CHARACTERS

BAR = 0.60


def winner(seed: int, p1: str, p2: str) -> str | None:
    fight = Fight({"p1": CHARACTERS[p1], "p2": CHARACTERS[p2]}, seed=seed)
    bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
    for _ in range(2 * ROUND_FRAMES):
        if fight.over:
            break
        fight.step({k: b.input(fight) for k, b in bots.items()})
    return fight.winner


def share(a: str, b: str, seeds) -> float:
    """a's share of the decided rounds against b, playing each seed from both sides."""
    won = lost = 0
    for seed in seeds:
        for p1, p2 in ((a, b), (b, a)):
            w = winner(seed, p1, p2)
            if w is None:
                continue
            if (w == "p1") == (p1 == a):
                won += 1
            else:
                lost += 1
    return won / max(1, won + lost)


def main(argv: list[str]) -> None:
    n = int(argv[0]) if argv else 200
    for a, b in itertools.combinations(CHARACTERS, 2):
        s = share(a, b, range(n))
        flag = "" if 1 - BAR <= s <= BAR else "   <- over the bar"
        print(f"{a:>6} v {b:<6}  {a} {s:4.0%}  {b} {1 - s:4.0%}{flag}")


if __name__ == "__main__":
    main(sys.argv[1:])
