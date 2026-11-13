"""The on-screen control hints name each player's own keys or buttons."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from arqade_common.input import KEYBOARD, PAD, LastDevice
from error_invaders import game


class Devices:
    def __init__(self, p1, p2, latest="p1"):
        self.devices = LastDevice(PAD)
        self.devices._devices.update(p1=p1, p2=p2)
        self.devices.latest = latest


@pytest.fixture
def devices(monkeypatch):
    def use(p1, p2, latest="p1"):
        monkeypatch.setattr(game, "inp", Devices(p1, p2, latest))
    return use


def test_title_hint_on_keyboard_names_keys_and_actions(devices):
    devices(KEYBOARD, KEYBOARD)
    assert game.title_hints(0) == ["WASD/ARROWS: SELECT  ·  B/L: OK  ·  SPACE/ENTER: GO"]
    assert game.title_hints(1) == ["WASD/ARROWS: SELECT  ·  B/L: PLAY  ·  V/K: BACK"]


def test_title_hint_mixed_gives_each_player_a_line(devices):
    devices(KEYBOARD, PAD)
    assert game.title_hints(0) == ["P1 KEYS  WASD: SELECT  ·  B: OK  ·  SPACE: GO",
                                   "P2 PAD  STICK: SELECT  ·  A: OK  ·  START: GO"]


def test_pause_hint_names_the_keys(devices):
    devices(KEYBOARD, KEYBOARD, latest="p2")
    assert game.key_hint((("a", "PICK"), ("start", "RESUME")), "p2") == "L: PICK  ·  ENTER: RESUME"


@pytest.mark.parametrize("p1,p2", [(KEYBOARD, KEYBOARD), (KEYBOARD, PAD), (PAD, KEYBOARD)])
@pytest.mark.parametrize("two", [False, True])
def test_keyboard_screens_draw(devices, monkeypatch, p1, p2, two):
    pygame.init()
    pygame.display.set_mode((1, 1))
    for name in ("g", "state"):
        monkeypatch.setattr(game, name, getattr(game, name))   # put the match back afterwards
    devices(p1, p2)
    game.new_game(two)
    S = pygame.Surface((game.W, game.H))
    for t in (0.3, 0.6):
        game.how_to.t = t
        game.draw_tutorial(S)
    for step in (0, 1):
        game.menu["step"] = step
        game.draw_title(S)
    game.menu["step"] = 0
    game.draw_pause(S)
