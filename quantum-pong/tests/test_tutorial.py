import pytest

from quantum_pong import config
from quantum_pong.gates import is_live
from quantum_pong.tutorial import DEMO_KINDS, DemoScene, DismissGate

DT = 1 / 60


# --- Dismissal ---


def test_a_press_in_the_first_moment_does_not_dismiss():
    gate = DismissGate()
    assert not gate.update(DT, pressed=True)
    while gate.age + DT < config.TUTORIAL_IGNORE_SECONDS:
        assert not gate.update(DT, pressed=True)


def test_a_press_after_the_grace_period_dismisses_at_once():
    gate = DismissGate()
    while gate.age < config.TUTORIAL_IGNORE_SECONDS:
        gate.update(DT, pressed=False)
    assert gate.update(DT, pressed=True)


def test_nothing_pressed_never_dismisses():
    gate = DismissGate()
    for _ in range(60 * 30):
        assert not gate.update(DT, pressed=False)


# --- The demo ---


def _run_scene(demo: DemoScene):
    """Step one whole scene; yield after every frame."""
    scene = demo.scene
    while demo.scene == scene:
        demo.step(DT)
        yield


def test_demo_cycles_through_every_gate_kind():
    demo = DemoScene()
    seen = []
    for _ in DEMO_KINDS:
        seen.append(demo.kind)
        for _ in _run_scene(demo):
            pass
    assert seen == list(DEMO_KINDS)


@pytest.mark.parametrize("scene", range(len(DEMO_KINDS)))
def test_each_scene_announces_the_gate_then_the_ball_runs_into_it(scene):
    demo = DemoScene(scene=scene)
    gate = demo.gates[0]
    assert not is_live(gate, demo.t)  # announced first, as a dashed outline
    consumed_at = None
    for _ in _run_scene(demo):
        if demo.scene != scene:
            break
        assert demo.balls, "the demo never runs out of balls"
        if consumed_at is None and not demo.gates:
            consumed_at = demo.t
    assert consumed_at is not None
    # It was live when the ball hit it: the warning lasted the real time.
    assert consumed_at >= config.GATE_WARNING_SECONDS


def test_h_scene_splits_the_ball():
    demo = DemoScene(scene=DEMO_KINDS.index("H"))
    most = 0
    for _ in _run_scene(demo):
        most = max(most, len(demo.balls))
    assert most == 2


def test_x_scene_sends_the_ball_back():
    demo = DemoScene(scene=DEMO_KINDS.index("X"))
    for _ in _run_scene(demo):
        if not demo.gates:
            assert demo.balls[0].vx < 0
            return
    pytest.fail("the X gate was never hit")
