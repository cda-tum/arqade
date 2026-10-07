from planck_time.main import parse_args


def test_defaults_are_a_windowed_dev_run():
    args = parse_args([])
    assert not args.fullscreen and not args.no_keyboard and not args.input_test


def test_boss_every_defaults_to_the_config():
    from planck_time import config

    assert parse_args([]).boss_every == config.BOSS_EVERY
    assert parse_args(["--boss-every", "1"]).boss_every == 1


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
    game.run(fullscreen=False, window_size="640x360", show_fps=True)
    assert frames["n"] >= 30


def test_the_default_window_is_a_whole_multiple_of_the_internal_size():
    from planck_time import config

    w, h = (int(v) for v in parse_args([]).window_size.split("x"))
    assert w % config.INTERNAL_WIDTH == 0 and h % config.INTERNAL_HEIGHT == 0
    assert w // config.INTERNAL_WIDTH == h // config.INTERNAL_HEIGHT
