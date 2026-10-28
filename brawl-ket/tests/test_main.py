"""Tests for the CLI, the input-test screen and a headless run of the game loop."""

from __future__ import annotations

import asyncio

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


def test_a_pad_layout_can_be_picked() -> None:
    assert parse_args([]).pad_layout is None
    assert parse_args(["--pad-layout", "xbox"]).pad_layout == "xbox"


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
    asyncio.run(game.run(fullscreen=False, window_size="640x360", show_fps=True))
    assert frames["n"] >= 30


def test_quit_on_the_title_ends_the_game_loop(monkeypatch) -> None:
    """Up (round to the last row), then A: the loop returns, the way Start + Select leaves it."""
    import pygame

    from brawl_ket import game

    real_update = game.Input.update
    frames = {"n": 0}

    def update(self, dt):
        real_update(self, dt)
        frames["n"] += 1
        if frames["n"] == 3:
            self.frame.nav["p1"] = (0, -1)
        elif frames["n"] == 5:
            self.frame.confirms["p1"] = True
        elif frames["n"] > 120:             # never got out: fail rather than hang
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    monkeypatch.setattr(game.Input, "update", update)
    asyncio.run(game.run(fullscreen=False, window_size="640x360", show_fps=False))
    assert frames["n"] < 30


def test_in_the_browser_the_page_hears_a_match_and_quitting_goes_back_to_the_title(monkeypatch) -> None:
    """Through the menus into a round (arqade:game-start), then Start + Select: the match ends
    (arqade:game-end), the page is told (arqade:quit), and the game carries on at its title."""
    import pygame

    from brawl_ket import game
    from brawl_ket import match as M

    sent = []
    browser = {"on": True}
    monkeypatch.setattr(game.runtime, "is_browser", lambda: browser["on"])
    monkeypatch.setattr(game.web, "post_event", lambda kind, game_id: sent.append(kind))
    matches = []

    class Recorded(M.Match):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            matches.append(self)

    monkeypatch.setattr(game, "Match", Recorded)
    real_update = game.Input.update
    script = {"n": 0, "quit": 0}

    def update(self, dt):
        real_update(self, dt)
        script["n"] += 1
        assert script["n"] < 900, "the script got stuck"
        m = matches[0]
        tap = script["n"] % 2 == 0                  # a fresh press every other frame
        if script["quit"]:                          # Start + Select held a few frames, then let go
            script["quit"] += 1
            if script["quit"] < 6:
                self.start_select["p1"] = (True, True)
            elif m.state == M.TITLE and script["quit"] == 20:
                browser["on"] = False               # a browser has no window to close: stop being one
                pygame.event.post(pygame.event.Event(pygame.QUIT))
        elif m.state in (M.TITLE, M.SELECT, M.STAGE_SELECT) and tap:
            self.frame.confirms = {"p1": True, "p2": True}
        elif m.state == M.TUTORIAL and tap:
            self.frame.any_button = True
        elif m.state == M.FIGHT:
            script["quit"] = 1
            self.start_select["p1"] = (True, True)

    monkeypatch.setattr(game.Input, "update", update)
    asyncio.run(game.run(fullscreen=False, window_size="640x360", show_fps=False))
    assert sent == [game.web.GAME_START, game.web.GAME_END, game.web.QUIT]
    assert matches[0].state == M.TITLE and not matches[0].quit


def test_in_the_browser_quit_on_the_title_goes_back_to_the_title(monkeypatch) -> None:
    """A on QUIT tells the page and stays on the title instead of ending."""
    import pygame

    from brawl_ket import game

    sent = []
    browser = {"on": True}
    monkeypatch.setattr(game.runtime, "is_browser", lambda: browser["on"])
    monkeypatch.setattr(game.web, "post_event", lambda kind, game_id: sent.append(kind))
    real_update = game.Input.update
    frames = {"n": 0}

    def update(self, dt):
        real_update(self, dt)
        frames["n"] += 1
        if frames["n"] == 3:
            self.frame.nav["p1"] = (0, -1)          # up: round to QUIT
        elif frames["n"] == 5:
            self.frame.confirms["p1"] = True
        elif frames["n"] == 40:
            browser["on"] = False
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        assert frames["n"] < 120, "the loop did not end"

    monkeypatch.setattr(game.Input, "update", update)
    asyncio.run(game.run(fullscreen=False, window_size="640x360", show_fps=False))
    assert sent == [game.web.QUIT] and frames["n"] >= 40


def test_the_default_window_is_a_whole_multiple_of_the_internal_size() -> None:
    w, h = (int(v) for v in parse_args([]).window_size.split("x"))
    assert w % config.INTERNAL_WIDTH == 0 and h % config.INTERNAL_HEIGHT == 0
    assert w // config.INTERNAL_WIDTH == h // config.INTERNAL_HEIGHT


def test_a_press_is_used_by_exactly_one_step() -> None:
    """Several steps in one frame must not repeat an edge press; none must not lose it."""
    from brawl_ket.game import consume, merge_pending
    from brawl_ket.match import FrameInput

    press = FrameInput(fighters={"p1": FighterInput(dx=1, a=True), "p2": FighterInput()},
                       confirms={"p1": True, "p2": False}, nav={"p1": (0, 1), "p2": (0, 0)},
                       activity=True, any_button=True)
    pending = merge_pending(FrameInput(), press)
    assert pending.fighters["p1"].a and pending.confirms["p1"] and pending.nav["p1"] == (0, 1)
    assert pending.any_button
    spent = consume(pending)
    assert not spent.fighters["p1"].a and spent.fighters["p1"].dx == 1     # the stick is still held
    assert not spent.confirm and spent.nav["p1"] == (0, 0) and not spent.any_button
    assert spent.activity                                                 # holding the stick counts
    # a frame with no step due: the next poll must not wipe the unspent presses
    again = merge_pending(pending, FrameInput(fighters={"p1": FighterInput(dx=1), "p2": FighterInput()}))
    assert again.fighters["p1"].a and again.confirms["p1"] and again.nav["p1"] == (0, 1)
    assert again.any_button
