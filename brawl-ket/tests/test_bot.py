import pytest

from brawl_ket.bot import Bot
from brawl_ket.config import ROUND_FRAMES
from brawl_ket.fight import Fight
from brawl_ket.moves import CHARACTERS

SEEDS = range(10)
PAIRINGS = [(a, b) for a in CHARACTERS for b in CHARACTERS]


def test_every_pairing_is_covered():
    assert {"ROBERT", "BOHR"} <= set(CHARACTERS)
    assert len(PAIRINGS) == len(CHARACTERS) ** 2


def play(seed, pairing=("ROBERT", "ROBERT")):
    """One round between two bots; returns the finished Fight and its events."""
    fight = Fight({"p1": CHARACTERS[pairing[0]], "p2": CHARACTERS[pairing[1]]}, seed=seed)
    bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
    events = []
    for _ in range(2 * ROUND_FRAMES):      # hit freezes don't run the clock: room for them
        if fight.over:
            break
        events += fight.step({key: bot.input(fight) for key, bot in bots.items()})
    return fight, events


@pytest.mark.parametrize("pairing", PAIRINGS)
def test_bot_vs_bot_rounds_always_finish(pairing):
    for seed in SEEDS:
        fight, events = play(seed, pairing)
        assert fight.over, f"seed {seed} did not finish"


@pytest.mark.parametrize("pairing", PAIRINGS)
def test_bots_land_hits_in_both_colours(pairing):
    errors = set()
    for seed in SEEDS:
        _, events = play(seed, pairing)
        errors |= {e.error for e in events if e.kind == "hit"}
    fixed = all(CHARACTERS[name].fixed_basis for name in pairing)
    assert ({"X"} if fixed else {"X", "Z"}) <= errors, (pairing, errors)       # both colours land (DOS: green)


def test_bots_switch_basis_sometimes():
    switches = sum(1 for seed in SEEDS for e in play(seed)[1] if e.kind == "switch")
    assert switches > 0


@pytest.mark.parametrize("pairing", PAIRINGS)
def test_bots_are_deterministic(pairing):
    for seed in SEEDS:
        (f1, e1), (f2, e2) = play(seed, pairing), play(seed, pairing)
        assert f1.winner == f2.winner
        assert e1 == e2


# ERWIN and DOS have no bot logic of their own until Task 6 (they play as ROBERT does): Task 6
# removes this list and the test takes PAIRINGS again.
FAVOURED_PAIRINGS = [
    pytest.param(pair, marks=pytest.mark.xfail(reason="ERWIN's bot: Task 6", strict=False))
    if pair == ("ROBERT", "ERWIN") else
    pytest.param(pair, marks=pytest.mark.xfail(reason="DOS's bot: Task 6", strict=False))
    if pair == ("BOHR", "DOS") else pair
    for pair in PAIRINGS
]


@pytest.mark.parametrize("pairing", FAVOURED_PAIRINGS)
def test_neither_side_is_favoured(pairing):
    winners = {play(seed, pairing)[0].winner for seed in SEEDS}
    assert {"p1", "p2"} <= winners


def test_neither_character_always_wins():
    # ROBERT against BOHR, from both sides: each character wins some rounds
    won = set()
    for pairing in (("ROBERT", "BOHR"), ("BOHR", "ROBERT")):
        for seed in SEEDS:
            winner = play(seed, pairing)[0].winner
            if winner is not None:
                won.add(pairing[0] if winner == "p1" else pairing[1])
    assert won == {"ROBERT", "BOHR"}


def test_bohr_bots_use_their_specials():
    # over some rounds, a BOHR bot measures, waves and slams
    slots = set()
    for seed in range(40):
        if {"stand.X", "crouch.X", "air.X"} <= slots:
            break
        fight = Fight({"p1": CHARACTERS["BOHR"], "p2": CHARACTERS["ROBERT"]})
        bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
        while not fight.over:
            fight.step({key: bot.input(fight) for key, bot in bots.items()})
            bohr = fight.fighters["p1"]
            if bohr.action == "attack":
                slots.add(bohr.slot)
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
        pressed = (mine.a, mine.b, mine.x, mine.y)
        assert not any(p and q for p, q in zip(pressed, last or (False,) * 4))
        last = pressed
