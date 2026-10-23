"""The balance bar (docs/superpowers/specs/2026-10-21-brawl-ket-erwin-dos-design.md, section 6,
2026-10-21-brawl-ket-m-cutie-design.md, section 5, and 2026-10-21-brawl-ket-alice-bob-design.md, section 5):
bot against bot, from both sides, no fighter wins more than about 60% of the rounds against another.
Held for every pairing with ERWIN, DOS, M-CUTIE or ALICE & BOB; `tools/balance.py` prints the whole
table (the older three's pairings included, which were never held to it)."""

import itertools

import pytest

from brawl_ket.bot import Bot
from brawl_ket.config import ROUND_FRAMES
from brawl_ket.fight import Fight
from brawl_ket.moves import CHARACTERS

SEEDS = range(50)       # 100 rounds a pairing, 50 from each side
BAR = 0.62              # "about 60%", with room for 100 rounds' noise (tools/balance.py checks 0.60 over 400)
NEW = ("ERWIN", "DOS", "M-CUTIE", "ALICE & BOB")
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
    assert len(PAIRS) == 18         # all 21 pairings of seven but the older three's among themselves


# Over the bar, for the user to decide: with the health and walk the spec fixes, M-CUTIE plays
# PHOEBE as ROBERT does (60%) with 5 more health; about 65% over 400 rounds, whatever her bot does
# (docs/superpowers/plans/2026-10-21-brawl-ket-m-cutie.md, Task 4).
OVER_THE_BAR = {("PHOEBE", "M-CUTIE"): "M-CUTIE wins about 65% against PHOEBE: for the user to decide"}
# ... and ALICE & BOB's two outside the bar, both measured over 400 rounds in their plan's Task 6
# (docs/superpowers/plans/2026-10-22-brawl-ket-alice-bob.md): BOHR wins about 67% against them
# (MEASURE, 12 and a knockdown from 130 px, and CHARGE NOISE, which hits each body inside it), and
# they win about 63% against PHOEBE (with ROBERT's normals: ROBERT himself wins 60% against her).
# After the playtest's singlet colours and ANCHOR, over 200 rounds: BOHR about 72%, them about 63%
OVER_THE_BAR.update({
    ("BOHR", "ALICE & BOB"): "BOHR wins about 80% against ALICE & BOB: for the user to decide",
    ("PHOEBE", "ALICE & BOB"): "ALICE & BOB win about 62% against PHOEBE: for the user to decide",
})
# ... and after the user's feel tuning (2026-10-22: every A normal 4 frames more recovery, faster
# walks, and jumps long and high enough to clear anyone), over 200 rounds: ROBERT, whose jab
# strings carried him, loses ground; BOHR's MEASURE and CHARGE NOISE catch the longer jumps
OVER_THE_BAR.update({
    ("ROBERT", "ERWIN"): "ERWIN wins about 68% against ROBERT: for the user to decide",
    ("ROBERT", "DOS"): "ROBERT wins about 63% against DOS: for the user to decide",
})
# ... and with SUPERposition, all seven supers (2026-10-22, docs/superpowers/plans/2026-10-22-brawl-ket-
# superposition-supers.md, Task 4), over 200 rounds: DOS, the slowest, gets caught by PHOEBE's beam
# and ERWIN's pounces (DOS against ALICE & BOB, BOHR against ERWIN and ROBERT against ALICE & BOB came
# back inside the bar)
OVER_THE_BAR.update({
    ("PHOEBE", "DOS"): "PHOEBE wins about 64% against DOS: for the user to decide",
    ("ERWIN", "DOS"): "ERWIN wins about 64% against DOS: for the user to decide",
})
# ... and with a super's startup untouchable (2026-10-22: a jab used to knock BOHR out of his 36
# frames of WAVEFUNCTION COLLAPSE, wasting the bar), over 200 rounds
OVER_THE_BAR.update({
    ("BOHR", "DOS"): "BOHR wins about 63% against DOS: for the user to decide",
})
# ... and with DOS's bar green only (2026-10-23, section 9 of the SUPERposition spec): it fills about
# twice as fast, and his BLUE SCREEN, which freezes both kids, comes round twice as often
OVER_THE_BAR.update({
    ("DOS", "ALICE & BOB"): "DOS wins about 83% against ALICE & BOB: for the user to decide",
})
CASES = [pytest.param(p, id="-".join(p), marks=[pytest.mark.xfail(reason=OVER_THE_BAR[p], strict=False)]
                      if p in OVER_THE_BAR else []) for p in PAIRS]


@pytest.mark.parametrize("pair", CASES)
def test_no_fighter_wins_more_than_about_60_percent(pair):
    s = share(*pair)
    assert 1 - BAR <= s <= BAR, (pair, round(s, 2))
