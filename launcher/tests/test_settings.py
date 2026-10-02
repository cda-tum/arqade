import json

import pygame

from arqade_launcher import settings
from arqade_launcher.settings import ACTIONS, PLAYERS, Settings


def test_defaults_bind_every_action_to_a_real_key():
    for player in PLAYERS:
        for action in ACTIONS:
            name = settings.DEFAULT_KEYS[player][action]
            assert pygame.key.name(pygame.key.key_code(name)) == name


def test_default_keys_are_all_different_and_never_the_exit_key():
    keys = [settings.DEFAULT_KEYS[p][a] for p in PLAYERS for a in ACTIONS]
    assert len(keys) == len(set(keys))
    assert settings.EXIT_KEY not in keys


def test_default_keys_sit_in_the_same_place_on_qwertz():
    # Y/Z swap places on a German keyboard, and its punctuation is elsewhere.
    for player in PLAYERS:
        for name in settings.DEFAULT_KEYS[player].values():
            assert name not in ("y", "z") and (len(name) > 1 or name.isalnum())


def test_bind_moves_a_key_that_was_used_elsewhere():
    s = Settings()
    moved = s.bind("p1", "a", "k")  # k is P2's B by default
    assert moved == ("p2", "b")
    assert s.keys["p1"]["a"] == "k"
    assert s.keys["p2"]["b"] is None


def test_rebinding_the_same_key_to_the_same_action_moves_nothing():
    s = Settings()
    assert s.bind("p1", "a", s.keys["p1"]["a"]) is None


def test_round_trip(tmp_path):
    path = tmp_path / "sub" / "settings.json"
    s = Settings(fullscreen=False, pads=False, show_fps=True)
    s.bind("p2", "start", "space")
    settings.save(s, path)
    assert settings.load(path) == s


def test_broken_or_partial_files_fall_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json")
    assert settings.load(path) == Settings()
    path.write_text(json.dumps({"fullscreen": "yes", "keys": {"p1": {"a": "space", "up": 3}}}))
    loaded = settings.load(path)
    assert loaded.fullscreen is True
    assert loaded.keys["p1"]["a"] == "space"
    assert loaded.keys["p1"]["up"] == settings.DEFAULT_KEYS["p1"]["up"]
    assert settings.load(tmp_path / "missing.json") == Settings()
