"""The main menu's QUIT row and the HOW TO PLAY card before a match, driven by
the cabinet's raw joystick events like test_game.py."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from ion_surfer import game as game_mod  # noqa: E402
from ion_surfer import tutorial  # noqa: E402
from ion_surfer.config import INPUT_CONFIG  # noqa: E402
from ion_surfer.input import set_keyboard_enabled  # noqa: E402

START = INPUT_CONFIG["system"]["start_button"]    # raw 9
SELECT = INPUT_CONFIG["system"]["select_button"]  # raw 8
A = INPUT_CONFIG["p1"]["buttons"]["confirm"][0]    # raw 1 (also "right" in play)
B = INPUT_CONFIG["p1"]["buttons"]["back"][0]       # raw 2
L = 4                                              # printed L, raw 4
Y_AXIS = INPUT_CONFIG["p1"]["axes"][1]
X_AXIS = INPUT_CONFIG["p1"]["axes"][0]


class FakeSounds:
    def __init__(self):
        self.played = []

    def play(self, name):
        self.played.append(name)

    def impact(self, speed):
        self.played.append("bounce")

    def ambient(self, sources, dt):
        pass


@pytest.fixture
def make_menu(tmp_path, monkeypatch):
    monkeypatch.setattr(game_mod, "SCORE_FILE", tmp_path / "scores.json")
    pygame.init()

    def make():
        g = game_mod.Game(pygame.Surface((game_mod.W, game_mod.H)), sounds=FakeSounds())
        g.controls.joys = {0: (None, 0), 1: (None, 1)}
        return g

    yield make
    set_keyboard_enabled(True)
    pygame.quit()


def frame(g, *events, dt=1 / 60):
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


def axis(value, ax=Y_AXIS, pad=0):
    return pygame.event.Event(pygame.JOYAXISMOTION, instance_id=pad, axis=ax, value=value)


def tap(g, button, pad=0):
    frame(g, down(button, pad))
    frame(g, up(button, pad))


def wait(g, seconds):
    for _ in range(round(seconds * 60)):
        frame(g)


def select_row(g, label):
    while g.MAIN_ITEMS[g.menu_sel] != label:
        frame(g, axis(1.0))
        frame(g, axis(0.0))


def to_tutorial(g, row="1 PLAYER"):
    select_row(g, row)
    tap(g, A)
    assert g.state == "tutorial"


# ---------- QUIT on the main menu ----------
def test_quit_is_the_last_row_of_the_main_menu(make_menu):
    assert make_menu().MAIN_ITEMS[-1] == "QUIT"


def test_a_on_quit_quits(make_menu):
    g = make_menu()
    select_row(g, "QUIT")
    tap(g, A)
    assert not g.running


def test_start_on_quit_starts_a_match_instead(make_menu):
    g = make_menu()
    select_row(g, "QUIT")
    tap(g, START)
    assert g.running
    assert g.state == "tutorial" and g.mode == 1


def test_start_starts_the_selected_mode(make_menu):
    g = make_menu()
    select_row(g, "2 PLAYERS: CO-OP")
    tap(g, START)
    assert g.state == "tutorial" and g.mode == 3


def test_b_on_the_main_menu_does_nothing(make_menu):
    g = make_menu()
    select_row(g, "QUIT")
    tap(g, B)
    assert g.running and g.state == "menu"


def test_menu_moves_make_a_sound(make_menu):
    g = make_menu()
    select_row(g, "SANDBOX")
    assert "move" in g.sounds.played


# ---------- the HOW TO PLAY card ----------
@pytest.mark.parametrize("row,mode", [("1 PLAYER", 1), ("2 PLAYERS: VERSUS", 2),
                                      ("2 PLAYERS: CO-OP", 3), ("SANDBOX", game_mod.SANDBOX)])
def test_every_mode_from_the_menu_opens_the_card_then_plays(make_menu, row, mode):
    g = make_menu()
    to_tutorial(g, row)
    assert g.mode == mode
    wait(g, 0.5)
    tap(g, L)
    assert g.state == "play"
    assert g.sounds.played[-1] == "start"


def test_presses_in_the_first_moment_are_ignored(make_menu):
    g = make_menu()
    to_tutorial(g)
    tap(g, A)  # the bounce of the A that picked the mode
    wait(g, tutorial.MIN_AGE / 2)
    tap(g, START)
    assert g.state == "tutorial"
    wait(g, tutorial.MIN_AGE)
    tap(g, A)
    assert g.state == "play"


def test_the_stick_does_not_dismiss_it(make_menu):
    g = make_menu()
    to_tutorial(g)
    wait(g, 1.0)
    for ax in (X_AXIS, Y_AXIS):
        frame(g, axis(1.0, ax))
        frame(g, axis(-1.0, ax))
        frame(g, axis(0.0, ax))
    assert g.state == "tutorial"


def test_any_button_on_either_pad_dismisses_it(make_menu):
    for button, pad in ((7, 1), (B, 0), (L, 1)):  # raw 7 isn't mapped at all
        g = make_menu()
        to_tutorial(g)
        wait(g, 0.5)
        tap(g, button, pad)
        assert g.state == "play"


def test_the_world_waits_behind_the_card(make_menu):
    g = make_menu()
    to_tutorial(g)
    wait(g, 2.0)
    assert g.cam_x == 0.0 and g.t == 0.0


def test_the_dismissing_press_does_not_act_in_the_match(make_menu):
    # A is also "right" in play: held on, it would auto-repeat the cursor.
    g = make_menu()
    to_tutorial(g)
    wait(g, 0.5)
    frame(g, down(A))
    assert g.state == "play"
    sel = g.cursors[0].sel
    wait(g, 1.0)
    assert g.cursors[0].sel == sel
    frame(g, up(A))
    tap(g, A)  # a fresh press does move it
    assert g.cursors[0].sel == sel + 1


def test_start_plus_select_quits_from_the_card(make_menu):
    g = make_menu()
    to_tutorial(g)
    assert frame(g, down(START), down(SELECT)) is False


def test_start_dismissing_does_not_break_the_quit_combo(make_menu):
    g = make_menu()
    to_tutorial(g)
    wait(g, 0.5)
    frame(g, down(START))
    assert g.state == "play"
    assert frame(g, down(SELECT)) is False


def test_keyboard_dismisses_only_with_the_keyboard_on(make_menu):
    key = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_k, unicode="k")
    g = make_menu()
    to_tutorial(g)
    wait(g, 0.5)
    set_keyboard_enabled(False)
    frame(g, key)
    assert g.state == "tutorial"
    set_keyboard_enabled(True)
    frame(g, key)
    assert g.state == "play"


def test_restart_and_rematches_skip_the_card(make_menu):
    g = make_menu()
    to_tutorial(g)
    wait(g, 0.5)
    tap(g, A)
    tap(g, START)                    # pause
    frame(g, axis(1.0))
    frame(g, axis(0.0))              # RESTART
    tap(g, A)
    assert g.state == "play"
    g.game_over()
    tap(g, A)                        # SAME SEED
    assert g.state == "play"


def test_quit_to_title_then_a_new_match_shows_it_again(make_menu):
    g = make_menu()
    to_tutorial(g)
    wait(g, 0.5)
    tap(g, A)
    tap(g, START)
    for _ in range(g.PAUSE_ITEMS.index("QUIT TO TITLE")):
        frame(g, axis(1.0))
        frame(g, axis(0.0))
    tap(g, A)
    assert g.state == "menu"
    to_tutorial(g)


def test_sandbox_shortcut_skips_it(make_menu):
    g = game_mod.Game(pygame.Surface((game_mod.W, game_mod.H)), sandbox_only=True)
    assert g.state == "play"


@pytest.mark.parametrize("mode", [1, 2, 3, game_mod.SANDBOX])
def test_the_card_draws_and_its_demo_loops(make_menu, mode):
    g = make_menu()
    g.open_tutorial(mode)
    for _ in range(int(tutorial.LOOP * 60) + 30):
        g.update(1 / 60)
        g.controls.begin_frame()
    g.draw()
    assert g.state == "tutorial"
    assert g.tutorial.demo.t < 1.0  # it started over


def test_the_demo_does_not_touch_the_global_random_state(make_menu):
    import random
    g = make_menu()
    g.open_tutorial(1)  # picks the match's seed, as it should
    random.seed(5)
    expected = [random.random() for _ in range(3)]
    random.seed(5)
    for _ in range(240):
        g.update(1 / 60)
    assert [random.random() for _ in range(3)] == expected


def test_the_solo_demo_surfs_and_collects_photons(make_menu):
    demo = tutorial.Demo(1)
    for _ in range(4 * 60):
        demo.update(1 / 60)
    ion = demo.world.ions[0]
    assert ion.x > 600 and ion.bonus > 0 and ion.lives == 3


def test_the_core_events_make_sounds(make_menu):
    g = make_menu()
    g.start(game_mod.SANDBOX)
    tap(g, SELECT, pad=1)            # laser kick
    tap(g, 5)                        # blue R: add an ion
    g.start(1)
    ion = g.ions[0]
    g.ents.append(game_mod.Ent(type="photon", x=ion.x, y=ion.y, ph=0.0))
    frame(g)
    g.lose(ion, "ION LOST")
    assert {"kick", "ion_add", "photon", "lost"} <= set(g.sounds.played)
