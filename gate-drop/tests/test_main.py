from gate_drop.main import parse_args


def test_defaults_are_a_windowed_dev_run():
    args = parse_args([])
    assert not args.fullscreen and not args.no_keyboard and not args.input_test
    assert args.window_size == "1440x810"


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
