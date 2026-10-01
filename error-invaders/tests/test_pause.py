import pytest

from error_invaders import game
from error_invaders.game import Obj
from error_invaders.pause import ITEMS, PauseMenu


class FakeInput:
    """Just enough of input.Input for one frame: `hits` are the actions
    pressed this frame (for both players), Start sets pause and confirm."""

    def __init__(self, *, start=False, hits=()):
        self.pause = self.confirm = start
        self.back = False
        self.hits = set(hits)

    def down(self, p, a): return a in self.hits
    def hit(self, p, a): return a in self.hits
    def any_hit(self, a): return a in self.hits


@pytest.fixture
def playing(monkeypatch):
    monkeypatch.setattr(game, "save_hiscores", lambda: None)
    monkeypatch.setattr(game, "mode", "easy")
    monkeypatch.setattr(game, "hiscores", {"easy": 0, "hard": 0, "rush": 0})
    game.new_game(False)
    game.g.pb.append(Obj(x=400.0, y=400.0, vx=0, vy=-640, kind="n", col="X", owner="p1"))
    yield game.g
    game.to_menu()


def frame(start=False, hits=(), dt=1 / 60):
    game.inp = FakeInput(start=start, hits=hits)
    if game.state == "play": game.step_play(dt)
    elif game.state == "paused": game.step_paused()


def snapshot(g):
    return (g.pb[0].y, g.F.stepT, g.efT, g.ufoT, g.players[0].inv, g.players[0].x)


def test_menu_selection_moves_and_wraps():
    m = PauseMenu()
    assert m.item == "RESUME"
    assert m.step(move=1, pick=False, resume=False) == "move"
    assert m.item == "QUIT TO TITLE"
    m.step(move=1, pick=False, resume=False)
    assert m.item == ITEMS[0]
    m.step(move=-1, pick=False, resume=False)
    assert m.item == ITEMS[-1]
    m.open()
    assert m.item == "RESUME"


def test_menu_pick_and_resume():
    m = PauseMenu()
    assert m.step(move=0, pick=False, resume=False) is None
    assert m.step(move=0, pick=True, resume=False) == "resume"
    m.step(move=1, pick=False, resume=False)
    assert m.step(move=0, pick=True, resume=False) == "title"
    assert m.step(move=0, pick=False, resume=True) == "resume"


def test_start_pauses_and_everything_freezes(playing):
    frame()
    assert game.state == "play"
    frame(start=True)
    assert game.state == "paused"
    before = snapshot(playing)
    for _ in range(120):
        frame(hits={"left"})    # holding the stick moves nothing while paused
    assert game.state == "paused"
    assert snapshot(playing) == before


@pytest.mark.parametrize("resume", [dict(start=True), dict(hits={"swap"}), dict(hits={"fire"})])
def test_start_b_or_a_on_resume_resumes(playing, resume):
    frame(start=True)
    frame(**resume)
    assert game.state == "play"
    y = playing.pb[0].y
    frame()
    assert playing.pb[0].y < y           # the game runs again


def test_a_on_quit_to_title_goes_to_the_title_without_a_score(playing):
    playing.score = 12345
    frame(start=True)
    frame(hits={"down"})
    assert game.pause_menu.item == "QUIT TO TITLE"
    frame(hits={"fire"})
    assert game.state == "title"
    assert game.hiscores["easy"] == 0


def test_every_pause_opens_on_resume(playing):
    frame(start=True)
    frame(hits={"down"})
    frame(start=True)                    # resume
    frame(start=True)                    # pause again
    assert game.pause_menu.item == "RESUME"
