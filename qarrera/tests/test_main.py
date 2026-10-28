import asyncio

import pytest

from qarrera.main import parse_args


def test_defaults_are_a_windowed_dev_run():
    args = parse_args([])
    assert not args.fullscreen and not args.no_keyboard and not args.input_test
    assert args.window_size == "1440x810"


def test_a_pad_layout_can_be_picked():
    assert parse_args([]).pad_layout is None
    assert parse_args(["--pad-layout", "xbox"]).pad_layout == "xbox"


def test_the_cabinet_loader_flags_parse():
    args = parse_args(["--fullscreen", "--no-keyboard"])
    assert args.fullscreen and args.no_keyboard


def _run_frames(monkeypatch, n, on_frame):
    """The real game loop, drawing with OpenGL through SDL's offscreen driver
    (see test_render.py); on_frame(i) runs after each flip."""
    import pygame

    from qarrera import game, gfx

    real_open = gfx.open_window

    def open_window(size, fullscreen):
        try:
            return real_open(size, fullscreen)
        except RuntimeError as exc:
            pytest.skip(f"no OpenGL here: {exc}")

    monkeypatch.setattr(gfx, "open_window", open_window)
    frames = {"n": 0}
    real_flip = pygame.display.flip

    def flip():
        real_flip()
        frames["n"] += 1
        assert frames["n"] < n, "the loop didn't end"
        on_frame(frames["n"])

    monkeypatch.setattr(pygame.display, "flip", flip)
    try:
        asyncio.run(game.run(fullscreen=False, window_size="480x270", show_fps=True))
    finally:
        pygame.display.quit()
    return frames["n"]


def test_the_game_runs_and_quits(monkeypatch):
    import pygame

    def on_frame(i):
        if i == 30:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    assert _run_frames(monkeypatch, 100, on_frame) >= 30


def test_quit_on_the_title_ends_the_game_loop(monkeypatch):
    from qarrera.match import MENU_ROWS, Match

    real_update = Match.update

    def update(self, dt, inp):
        self.row = MENU_ROWS.index("QUIT")
        return real_update(self, dt, type(inp)(pick=True, activity=True))

    monkeypatch.setattr(Match, "update", update)
    assert _run_frames(monkeypatch, 50, lambda i: None) == 0  # A on QUIT: the loop ends before drawing


def test_in_the_browser_quit_goes_back_to_the_title(monkeypatch):
    """Start + Select tells the page and returns to the title instead of ending."""
    import pygame

    from qarrera import game
    from qarrera.input import Input
    from qarrera.match import TITLE

    sent = []
    browser = {"on": True}
    monkeypatch.setattr(game.runtime, "is_browser", lambda: browser["on"])
    monkeypatch.setattr(game.web, "post_event", lambda kind, game_id: sent.append(kind))
    combo = {"held": False}
    monkeypatch.setattr(Input, "quit_combo", lambda self: combo["held"])
    states = []
    real_draw = game.Renderer.draw

    def draw(self, match, events, dt):
        states.append(match.state)
        real_draw(self, match, events, dt)

    monkeypatch.setattr(game.Renderer, "draw", draw)

    def on_frame(i):
        combo["held"] = 5 <= i < 10
        if i == 20:  # a browser has no window to close, so stop being one to end the test
            browser["on"] = False
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    _run_frames(monkeypatch, 100, on_frame)
    assert sent == [game.web.QUIT]
    assert states[-1] == TITLE
