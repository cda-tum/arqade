"""Tests for the CLI, the input-test screen and a headless run of the game loop."""

from __future__ import annotations

from brawl_ket import config
from brawl_ket.fighter import FighterInput
from brawl_ket.main import parse_args


def test_defaults_are_a_windowed_dev_run() -> None:
    args = parse_args([])
    assert not args.fullscreen and not args.no_keyboard and not args.input_test and not args.fps
    assert args.window_size == "1280x720"


def test_the_cabinet_loader_flags_parse() -> None:
    args = parse_args(["--fullscreen", "--no-keyboard"])
    assert args.fullscreen and args.no_keyboard


def test_the_input_test_screen_runs_and_leaves_on_quit() -> None:
    import pygame

    from brawl_ket.input_test import run_input_test

    pygame.init()
    surface = pygame.Surface((640, 360))
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    run_input_test(surface, None)


def test_the_game_runs_headless_and_quits(monkeypatch) -> None:
    """A real main loop, on the dummy video driver, for 30 frames."""
    import pygame

    from brawl_ket import game

    frames = {"n": 0}
    real_flip = pygame.display.flip

    def flip() -> None:
        real_flip()
        frames["n"] += 1
        if frames["n"] == 30:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    monkeypatch.setattr(pygame.display, "flip", flip)
    game.run(fullscreen=False, window_size="640x360", show_fps=True)
    assert frames["n"] >= 30


def test_the_default_window_is_a_whole_multiple_of_the_internal_size() -> None:
    w, h = (int(v) for v in parse_args([]).window_size.split("x"))
    assert w % config.INTERNAL_WIDTH == 0 and h % config.INTERNAL_HEIGHT == 0
    assert w // config.INTERNAL_WIDTH == h // config.INTERNAL_HEIGHT


def test_a_press_is_used_by_exactly_one_step() -> None:
    """Several steps in one frame must not repeat an edge press; none must not lose it."""
    from brawl_ket.game import consume, merge_pending

    idle = {"p1": FighterInput(), "p2": FighterInput()}
    press = {"p1": FighterInput(dx=1, a=True), "p2": FighterInput()}
    pending = merge_pending(idle, press)
    assert pending["p1"].a
    spent = consume(pending)
    assert not spent["p1"].a and spent["p1"].dx == 1            # the stick is still held
    # a frame with no step due: the next poll must not wipe the unspent press
    again = merge_pending(pending, {"p1": FighterInput(dx=1), "p2": FighterInput()})
    assert again["p1"].a
