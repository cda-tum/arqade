from qurves import rules, tutorial
from qurves.tutorial import Demo


def play(demo, seconds, dt=1 / 60):
    events = []
    for _ in range(round(seconds / dt)):
        events += demo.update(dt)
    return events


def test_the_demo_splits_loses_a_copy_and_p1_takes_the_round():
    demo = Demo()
    assert demo.phase == 0
    events = []
    phases = []
    while not demo.state.over:
        events += demo.update(1 / 60)
        phases.append(demo.phase)
        assert len(phases) < 600, "the demo never ends"
    assert [e.player for e in events if isinstance(e, rules.Split)] == ["p1"]
    crashes = [e for e in events if isinstance(e, rules.Crash)]
    assert [c.player for c in crashes] == ["p1", "p2"]  # a copy first, then P2 at the wall
    assert demo.state.winner == "p1"
    assert sorted(set(phases)) == [0, 1, 2, 3] and phases == sorted(phases)
    # A few seconds is all it takes, so a reader sees it whole.
    assert 3.0 < len(phases) / 60 < 6.0


def test_the_copy_that_crashed_dissolves_and_the_survivor_turns_solid():
    demo = Demo()
    events = play(demo, 3.0)
    collapse = next(e for e in events if isinstance(e, rules.Collapse))
    assert collapse.player == "p1" and collapse.reason == "crash"
    assert collapse.dissolved and collapse.solidified
    p1 = demo.state.players["p1"]
    assert p1.alive and len(p1.bikes) == 1 and not p1.nodes


def test_the_demo_loops():
    demo = Demo()
    first = demo.state
    play(demo, 4.0 + tutorial.DEMO_HOLD + 0.5)
    assert demo.state is not first and not demo.state.over


def test_the_card_names_only_printed_cabinet_buttons():
    assert {b for row in tutorial.CLUSTER for b in row} == {"L", "X", "R", "Y", "B", "A"}
    assert set(tutorial.BUTTON_DIR) == {"X", "Y", "B", "A"}
    assert tutorial.PROMPT == "PRESS ANY BUTTON TO START"
