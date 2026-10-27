import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import asyncio  # noqa: E402

import pygame  # noqa: E402

from ion_surfer import game  # noqa: E402
from ion_surfer.input import Controls  # noqa: E402
from ion_surfer.main import parse_args  # noqa: E402


def test_the_cabinet_loader_flags_parse():
    args = parse_args(["--fullscreen", "--no-keyboard"])
    assert args.fullscreen and args.no_keyboard and args.pad_layout is None
    assert parse_args(["--pad-layout", "xbox"]).pad_layout == "xbox"


def _run_frames(monkeypatch, tmp_path, n, on_frame):
    """The real game loop on the dummy video driver; on_frame(i) runs after each flip."""
    frames = {"n": 0}
    real_flip = pygame.display.flip

    def flip():
        real_flip()
        frames["n"] += 1
        assert frames["n"] < n, "the loop didn't end"
        on_frame(frames["n"])

    monkeypatch.setattr(pygame.display, "flip", flip)
    monkeypatch.setattr(game, "SCORE_FILE", tmp_path / "scores.json")
    asyncio.run(game.run(window_size="600x320", show_fps=True))
    return frames["n"]


def test_the_game_runs_headless_and_quits(monkeypatch, tmp_path):
    def on_frame(i):
        if i == 30:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    assert _run_frames(monkeypatch, tmp_path, 100, on_frame) >= 30


def test_in_the_browser_quit_goes_back_to_the_menu(monkeypatch, tmp_path):
    """Start + Select tells the page and returns to the menu instead of ending."""
    sent = []
    browser = {"on": True}
    monkeypatch.setattr(game.runtime, "is_browser", lambda: browser["on"])
    monkeypatch.setattr(game.web, "post_event", lambda kind, game_id: sent.append(kind))
    combo = {"held": False}
    monkeypatch.setattr(Controls, "quit_combo", lambda self: combo["held"])

    def on_frame(i):
        combo["held"] = 5 <= i < 10
        if i == 40:  # a browser has no window to close, so stop being one to end the test
            browser["on"] = False
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    _run_frames(monkeypatch, tmp_path, 100, on_frame)
    assert sent == [game.web.QUIT]
