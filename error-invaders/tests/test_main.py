import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import asyncio  # noqa: E402

import pygame  # noqa: E402

from error_invaders import game  # noqa: E402
from error_invaders.input import Input  # noqa: E402
from error_invaders.main import parse_args  # noqa: E402


def test_the_cabinet_loader_flags_parse():
    args = parse_args(["--fullscreen", "--no-keyboard"])
    assert args.fullscreen and args.no_keyboard and args.pad_layout is None
    assert parse_args(["--pad-layout", "xbox"]).pad_layout == "xbox"


def _run_frames(monkeypatch, n, on_frame):
    """The real game loop on the dummy video driver; on_frame(i) runs after each flip."""
    frames = {"n": 0}
    real_flip = pygame.display.flip

    def flip():
        real_flip()
        frames["n"] += 1
        assert frames["n"] < n, "the loop didn't end"
        on_frame(frames["n"])

    monkeypatch.setattr(pygame.display, "flip", flip)
    monkeypatch.setattr(game, "HISCORE_FILE", None, raising=False)
    asyncio.run(game.run(window_size="480x360", show_fps=True))
    return frames["n"]


def test_the_game_runs_headless_and_quits(monkeypatch):
    def on_frame(i):
        if i == 30:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    assert _run_frames(monkeypatch, 100, on_frame) >= 30


def test_in_the_browser_quit_goes_back_to_the_title(monkeypatch):
    """Start + Select tells the page and returns to the title instead of ending."""
    sent = []
    browser = {"on": True}
    monkeypatch.setattr(game.runtime, "is_browser", lambda: browser["on"])
    monkeypatch.setattr(game.web, "post_event", lambda kind, game_id: sent.append(kind))
    combo = {"held": False}
    real_update = Input.update

    def update(self, dt):
        real_update(self, dt)
        self.quit_combo = combo["held"]

    monkeypatch.setattr(Input, "update", update)

    def on_frame(i):
        combo["held"] = 5 <= i < 10
        if i == 40:  # a browser has no window to close, so stop being one to end the test
            browser["on"] = False
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    _run_frames(monkeypatch, 100, on_frame)
    assert sent == [game.web.QUIT] and game.state == "title"
