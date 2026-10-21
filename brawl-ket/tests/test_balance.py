"""The balance bar (docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md, section 6):
bot against bot, from both sides, no fighter wins more than about 60% of the rounds against
another. Held for every pairing with ERWIN or DOS; `tools/balance.py` prints the whole table
(the older three's pairings included, which were never held to it)."""

import itertools

import pytest

from brawl_ket.bot import Bot
from brawl_ket.config import ROUND_FRAMES
from brawl_ket.fight import Fight
from brawl_ket.moves import CHARACTERS

SEEDS = range(50)       # 100 rounds a pairing, 50 from each side
BAR = 0.62              # "about 60%", with room for 100 rounds' noise (tools/balance.py checks 0.60 over 400)
NEW = ("ERWIN", "DOS")
PAIRS = [(a, b) for a, b in itertools.combinations(CHARACTERS, 2) if a in NEW or b in NEW]


def winner(seed: int, p1: str, p2: str) -> str | None:
    fight = Fight({"p1": CHARACTERS[p1], "p2": CHARACTERS[p2]}, seed=seed)
    bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
    for _ in range(2 * ROUND_FRAMES):
        if fight.over:
            break
        fight.step({k: b.input(fight) for k, b in bots.items()})
    return fight.winner


def share(a: str, b: str) -> float:
    """a's share of the decided rounds against b, playing each seed from both sides."""
    won = lost = 0
    for seed in SEEDS:
        for p1, p2 in ((a, b), (b, a)):
            w = winner(seed, p1, p2)
            if w is None:
                continue
            if (w == "p1") == (p1 == a):
                won += 1
            else:
                lost += 1
    return won / max(1, won + lost)


def test_every_new_pairing_is_checked():
    assert len(PAIRS) == 9          # ERWIN against the other five, DOS against the four besides ERWIN


@pytest.mark.parametrize("pair", PAIRS, ids="-".join)
def test_no_fighter_wins_more_than_about_60_percent(pair):
    s = share(*pair)
    assert 1 - BAR <= s <= BAR, (pair, round(s, 2))
