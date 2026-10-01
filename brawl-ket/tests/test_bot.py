from brawl_ket.bot import Bot
from brawl_ket.config import ROUND_FRAMES
from brawl_ket.fight import Fight
from brawl_ket.moves import TRIO

SEEDS = range(10)


def play(seed):
    """One TRIO mirror round between two bots; returns the finished Fight and its events."""
    fight = Fight({"p1": TRIO, "p2": TRIO})
    bots = {"p1": Bot("p1", seed), "p2": Bot("p2", seed + 1000)}
    events = []
    for _ in range(ROUND_FRAMES + 1):
        if fight.over:
            break
        events += fight.step({key: bot.input(fight) for key, bot in bots.items()})
    return fight, events


def test_bot_vs_bot_rounds_always_finish():
    for seed in SEEDS:
        fight, events = play(seed)
        assert fight.over, f"seed {seed} did not finish"
        assert any(e.kind == "logical" for e in events), f"seed {seed}: no logical error"


def test_bots_are_deterministic():
    for seed in SEEDS:
        (f1, e1), (f2, e2) = play(seed), play(seed)
        assert f1.winner == f2.winner
        assert len(e1) == len(e2)
        assert e1 == e2


def test_neither_side_is_favoured():
    winners = {play(seed)[0].winner for seed in SEEDS}
    assert {"p1", "p2"} <= winners


def test_presses_are_edges_not_held():
    fight = Fight({"p1": TRIO, "p2": TRIO})
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
