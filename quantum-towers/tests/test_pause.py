import asyncio
import os

import pygame
import pytest

from quantum_towers import config, main
from quantum_towers.input import PlayerRawInput, set_keyboard_enabled
from quantum_towers.pause import PAUSE_ITEMS, PauseButtons, PauseMenu
from quantum_towers.quantum import states_equal, zero_state
from quantum_towers.sound import Sounds

NOTHING = PauseButtons()
START = PauseButtons(start=True)
A = PauseButtons(confirm=True)
B = PauseButtons(back=True)
UP = PauseButtons(up=True)
DOWN = PauseButtons(down=True)


def _feed(menu: PauseMenu, *frames: PauseButtons) -> list[str]:
    return [menu.update(frame) for frame in frames]


def _paused_menu() -> PauseMenu:
    menu = PauseMenu()
    _feed(menu, NOTHING, START, NOTHING)
    assert menu.paused
    return menu


# --- PauseMenu ---------------------------------------------------------------


def test_play_runs_until_start_is_pressed():
    menu = PauseMenu()
    assert _feed(menu, NOTHING, A, B, UP, DOWN, NOTHING) == ["play"] * 6
    assert not menu.paused


def test_start_pauses_and_play_stays_frozen():
    menu = PauseMenu()
    assert _feed(menu, NOTHING, START) == ["play", "paused"]
    assert menu.paused
    assert menu.selected == 0
    # Holding Start, or doing nothing, keeps the game frozen.
    assert _feed(menu, START, NOTHING, NOTHING) == ["paused"] * 3
    assert menu.paused


def test_start_held_over_from_the_title_does_not_pause():
    menu = PauseMenu()
    assert _feed(menu, START, START, START) == ["play"] * 3
    assert not menu.paused


def test_start_resumes():
    menu = _paused_menu()
    # The resuming frame itself is still frozen; play resumes on the next.
    assert _feed(menu, START, NOTHING) == ["paused", "play"]
    assert not menu.paused


def test_b_resumes():
    menu = _paused_menu()
    assert _feed(menu, B, NOTHING) == ["paused", "play"]
    assert not menu.paused


def test_a_on_resume_resumes():
    menu = _paused_menu()
    assert _feed(menu, A, NOTHING) == ["paused", "play"]
    assert not menu.paused


def test_a_on_quit_to_title_goes_to_the_title():
    menu = _paused_menu()
    _feed(menu, DOWN, NOTHING)
    assert PAUSE_ITEMS[menu.selected] == "QUIT TO TITLE"
    assert menu.update(A) == "title"
    assert not menu.paused


def test_stick_moves_the_selection_and_wraps():
    menu = _paused_menu()
    _feed(menu, DOWN)
    assert menu.selected == 1
    _feed(menu, DOWN)  # still held: no repeat
    assert menu.selected == 1
    _feed(menu, NOTHING, DOWN)
    assert menu.selected == 0  # wrapped
    _feed(menu, NOTHING, UP)
    assert menu.selected == 1
    _feed(menu, NOTHING, UP)
    assert menu.selected == 0


def test_pausing_again_starts_on_resume():
    menu = _paused_menu()
    _feed(menu, DOWN, NOTHING, START, NOTHING, START)
    assert menu.paused
    assert menu.selected == 0


def test_any_held_reports_any_button():
    assert not NOTHING.any_held()
    assert all(b.any_held() for b in (START, A, B, UP, DOWN))


# --- run_game, driven with scripted input -----------------------------------


def _raw(**held) -> PlayerRawInput:
    buttons = {name: held.get(name, False) for name in config.ACTION_NAMES}
    return PlayerRawInput(
        button_held=buttons,
        up_held=held.get("up", False),
        start_held=held.get("start", False),
        select_held=held.get("select", False),
        confirm_held=held.get("confirm", False),
        down_held=held.get("down", False),
        back_held=held.get("back", False),
    )


class _NullSound:
    def play(self) -> None:
        pass


@pytest.fixture
def game(monkeypatch):
    """Runs main.run_game headlessly, with P1's input taken from a script
    (one dict of held buttons per frame; P2 holds nothing). The script ends
    with the Start + Select quit combo unless it returns first."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    surface = pygame.display.set_mode((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
    set_keyboard_enabled(False)
    monkeypatch.setattr(config, "FPS", 0)  # no frame cap: run as fast as it can

    def run(script: list[dict], idle_frames: int = 0):
        frames = iter(script + [{}] * idle_frames + [{"start": True, "select": True}])

        def poll(_keys):
            return _raw(**next(frames)), _raw()

        monkeypatch.setattr(main, "_poll_players", poll)
        null = _NullSound()
        return asyncio.run(main.run_game(surface, None, Sounds(null, null, null), show_fps=False))

    yield run
    set_keyboard_enabled(True)
    pygame.quit()


def _mash_gates() -> list[dict]:
    """Three X presses (an odd number, so |0> ends up |1>) and a push up."""
    return [{"X": True}, {}, {"X": True}, {}, {"X": True}, {}, {"up": True}, {}]


def test_run_game_applies_gates_when_not_paused(game):
    result, players = game([{}] + _mash_gates())
    assert result == "quit"
    assert not states_equal(players["p1"].state, zero_state())


def test_run_game_freezes_while_paused(game):
    result, players = game([{}, {"start": True}, {}] + _mash_gates())
    assert result == "quit"
    assert states_equal(players["p1"].state, zero_state())
    assert players["p1"].floor == 0


def test_run_game_b_resumes_without_firing_h(game):
    # B is also the H gate. Resuming with it must not apply H, but play must
    # run again afterwards.
    script = [{}, {"start": True}, {}, {"H": True, "back": True}, {"H": True, "back": True}, {}]
    result, players = game(script + [{"X": True}, {}])
    assert result == "quit"
    assert not states_equal(players["p1"].state, zero_state())  # X applied
    script_without_x = [{}, {"start": True}, {}, {"H": True, "back": True}, {}]
    _result, players = game(script_without_x)
    assert states_equal(players["p1"].state, zero_state())  # no H


def test_run_game_quit_to_title(game):
    result, _players = game([{}, {"start": True}, {}, {"down": True}, {}, {"confirm": True}])
    assert result == "title"


def test_run_game_idle_timeout_runs_while_paused(game, monkeypatch):
    monkeypatch.setattr(config, "IDLE_TIMEOUT_SECONDS", 0.05)
    result, _players = game([{}, {"start": True}], idle_frames=100_000)
    assert result == "idle"
