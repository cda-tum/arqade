import asyncio

from gate_drop.main import parse_args


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


def test_the_input_test_screen_runs_and_leaves_on_quit():
    import pygame

    from gate_drop.input_test import run_input_test

    pygame.init()
    surface = pygame.Surface((480, 270))
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    run_input_test(surface, None)


def _run_frames(monkeypatch, n, on_frame):
    """The real game loop on the dummy video driver; on_frame(i) runs after each flip."""
    import pygame

    from gate_drop import game

    frames = {"n": 0}
    real_flip = pygame.display.flip

    def flip():
        real_flip()
        frames["n"] += 1
        assert frames["n"] < n, "the loop didn't end"
        on_frame(frames["n"])

    monkeypatch.setattr(pygame.display, "flip", flip)
    asyncio.run(game.run(fullscreen=False, window_size="480x270", show_fps=True))
    return frames["n"]


def test_the_game_runs_headless_and_quits(monkeypatch):
    import pygame

    def on_frame(i):
        if i == 30:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    assert _run_frames(monkeypatch, 100, on_frame) >= 30


def test_in_the_browser_quit_goes_back_to_the_title(monkeypatch):
    """Start + Select tells the page and returns to the title instead of ending."""
    import pygame

    from gate_drop import game
    from gate_drop.input import Input

    sent = []
    browser = {"on": True}
    monkeypatch.setattr(game.runtime, "is_browser", lambda: browser["on"])
    monkeypatch.setattr(game.web, "post_event", lambda kind, game_id: sent.append(kind))
    combo = {"held": False}
    monkeypatch.setattr(Input, "quit_combo", lambda self: combo["held"])

    def on_frame(i):
        combo["held"] = 5 <= i < 10
        if i == 40:  # a browser has no window to close, so stop being one to end the test
            browser["on"] = False
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    _run_frames(monkeypatch, 100, on_frame)
    assert sent == [game.web.QUIT]
