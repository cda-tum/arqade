from gate_drop import tutorial
from gate_drop.tutorial import Demo


def run(demo, seconds, dt=1 / 60):
    events = []
    for _ in range(round(seconds / dt)):
        events += demo.update(dt)
    return events


def test_the_demo_moves_turns_drops_and_cancels_both_errors():
    demo = Demo()
    kinds = [e.kind for e in run(demo, tutorial.DEMO_LOOP - 0.1)]
    assert kinds.count("move") == 1 and kinds.count("rotate") == 2 and "land" in kinds
    assert kinds.count("errors") == 1 and demo.solved
    assert demo.board.piece is None  # it holds the cleared board, no random next pill


def test_the_demo_loops():
    demo = Demo()
    run(demo, tutorial.DEMO_LOOP + 0.1)
    assert demo.t < 0.2 and demo.board.errors_left() == len(tutorial.DEMO_ERRORS)


def test_the_demo_lights_each_control_while_it_uses_it():
    demo = Demo()
    lit = []
    for _ in range(round(tutorial.DEMO_LOOP * 60)):
        demo.update(1 / 60)
        if demo.control() and (not lit or lit[-1] != demo.control()):
            lit.append(demo.control())
    assert lit == ["left", "a", "a", "down"] or lit == ["left", "a", "down"]
    assert "a" in lit and lit[0] == "left" and lit[-1] == "down"


def test_the_card_text_fits_and_uses_the_printed_button_names():
    assert tutorial.CLUSTER == (("L", "X", "R"), ("Y", "B", "A"))
    assert ("START", "PAUSE") in tutorial.CONTROLS
    for name, _ in tutorial.CONTROLS:
        assert name in {"STICK", "START"} or any(name in row for row in tutorial.CLUSTER)
    for lines in tutorial.GOAL.values():
        assert 1 <= len(lines) <= 3 and all(len(line) <= 36 for line in lines)
    assert tutorial.PROMPT == "PRESS ANY BUTTON TO START"


def test_every_caption_fits_under_the_demo_well():
    demo = Demo()
    for _ in range(round(tutorial.DEMO_LOOP * 60)):
        demo.update(1 / 60)
        assert all(len(line) <= 15 for line in tutorial.caption(demo))
