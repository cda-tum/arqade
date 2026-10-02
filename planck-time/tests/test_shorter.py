"""SHORTER! teaches circuit optimisation over a session. The answer is always
the circuit with fewer gates once identical neighbours cancel (repeatedly);
what the written counts show depends on how often the player has seen it."""

from planck_time.microgames.shorter import Shorter, cancelled, compiled, written

SEEDS = range(150)
LEVELS = (0, 3)


def rounds(appearance):
    for seed in SEEDS:
        for level in LEVELS:
            g = Shorter.spawn(seed, level, 4.0, appearance)
            yield g, g.circuits[g.short], g.circuits[1 - g.short]


def test_cancelling_cascades():
    assert cancelled(["X", "H", "H", "X"]) == {0, 1, 2, 3}
    assert cancelled(["X", "Z", "X"]) == set()
    assert cancelled(["H", "H", "H"]) == {0, 1}


def test_the_answer_is_always_shorter_after_optimising():
    for appearance in (0, 1, 2, 4):
        for _g, answer, decoy in rounds(appearance):
            assert compiled(answer) < compiled(decoy)


def test_first_time_the_answer_is_plainly_shorter_and_the_other_has_a_pair():
    for _g, answer, decoy in rounds(0):
        assert written(answer) < written(decoy)
        assert compiled(decoy) < written(decoy)  # it does optimise...
        assert compiled(decoy) > written(answer)  # ...and is still longer


def test_second_time_counting_by_eye_picks_wrong():
    for _g, answer, decoy in rounds(1):
        assert written(answer) > written(decoy)


def test_later_the_written_counts_say_nothing_either_way():
    looks = {1: 0, 0: 0, -1: 0}
    for _g, answer, decoy in rounds(2):
        looks[(written(answer) > written(decoy)) - (written(answer) < written(decoy))] += 1
    total = sum(looks.values())
    assert looks[1] > total * 0.35 and looks[0] > total * 0.12 and looks[-1] > total * 0.12


def test_the_session_counts_appearances():
    import random

    from planck_time import session as S
    from planck_time.hiscores import Hiscores

    s = S.Session(random.Random(0), Hiscores(None), [Shorter])
    s.update(1 / 60, S.FrameInput(activity=True, confirms={"p1": True, "p2": False}))
    seen = [s.games["p1"].appearance]
    for _ in range(2):
        while s.state != S.PLAY:
            s.update(1 / 60, S.FrameInput(activity=True))
        while s.state == S.PLAY:
            fi = S.FrameInput(activity=True)
            fi.players = {"p1": s.games["p1"].bot(), "p2": S.PlayerInput()}
            s.update(1 / 60, fi)
        while s.state != S.INTRO:
            s.update(1 / 60, S.FrameInput(activity=True))
        seen.append(s.games["p1"].appearance)
    assert seen == [0, 1, 2]
