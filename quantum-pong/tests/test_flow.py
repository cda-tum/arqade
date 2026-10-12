"""The screen flow in main.main(), with every screen stubbed out: title ->
HOW TO PLAY -> match -> winner -> title, and QUIT from the title."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from quantum_pong import main as main_mod


def _run(monkeypatch, title, tutorial, game, winner=()):
    """Run main() with scripted screen results; return the screens shown."""
    shown = []
    title, tutorial, game, winner = iter(title), iter(tutorial), iter(game), iter(winner)

    def screen(name, results):
        def run(*args, **kwargs):
            shown.append(name)
            return next(results)
        return run

    monkeypatch.setattr(main_mod, "run_title_screen", screen("title", title))
    monkeypatch.setattr(main_mod, "run_tutorial_screen", screen("tutorial", tutorial))
    monkeypatch.setattr(main_mod, "run_game", screen("game", game))
    monkeypatch.setattr(main_mod, "run_winner_screen", screen("winner", winner))
    with pytest.raises(SystemExit) as exit_info:
        main_mod.main(["--no-keyboard"])
    assert exit_info.value.code == 0  # a clean exit hands back to the cabinet's menu
    return shown


def test_quit_on_the_title_exits_cleanly(monkeypatch):
    assert _run(monkeypatch, ["quit"], [], []) == ["title"]


def test_tutorial_comes_between_the_title_and_the_match(monkeypatch):
    shown = _run(monkeypatch, ["start", "quit"], ["play"], [("title", {})])
    assert shown == ["title", "tutorial", "game", "title"]


def test_tutorial_is_shown_again_after_quit_to_title(monkeypatch):
    shown = _run(
        monkeypatch, ["start", "start", "quit"], ["play", "play"], [("title", {}), ("idle", {})]
    )
    assert shown == ["title", "tutorial", "game", "title", "tutorial", "game", "title"]


def test_after_a_win_the_next_match_starts_from_the_title_with_its_tutorial(monkeypatch):
    score = {"p1": 7, "p2": 3}
    shown = _run(
        monkeypatch, ["start", "start", "quit"], ["play", "play"],
        [("p1", score), ("title", {})], ["continue"],
    )
    assert shown == ["title", "tutorial", "game", "winner", "title", "tutorial", "game", "title"]


def test_quit_on_the_tutorial_exits(monkeypatch):
    assert _run(monkeypatch, ["start"], ["quit"], []) == ["title", "tutorial"]


def test_idle_on_the_tutorial_goes_back_to_the_title(monkeypatch):
    shown = _run(monkeypatch, ["start", "quit"], ["idle"], [])
    assert shown == ["title", "tutorial", "title"]
