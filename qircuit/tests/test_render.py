"""A smoke test of the real OpenGL drawing, through SDL's offscreen driver
(desktop GL, in software). Skipped where no GL context can be made."""

import os
import random

import pytest

os.environ["SDL_VIDEODRIVER"] = "offscreen"
import pygame  # noqa: E402

from qircuit import config, gfx  # noqa: E402
from qircuit.match import RACE, FrameInput, Match  # noqa: E402


@pytest.fixture(scope="module")
def renderer():
    pygame.display.quit()
    pygame.init()
    try:
        size, es = gfx.open_window((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT), False)
    except RuntimeError as exc:
        pytest.skip(f"no OpenGL here: {exc}")
    from qircuit.render import Renderer
    yield Renderer(size, es)
    pygame.display.quit()


@pytest.mark.parametrize("track_index", [0, 1, 2])
def test_every_screen_draws(renderer, track_index):
    m = Match(random.Random(0))
    m.humans, m.bots, m.track_index = 2, 3, track_index
    for _ in range(5):
        renderer.draw(m, m.update(1 / 60, FrameInput()), 1 / 60)  # the title and its demo
    renderer.draw(m, m.update(1 / 60, FrameInput(confirm=True)), 1 / 60)  # the racer select
    renderer.draw(m, m.update(1 / 60, FrameInput(pause=True)), 1 / 60)  # the HOW TO PLAY card
    for _ in range(20):  # past tutorial.LOCK
        renderer.draw(m, m.update(1 / 60, FrameInput()), 1 / 60)
    renderer.draw(m, m.update(1 / 60, FrameInput(any_button=True)), 1 / 60)  # countdown
    for _ in range(round(config.COUNTDOWN * 60) + 40):
        renderer.draw(m, m.update(1 / 60, FrameInput(activity=True)), 1 / 60)
    assert m.state == RACE
    race = m.race
    race.bodies[0].air, race.bodies[0].z = True, 20.0
    race.bodies[1].measured, race.bodies[3].ghost = 0.5, 1.0
    race.bodies[2].load, race.bodies[2].slip = 2.0, 0.5
    for _ in range(10):
        renderer.draw(m, m.update(1 / 60, FrameInput(activity=True)), 1 / 60)
    renderer.present()
    shot = renderer.snapshot()
    assert shot.get_size() == (config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT)
    colours = {shot.get_at((x, y))[:3] for x in range(0, 960, 40) for y in range(60, 540, 40)}
    assert len(colours) > 10  # a picture, not a blank


def test_pyopengl_sees_the_context(renderer):
    """PyOpenGL must look for the context on the platform SDL made it on
    (EGL, see qircuit/__init__.py), or it finds none the first time it
    needs one."""
    from OpenGL import platform
    assert platform.GetCurrentContext()
