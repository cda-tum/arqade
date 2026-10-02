"""Pause behaviour of the game loop, driven by the same raw joystick events the
cabinet sends (see "Pausing" and "Button convention" in ../AGENTS.md)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from ion_surfer import game as game_mod  # noqa: E402
from ion_surfer.config import INPUT_CONFIG  # noqa: E402

START = INPUT_CONFIG["system"]["start_button"]    # raw 9
SELECT = INPUT_CONFIG["system"]["select_button"]  # raw 8
A = INPUT_CONFIG["p1"]["buttons"]["confirm"][0]    # raw 1
B = INPUT_CONFIG["p1"]["buttons"]["back"][0]       # raw 2
Y_AXIS = INPUT_CONFIG["p1"]["axes"][1]


@pytest.fixture
def make_game(tmp_path, monkeypatch):
    monkeypatch.setattr(game_mod, "SCORE_FILE", tmp_path / "scores.json")
    pygame.init()

    def make(mode=1, sandbox_only=False):
        g = game_mod.Game(pygame.Surface((game_mod.W, game_mod.H)), sandbox_only=sandbox_only)
        # Fake both pads as connected joysticks: instance id == pad index.
        g.controls.joys = {0: (None, 0), 1: (None, 1)}
        if not sandbox_only:
            g.start(mode)
        return g

    yield make
    pygame.quit()


def frame(g, *events, dt=1 / 60):
    """One iteration of run()'s loop. Returns False if the quit combo fired."""
    g.controls.begin_frame()
    for e in events:
        g.controls.handle(e)
    if g.controls.quit_combo():
        return False
    g.controls.update(dt)
    g.update(dt)
    return True


def down(button, pad=0):
    return pygame.event.Event(pygame.JOYBUTTONDOWN, instance_id=pad, button=button)


def up(button, pad=0):
    return pygame.event.Event(pygame.JOYBUTTONUP, instance_id=pad, button=button)


def tap(g, button, pad=0):
    frame(g, down(button, pad))
    frame(g, up(button, pad))


def stick_down(g, pad=0):
    frame(g, pygame.event.Event(pygame.JOYAXISMOTION, instance_id=pad, axis=Y_AXIS, value=1.0))
    frame(g, pygame.event.Event(pygame.JOYAXISMOTION, instance_id=pad, axis=Y_AXIS, value=0.0))


@pytest.mark.parametrize("pad", [0, 1])
def test_start_pauses_play_from_either_pad(make_game, pad):
    g = make_game(mode=2)
    tap(g, START, pad)
    assert g.state == "pause"
    assert g.menu_sel == 0


def test_pause_freezes_the_world(make_game):
    g = make_game()
    for _ in range(10):
        frame(g)
    tap(g, START)
    t, cam = g.t, g.cam_x
    for _ in range(30):
        frame(g)
    assert g.state == "pause"
    assert (g.t, g.cam_x) == (t, cam)


def test_select_alone_does_not_pause(make_game):
    g = make_game()
    tap(g, SELECT)
    assert g.state == "play"


def test_start_plus_select_still_quits_while_playing_and_paused(make_game):
    g = make_game()
    assert frame(g, down(START), down(SELECT)) is False
    g = make_game()
    tap(g, START)
    assert g.state == "pause"
    frame(g, down(START))
    assert frame(g, down(SELECT)) is False


@pytest.mark.parametrize("button", [START, B])
def test_start_or_b_resumes(make_game, button):
    g = make_game()
    tap(g, START)
    stick_down(g)  # even with another item highlighted, Start/B resume
    tap(g, button)
    assert g.state == "play"


def test_pause_menu_offers_resume_and_quit_to_title(make_game):
    items = make_game().PAUSE_ITEMS
    assert items[0] == "RESUME"
    assert "QUIT TO TITLE" in items


def test_a_on_resume_resumes(make_game):
    g = make_game()
    tap(g, START)
    tap(g, A)
    assert g.state == "play"


def test_a_on_quit_to_title_goes_to_the_title(make_game):
    g = make_game()
    tap(g, START)
    for _ in range(g.PAUSE_ITEMS.index("QUIT TO TITLE")):
        stick_down(g)
    assert g.PAUSE_ITEMS[g.menu_sel] == "QUIT TO TITLE"
    tap(g, A)
    assert g.state == "menu"
    assert g.running


def test_start_and_select_mean_pause_and_laser_kick_in_the_sandbox(make_game):
    g = make_game(mode=game_mod.SANDBOX)
    kicks = []
    g.sandbox.kick = kicks.append
    tap(g, SELECT, pad=1)
    assert g.state == "play" and kicks == [1]
    tap(g, START, pad=1)
    assert g.state == "pause" and kicks == [1]
    tap(g, START, pad=1)
    assert g.state == "play"


def test_sandbox_only_pause_menu_quits_the_program(make_game):
    g = make_game(sandbox_only=True)
    tap(g, START)
    assert g.PAUSE_ITEMS[-1] == "QUIT"
    for _ in range(len(g.PAUSE_ITEMS) - 1):
        stick_down(g)
    tap(g, A)
    assert not g.running


def test_keyboard_fallback_pauses_with_start_key_and_esc(make_game):
    g = make_game()
    for key in (pygame.K_1, pygame.K_ESCAPE):
        frame(g, pygame.event.Event(pygame.KEYDOWN, key=key, unicode=""))
        frame(g, pygame.event.Event(pygame.KEYUP, key=key, unicode=""))
        assert g.state == "pause"
        frame(g, pygame.event.Event(pygame.KEYDOWN, key=key, unicode=""))
        frame(g, pygame.event.Event(pygame.KEYUP, key=key, unicode=""))
        assert g.state == "play"
