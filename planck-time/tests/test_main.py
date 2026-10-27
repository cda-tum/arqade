import asyncio

from planck_time.main import parse_args


def test_defaults_are_a_windowed_dev_run():
    args = parse_args([])
    assert not args.fullscreen and not args.no_keyboard and not args.input_test


def test_boss_every_defaults_to_the_config():
    from planck_time import config

    assert parse_args([]).boss_every == config.BOSS_EVERY
    assert parse_args(["--boss-every", "1"]).boss_every == 1


def test_a_pad_layout_can_be_picked():
    assert parse_args([]).pad_layout is None
    assert parse_args(["--pad-layout", "xbox"]).pad_layout == "xbox"


def test_the_cabinet_loader_flags_parse():
    args = parse_args(["--fullscreen", "--no-keyboard"])
    assert args.fullscreen and args.no_keyboard


def test_the_input_test_screen_runs_and_leaves_on_quit():
    import pygame

    from planck_time.input_test import run_input_test

    pygame.init()
    surface = pygame.Surface((640, 360))
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    run_input_test(surface, None)


def test_the_game_runs_headless_and_quits(monkeypatch):
    """A real main loop, on the dummy video driver, for a few frames."""
    import pygame

    from planck_time import game

    frames = {"n": 0}
    real_flip = pygame.display.flip

    def flip():
        real_flip()
        frames["n"] += 1
        if frames["n"] == 30:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    monkeypatch.setattr(pygame.display, "flip", flip)
    monkeypatch.setattr(game.config, "SCORE_FILE", None)
    asyncio.run(game.run(fullscreen=False, window_size="640x360", show_fps=True))
    assert frames["n"] >= 30


def test_the_default_window_is_a_whole_multiple_of_the_internal_size():
    from planck_time import config

    w, h = (int(v) for v in parse_args([]).window_size.split("x"))
    assert w % config.INTERNAL_WIDTH == 0 and h % config.INTERNAL_HEIGHT == 0
    assert w // config.INTERNAL_WIDTH == h // config.INTERNAL_HEIGHT


def test_quit_on_the_title_ends_the_game_loop(monkeypatch):
    """Down to QUIT, A: run() returns, the same clean exit as Start + Select."""
    from planck_time import game
    from planck_time.input import Input
    from planck_time.session import FrameInput

    script = iter([{"nav": {"p1": (0, 1), "p2": (0, 0)}}, {"nav": {"p1": (0, 1), "p2": (0, 0)}},
                   {"confirms": {"p1": True, "p2": False}}])
    frames = {"n": 0}

    def frame_input(self):
        frames["n"] += 1
        assert frames["n"] < 100, "QUIT didn't quit"
        return FrameInput(activity=True, **next(script, {}))

    monkeypatch.setattr(Input, "frame_input", frame_input)
    monkeypatch.setattr(game.config, "SCORE_FILE", None)
    asyncio.run(game.run(fullscreen=False, window_size="640x360", show_fps=False))
    assert frames["n"] == 3
