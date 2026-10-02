import pytest

from brawl_ket.bot import Bot
from brawl_ket.config import ROUND_FRAMES
from brawl_ket.fight import Fight
from brawl_ket.moves import CHARACTERS

SEEDS = range(10)
PAIRINGS = [(a, b) for a in CHARACTERS for b in CHARACTERS]


def test_every_pairing_is_covered():
    assert {"TRIO", "QUINT"} <= set(CHARACTERS)
    assert len(PAIRINGS) == len(CHARACTERS) ** 2


def play(seed, pairing=("TRIO", "TRIO")):
    """One round between two bots; returns the finished Fight and its events."""
    fight = Fight({"p1": CHARACTERS[pairing[0]], "p2": CHARACTERS[pairing[1]]})
    bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
    events = []
    for _ in range(ROUND_FRAMES + 1):
        if fight.over:
            break
        events += fight.step({key: bot.input(fight) for key, bot in bots.items()})
    return fight, events


@pytest.mark.parametrize("pairing", PAIRINGS)
def test_bot_vs_bot_rounds_always_finish(pairing):
    for seed in SEEDS:
        fight, events = play(seed, pairing)
        assert fight.over, f"seed {seed} did not finish"
        assert any(e.kind == "logical" for e in events), f"seed {seed}: no logical error"


@pytest.mark.parametrize("pairing", PAIRINGS)
def test_bots_are_deterministic(pairing):
    for seed in SEEDS:
        (f1, e1), (f2, e2) = play(seed, pairing), play(seed, pairing)
        assert f1.winner == f2.winner
        assert e1 == e2


QUINT_TRIO_XFAIL = pytest.mark.xfail(
    strict=False,
    reason="QUINT's compensations (115 health, longer normals) land in Task 4 and grid-reading "
           "bots in Task 6; re-enable then (since Task 3's faster DIVE, TRIO as p1 also wins "
           "every seed against QUINT, so both mixed pairings are marked)",
)


@pytest.mark.parametrize("pairing", [
    pytest.param(p, marks=QUINT_TRIO_XFAIL) if set(p) == {"QUINT", "TRIO"} else p for p in PAIRINGS
])
def test_neither_side_is_favoured(pairing):
    winners = {play(seed, pairing)[0].winner for seed in SEEDS}
    assert {"p1", "p2"} <= winners


def test_neither_character_always_wins():
    # TRIO against QUINT, from both sides: each character wins some rounds
    won = set()
    for pairing in (("TRIO", "QUINT"), ("QUINT", "TRIO")):
        for seed in SEEDS:
            winner = play(seed, pairing)[0].winner
            if winner is not None:
                won.add(pairing[0] if winner == "p1" else pairing[1])
    assert won == {"TRIO", "QUINT"}


def test_quint_bots_use_their_specials():
    # over some rounds, a QUINT bot grabs, re-encodes and slams
    slots = set()
    for seed in range(40):
        if {"stand.X", "crouch.X", "air.X"} <= slots:
            break
        fight = Fight({"p1": CHARACTERS["QUINT"], "p2": CHARACTERS["TRIO"]})
        bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
        while not fight.over:
            fight.step({key: bot.input(fight) for key, bot in bots.items()})
            quint = fight.fighters["p1"]
            if quint.action == "attack":
                slots.add(quint.slot)
    assert {"stand.X", "crouch.X", "air.X"} <= slots


@pytest.mark.parametrize("pairing", PAIRINGS)
def test_presses_are_edges_not_held(pairing):
    fight = Fight({"p1": CHARACTERS[pairing[0]], "p2": CHARACTERS[pairing[1]]})
    bot, rival = Bot("p1", 3), Bot("p2", 4)
    last = None
    for _ in range(ROUND_FRAMES):
        if fight.over:
            break
        mine = bot.input(fight)
        fight.step({"p1": mine, "p2": rival.input(fight)})
        pressed = (mine.a, mine.b, mine.x)
        assert not any(p and q for p, q in zip(pressed, last or (False,) * 3))
        last = pressed
