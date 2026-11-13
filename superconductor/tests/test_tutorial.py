import asyncio
import os

import pygame
import pytest

from superconductor import tutorial
from superconductor.tutorial import SCENES, ScenePlayer, dismisses

DT = 1 / 60


def play_scene(name):
    """Run one scene to its end; every event it raised, and the frames the
    red X was up."""
    p = ScenePlayer((name,))
    events, x_up = [], 0
    while p.time + DT < p.scene.length:
        p.update(DT)
        events += p.board.events
        p.board.events.clear()
        if p.board.predict_collision("p1") is not None:
            x_up += 1
    return p, [e.kind for e in events], x_up


# ---------------------------------------------------------------- scenes
def test_every_scene_shows_what_its_caption_says():
    _, pair, _ = play_scene("pair")
    assert "routed" in pair and "gate" in pair
    _, coherence, _ = play_scene("coherence")
    assert "decohere" in coherence
    _, defect, _ = play_scene("defect")
    assert "blocked" in defect and "routed" in defect
    _, speed, _ = play_scene("speed")
    assert "boost" in speed and "gate" in speed
    _, bell, _ = play_scene("bell")
    assert "teleport" in bell and "routed" in bell


def test_red_x_scene_waits_out_the_x_and_never_crashes():
    _, kinds, x_up = play_scene("red_x")
    assert x_up > 60  # up for over a second, long enough to read
    assert "crash" not in kinds
    assert kinds.count("routed") == 2 and "gate" in kinds


def test_miscalibrated_scene_costs_fidelity():
    p = ScenePlayer(("miscal",))
    gates = []
    while p.time + DT < p.scene.length:
        p.update(DT)
        gates += [e for e in p.board.events if e.kind == "gate"]
        p.board.events.clear()
    assert len(gates) == 1 and gates[0].fidelity == pytest.approx(0.8)


def test_no_scene_costs_a_crash_or_uses_red_for_a_pair():
    for name in SCENES:
        _, kinds, _ = play_scene(name)
        assert "crash" not in kinds, name
        assert all(s[4] != 0 for s in SCENES[name].spawns), name  # 0 is red, the X's colour


def test_scenes_loop_in_order():
    p = ScenePlayer(("pair", "speed"))
    first = p.board
    for _ in range(int(SCENES["pair"].length / DT) + 2):
        p.update(DT)
    assert p.scene.name == "SPEED QUBIT" and p.board is not first
    for _ in range(int(SCENES["speed"].length / DT) + 2):
        p.update(DT)
    assert p.scene.name == "PAIR"


def test_legend_and_how_to_play_use_known_scenes():
    assert set(tutorial.LEGEND) <= set(SCENES)
    assert set(tutorial.HOW_TO_PLAY) <= set(SCENES)
    assert tutorial.HOW_TO_PLAY[0] == "pair"


# ---------------------------------------------------------------- dismissing
def test_any_button_dismisses_after_the_grace_time():
    assert not dismisses("button", 0.0, False)
    assert not dismisses("button", tutorial.MIN_SHOW - 0.01, False)
    assert dismisses("button", tutorial.MIN_SHOW, False)


def test_keys_dismiss_only_with_the_keyboard_on():
    assert dismisses("key", 1.0, True)
    assert not dismisses("key", 1.0, False)


def test_stick_never_dismisses():
    assert not dismisses("stick", 5.0, True)


# ---------------------------------------------------------------- the game's flow
@pytest.fixture
def game(tmp_path, monkeypatch):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    from superconductor import config
    from superconductor import game as game_mod

    monkeypatch.setattr(config, "HISCORE_FILE", tmp_path / "hiscores.json")
    g = game_mod.Game(False, "320x180", False)
    yield g
    pygame.quit()


def frame(g, update, *, confirm=False, hit=None, presses=()):
    """One frame of `update`, with these inputs."""
    inp = g.inp
    inp.update(DT)
    inp.confirm = inp.pause = confirm
    if hit:
        inp.pressed["p1"].add(hit)
    inp.presses.update(presses)
    g.t += DT
    g.state_t += DT
    update(DT)
    inp.end_frame()


def test_start_goes_through_how_to_play_into_the_match(game):
    frame(game, game.update_title, confirm=True)
    assert game.state == "tutorial"
    frame(game, game.update_tutorial, presses={"button"})  # the bounce: too early
    assert game.state == "tutorial"
    for _ in range(int(tutorial.MIN_SHOW / DT) + 1):
        frame(game, game.update_tutorial)
    assert game.state == "tutorial"  # waits for a button, however long
    frame(game, game.update_tutorial, presses={"button"})
    assert game.state == "play"


class FakePad:
    """A cabinet pad with some raw buttons held, the stick centred."""

    def __init__(self):
        self.down = set()

    def get_numbuttons(self):
        return 12

    def get_button(self, i):
        return i in self.down

    def get_numaxes(self):
        return 2

    def get_axis(self, i):
        return 0.0

    def get_numhats(self):
        return 0


def test_dismissing_press_does_not_act_in_the_match(game):
    frame(game, game.update_title, confirm=True)
    game.state_t = 1.0
    board = game.views[0].board
    board.update(0.01)
    board.update(0.6)  # both opening pairs are there
    station = list(board.cursors["p1"].path)
    pad = FakePad()
    game.inp.pads.pad = lambda slot: pad if slot == 0 else None  # P1's pad
    pad.down.add(1)  # printed A goes down: it closes the card...
    frame(game, game.update_tutorial, presses={"button"})
    assert game.state == "play"
    for _ in range(3):  # ...and, still held, does nothing in the match
        frame(game, game.update_play)
        assert board.cursors["p1"].path == station
    pad.down.clear()
    frame(game, game.update_play)
    pad.down.add(1)  # a fresh press of A is "next pair" again
    frame(game, game.update_play)
    assert board.cursors["p1"].path != station


def test_a_starts_from_mode_and_chip_rows(game):
    for row in (0, 1):
        game.set_state("title")
        game.menu_row = row
        frame(game, game.update_title, hit="next")
        assert game.state == "tutorial" and not game.quit_requested


def test_quit_is_the_last_row_and_a_on_it_quits(game):
    from superconductor.game import MENU_ROWS

    assert MENU_ROWS[-1] == "quit"
    for _ in range(5):  # the stick clamps on QUIT, it doesn't wrap round
        game.inp.move["p1"] = "down"
        game.update_title(DT)
    assert MENU_ROWS[game.menu_row] == "quit"
    frame(game, game.update_title, hit="next")
    assert game.quit_requested and game.state == "title"


def test_start_on_quit_still_plays(game):
    game.menu_row = 2
    frame(game, game.update_title, confirm=True)
    assert game.state == "tutorial" and not game.quit_requested


def test_b_on_the_title_does_not_quit(game):
    game.menu_row = 2
    frame(game, game.update_title, hit="other")
    assert game.state == "title" and not game.quit_requested


def test_back_to_title_never_lands_on_quit(game):
    game.menu_row = 2
    frame(game, game.update_title, confirm=True)
    game.to_menu()
    assert game.menu_row == 0


def test_quit_leaves_the_loop(game, monkeypatch):
    # the real loop: A on QUIT (P1's key B) must return from run()
    from superconductor import game as game_mod

    frames = []

    def draw_title(self, S):
        frames.append(1)
        if len(frames) > 30:
            raise AssertionError("QUIT did not leave the loop")

    monkeypatch.setattr(game_mod.Game, "draw_title", draw_title)
    game.menu_row = 2
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_b, mod=0, unicode="b", scancode=0))
    asyncio.run(game.run())
    assert game.quit_requested


def test_in_the_browser_quit_goes_back_to_the_title(game, monkeypatch):
    """A on QUIT tells the page and returns to the title instead of ending."""
    from superconductor import game as game_mod

    sent = []
    browser = {"on": True}
    monkeypatch.setattr(game_mod.runtime, "is_browser", lambda: browser["on"])
    monkeypatch.setattr(game_mod.web, "post_event", lambda kind, game_id: sent.append(kind))
    frames = []

    def draw_title(self, S):
        frames.append(1)
        assert len(frames) < 60, "the loop didn't end"
        if len(frames) == 20:  # a browser has no window to close, so stop being one to end the test
            browser["on"] = False
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    monkeypatch.setattr(game_mod.Game, "draw_title", draw_title)
    game.menu_row = 2
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_b, mod=0, unicode="b", scancode=0))
    asyncio.run(game.run())
    assert sent == [game_mod.web.QUIT] and game.state == "title" and len(frames) >= 20


# ---------------------------------------------------------------- control hints
def use_devices(game, p1, p2):
    game.inp.devices._devices.update(p1=p1, p2=p2)


def test_mixed_devices_get_a_hint_line_each(game):
    from arqade_common.input import KEYBOARD, PAD
    use_devices(game, KEYBOARD, PAD)
    assert game.hint_lines(lambda p: f"{game.name('a', p)}: OK") == ["P1 KEYS  B: OK", "P2 PAD  A: OK"]
    use_devices(game, KEYBOARD, KEYBOARD)
    assert game.hint_lines(lambda p: f"{game.name('a', p)}: OK") == ["B / L: OK"]
    use_devices(game, PAD, PAD)
    assert game.hint_lines(lambda p: f"{game.name('a', p)}: OK") == ["A: OK"]


@pytest.mark.parametrize("mode", ["single", "coop", "versus"])
@pytest.mark.parametrize("devices", [("keyboard", "keyboard"), ("keyboard", "pad"), ("pad", "keyboard")])
def test_every_screen_draws_for_keyboard_players(game, monkeypatch, mode, devices):
    from superconductor import game as game_mod
    monkeypatch.setattr(game_mod, "_fonts", {})  # fonts from an earlier pygame.init() are dead
    monkeypatch.setattr(game_mod, "_text_cache", {})
    use_devices(game, *devices)
    game.mode = mode
    S = pygame.Surface((320, 180))
    for row in range(3):
        game.menu_row = row
        game.draw_title(S)
    game.start_game()
    game.state_t = 3.0
    for draw in (game.draw_tutorial, game.draw_play, game.draw_paused, game.draw_over):
        draw(S)
