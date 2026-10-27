"""Pause behaviour of the game loop, driven by the same raw joystick events the
cabinet sends (see "Pausing" and "Button convention" in ../AGENTS.md)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from ion_surfer import game as game_mod  # noqa: E402
from arqade_common.input import ENCODER  # noqa: E402

START = ENCODER.buttons["start"]    # raw 9
SELECT = ENCODER.buttons["select"]  # raw 8
A = ENCODER.buttons["a"]    # raw 1
B = ENCODER.buttons["b"]       # raw 2
Y_AXIS = ENCODER.stick_axes[1]


@pytest.fixture
def make_game(tmp_path, monkeypatch):
    monkeypatch.setattr(game_mod, "SCORE_FILE", tmp_path / "scores.json")
    pygame.init()

    def make(mode=1, sandbox_only=False):
        g = game_mod.Game(pygame.Surface((game_mod.W, game_mod.H)), sandbox_only=sandbox_only)
        # Fake both pads as connected joysticks: instance id == pad index.
        g.controls.slots.slot_of = lambda iid: iid if iid in (0, 1) else None
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


def test_each_players_start_key_pauses(make_game):
    g = make_game()
    for key in (pygame.K_SPACE, pygame.K_RETURN):  # P1's Start, P2's Start
        frame(g, pygame.event.Event(pygame.KEYDOWN, key=key, unicode=""))
        frame(g, pygame.event.Event(pygame.KEYUP, key=key, unicode=""))
        assert g.state == "pause"
        frame(g, pygame.event.Event(pygame.KEYDOWN, key=key, unicode=""))
        frame(g, pygame.event.Event(pygame.KEYUP, key=key, unicode=""))
        assert g.state == "play"


class RecordingSounds:
    def __init__(self):
        self.impacts, self.ambient_calls = [], []

    def play(self, name):
        pass

    def impact(self, speed):
        self.impacts.append(speed)

    def ambient(self, sources, dt):
        self.ambient_calls.append(list(sources))


def test_a_landing_reports_how_hard_it_hit(make_game):
    """The sound is told the ion's speed into the wave: a higher drop, a
    harder landing."""
    def drop(height):
        g = make_game()
        g.sounds = RecordingSounds()
        g.next_spawn = float("inf")
        g.ents = []
        ion = g.ions[0]
        ion.y = g.surf([ion.curve], ion.x) + game_mod.R + height
        ion.vx = ion.vy = 0.0
        for _ in range(int(2 / game_mod.STEP)):
            g.ion_physics(ion, game_mod.STEP)
            if g.sounds.impacts:
                break
        return max(g.sounds.impacts)

    low, high = drop(20), drop(300)
    assert low < high
    # free fall at G from that height, give or take the slope and damping
    assert 0.8 * (2 * game_mod.G * 300) ** 0.5 < high < 1.1 * (2 * game_mod.G * 300) ** 0.5


def test_beams_and_strays_are_ambient_sources_only_in_a_running_match(make_game):
    g = make_game()
    g.next_spawn = float("inf")
    ion = g.ions[0]
    g.ents = [
        game_mod.Ent(type="laser", x=g.cam_x + 200, dir=1),
        game_mod.Ent(type="laser", x=g.cam_x + 1100, dir=-1),
        game_mod.Ent(type="stray", x=ion.x + 30, y=ion.y, vx=0.0, vy=0.0, active=True, color=game_mod.STRAY_C),
        game_mod.Ent(type="stray", x=g.cam_x + 2000, y=0.0, vx=0.0, vy=0.0, active=False,
                     color=game_mod.STRAY_C),
        game_mod.Ent(type="photon", x=ion.x, y=ion.y, ph=0.0),
    ]
    src = g.ambient_sources()
    kinds = [k for k, *_ in src]
    assert kinds == ["beam_up", "beam_down", "stray"]       # the inactive stray is still off screen
    (_, _, x_up, _), (_, _, x_down, _), (_, _, _, near_stray) = src
    assert x_up == 200 and x_down == 1100                    # screen x, for the pan
    assert near_stray > 0.8                                  # right next to the ion

    g.sounds = RecordingSounds()
    frame(g)
    assert g.sounds.ambient_calls[-1]                        # a running match hums
    g.state = "pause"
    assert g.ambient_sources() == []
    g.state = "menu"
    assert g.ambient_sources() == []


def test_the_sandbox_has_no_ambience(make_game):
    g = make_game(mode=game_mod.SANDBOX)
    g.ents = [game_mod.Ent(type="laser", x=300, dir=1)]
    assert g.ambient_sources() == []
