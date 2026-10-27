import asyncio

from qurves.main import parse_args


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


def test_quit_on_the_title_ends_the_game_loop(monkeypatch):
    from arqade_common.input import LastDevice

    from qurves import game
    from qurves.match import FrameInput

    script = iter([FrameInput(), FrameInput(nav=(0, 1), activity=True), FrameInput(confirm=True, pick=True)])

    class ScriptedInput:
        select_held_time = 0.0

        def __init__(self, pad_layout=None):
            self.devices = LastDevice()

        def handle(self, event):
            pass

        def update(self, dt):
            pass

        def quit_combo(self):
            return False

        def frame_input(self):
            return next(script)  # running past the script would raise StopIteration

    monkeypatch.setattr(game, "Input", ScriptedInput)
    asyncio.run(game.run(fullscreen=False, window_size="320x180", show_fps=False))  # returns: the loop exited


def _run_frames(monkeypatch, n, on_frame):
    """The real game loop on the dummy video driver; on_frame(i) runs after each flip."""
    import pygame

    from qurves import game

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

    from qurves import game
    from qurves.input import Input

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
