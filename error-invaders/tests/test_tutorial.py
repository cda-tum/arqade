import pygame
import pytest

from error_invaders import game, input as input_mod, tutorial
from error_invaders.tutorial import MIN_SHOW, Tutorial, demo

DT = 1 / 60


class FakeInput:
    """One frame of input: `hits` are actions pressed this frame (both
    players), `start` is the Start button, `button` any new button press."""

    def __init__(self, *, start=False, select=False, hits=(), button=False):
        self.pause = self.confirm = start
        self.back = select
        self.hits = set(hits)
        self.ev_keys = set()
        self.back_held = 0.0
        self.any_button = button or start or select or bool(self.hits & {"fire", "swap"})
        self.swallowed = False

    def down(self, p, a): return a in self.hits
    def hit(self, p, a): return a in self.hits
    def any_hit(self, a): return a in self.hits
    def swallow(self): self.swallowed = True


@pytest.fixture
def title(monkeypatch):
    monkeypatch.setattr(game, "save_hiscores", lambda: None)
    monkeypatch.setattr(game, "mode", "easy")
    monkeypatch.setattr(game, "hiscores", {"easy": 0, "hard": 0, "rush": 0})
    game.menu.update(step=0, two=False, row=0)
    game.to_menu()
    yield
    game.menu.update(step=0, two=False, row=0)
    game.to_menu()


def frame(**kw):
    """One frame of the game loop's title / tutorial / play step. Returns
    False if the game quit."""
    game.inp = FakeInput(**kw)
    if game.state == "title":
        return game.step_title(DT)
    if game.state == "tutorial":
        game.step_tutorial(DT)
    elif game.state == "play":
        game.step_play(DT)
    elif game.state == "paused":
        game.step_paused()
    return True


def wait(seconds):
    for _ in range(round(seconds / DT)):
        frame()


# ------------------------------------------------------------ the card itself

def test_presses_in_the_first_moments_are_ignored():
    t = Tutorial()
    t.open()
    assert not t.step(DT, True)              # the A that picked the mode, bouncing
    for _ in range(round(MIN_SHOW / DT)):
        t.step(DT, False)
    assert t.step(DT, True)


def test_nothing_pressed_keeps_it_up():
    t = Tutorial()
    t.open()
    assert not any(t.step(DT, False) for _ in range(600))


def test_demo_corrects_red_then_purple_then_blue():
    def colors(t): return [c for _, _, c, _ in demo(t)["invaders"]]
    assert colors(0.1) == ["X", "Y", "Z"]
    assert colors(1.0) == ["Y", "Z"]                  # red shot corrected the red error
    assert colors(2.0) == ["Z", "Z"]                  # red turned the purple one blue
    assert colors(3.0) == ["Z"]                       # and blue corrected it
    assert colors(tutorial.LOOP - 0.1) == []
    assert colors(tutorial.LOOP + 0.1) == ["X", "Y", "Z"]   # it loops


def test_demo_lights_the_buttons_it_uses():
    assert demo(0.55)["lit"] == {"a"}
    assert demo(2.25)["lit"] == {"b"}
    assert demo(0.1)["lit"] == set()
    assert demo(2.3)["ship_col"] == "Z"


# ------------------------------------------------------------ title -> tutorial -> play

def to_tutorial(**first):
    frame(hits={"fire"})                     # 1 PLAYER
    assert game.menu["step"] == 1
    frame(**(first or dict(hits={"fire"})))  # EASY


def test_title_then_mode_then_tutorial_then_play(title):
    to_tutorial()
    assert game.state == "tutorial"
    assert game.g is not None and not game.g.two
    frame(hits={"fire"})                     # too soon: still up
    assert game.state == "tutorial"
    wait(MIN_SHOW)
    frame(hits={"left", "down"})             # the stick never dismisses it
    assert game.state == "tutorial"
    frame(hits={"fire"})
    assert game.state == "play"
    assert game.inp.swallowed                # the dismissing A doesn't also fire


def test_start_starts_from_the_title(title):
    frame(start=True)
    assert game.menu["step"] == 1
    frame(start=True)
    assert game.state == "tutorial"


def test_any_button_dismisses_and_start_does_not_pause(title):
    to_tutorial()
    wait(MIN_SHOW)
    frame(start=True)
    assert game.state == "play"
    frame()
    assert game.state == "play"


def test_the_game_does_not_run_behind_the_card(title):
    to_tutorial()
    before = (game.g.F.stepT, game.g.efT, game.g.players[0].inv)
    wait(2.0)
    assert (game.g.F.stepT, game.g.efT, game.g.players[0].inv) == before


def test_quit_to_title_then_a_new_match_shows_it_again(title):
    to_tutorial()
    wait(MIN_SHOW)
    frame(button=True)
    frame(start=True)                        # pause
    frame(hits={"down"})
    frame(hits={"fire"})                     # QUIT TO TITLE
    assert game.state == "title"
    to_tutorial()
    assert game.state == "tutorial"


# ------------------------------------------------------------ QUIT on the title

def test_quit_is_the_last_row_and_a_quits(title):
    assert game.TITLE_ROWS[-1] == "QUIT"
    frame(hits={"down"})
    frame(hits={"down"})
    assert game.TITLE_ROWS[game.menu["row"]] == "QUIT"
    assert frame(hits={"fire"}) is False


def test_start_on_quit_starts_instead(title):
    frame(hits={"up"})                       # wraps to QUIT
    assert game.TITLE_ROWS[game.menu["row"]] == "QUIT"
    assert frame(start=True) is True
    assert game.menu["step"] == 1 and not game.menu["two"]


def test_b_on_the_first_page_does_not_quit(title):
    frame(hits={"up"})
    assert frame(hits={"swap"}) is True
    assert frame(select=True) is True
    assert game.state == "title" and game.menu["step"] == 0


def test_b_goes_back_from_the_mode_page(title):
    frame(hits={"down"})                     # 2 PLAYERS
    frame(hits={"fire"})
    assert game.menu["two"]
    frame(hits={"swap"})
    assert game.menu["step"] == 0 and game.menu["row"] == 1


# ------------------------------------------------------------ swallowing held buttons

class FakeJoy:
    def __init__(self): self.buttons = set()
    def get_numaxes(self): return 2
    def get_axis(self, i): return 0.0
    def get_numhats(self): return 0
    def get_numbuttons(self): return 12
    def get_button(self, i): return i in self.buttons


def test_a_held_through_the_dismissal_does_nothing_until_released(monkeypatch):
    monkeypatch.setattr(pygame.joystick, "get_count", lambda: 0)
    input_mod.set_keyboard_enabled(False)
    try:
        inp = input_mod.Input()
        joy = FakeJoy()
        inp.pads.pad = lambda slot: joy if slot == 0 else None   # P1's pad
        fire = inp.pad_layout.buttons["a"]
        joy.buttons.add(fire)
        inp.update(DT)
        inp.swallow()
        assert not inp.down("p1", "fire") and not inp.hit("p1", "fire")
        inp.update(DT)
        assert not inp.down("p1", "fire")
        joy.buttons.clear()
        inp.update(DT)
        joy.buttons.add(fire)
        inp.update(DT)
        assert inp.hit("p1", "fire") and inp.down("p1", "fire")
    finally:
        input_mod.set_keyboard_enabled(True)
