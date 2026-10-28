import random

import pygame
import pytest
from arqade_common.input import KEYBOARD, PAD, LastDevice

from qurves import config, render, rules
from qurves import match as m
from qurves.match import FrameInput, Match
from qurves.render import Renderer, cell_px


def test_cells_map_inside_the_arena_below_the_hud():
    assert cell_px((0, 0)) == (3, config.HUD_HEIGHT + 3)
    x, y = cell_px((config.GRID_W - 1, config.GRID_H - 1))
    assert x < config.INTERNAL_WIDTH and y < config.INTERNAL_HEIGHT


def devices(p1, p2):
    """Sides on these devices, as if each had pressed something on it."""
    d = LastDevice(p1)
    d._devices["p2"] = p2
    return d


def play_through_every_screen(mode=2, on=(PAD, PAD)):
    pygame.init()
    surface = pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
    mt = Match(random.Random(0))
    renderer = Renderer(surface, devices(*on))

    def frame(inp=None):
        events = mt.update(1 / 60, inp or FrameInput())
        renderer.draw(mt, events, 1 / 60)

    seen = set()
    frame()
    if mode == 4:
        frame(FrameInput(nav=(1, 0), activity=True))
    seen.add(mt.state)
    frame(FrameInput(confirm=True, activity=True))
    for _ in range(330):  # how to play, its demo running through once
        frame()
        seen.add(mt.state)
    frame(FrameInput(any_button=True, activity=True))
    for _ in range(200):  # the countdown, into the round
        frame()
        seen.add(mt.state)
    for name, pl in mt.round.players.items():  # every gate kind, right in front of everyone
        bike = pl.bikes[0]
        for i, kind in enumerate("HZHX"):
            mt.round.gates.append(rules.Gate(kind, (bike.pos[0] + bike.heading[0] * (2 + 5 * i), bike.pos[1])))
    for _ in range(900):  # splits, shields, jumps, decoherence, crashes, the next rounds
        frame()
        seen.add(mt.state)
    mt.scores = {p: i for i, p in enumerate(mt.players)}
    mt.scores["p1"] = config.ROUNDS_TO_WIN
    mt.match_winner = "p1"
    mt.state, mt.t = m.MATCH_RESULT, 2.0
    frame()
    seen.add(mt.state)
    return seen


def test_every_screen_renders_without_errors():
    seen = play_through_every_screen()
    assert seen >= {m.TITLE, m.TUTORIAL, m.COUNTDOWN, m.ROUND, m.ROUND_RESULT, m.MATCH_RESULT}


def test_four_player_screens_render_without_errors():
    seen = play_through_every_screen(mode=4)
    assert seen >= {m.TITLE, m.TUTORIAL, m.COUNTDOWN, m.ROUND, m.ROUND_RESULT, m.MATCH_RESULT}


@pytest.mark.parametrize("on", ((KEYBOARD, KEYBOARD), (KEYBOARD, PAD), (PAD, KEYBOARD)))
@pytest.mark.parametrize("mode", (2, 4))
def test_every_screen_renders_for_keyboard_players(mode, on):
    seen = play_through_every_screen(mode, on)  # keycaps on the title, the card and the result
    assert seen >= {m.TITLE, m.TUTORIAL, m.COUNTDOWN, m.ROUND, m.ROUND_RESULT, m.MATCH_RESULT}


def test_it_still_renders_with_glow_and_scanlines_off(monkeypatch):
    monkeypatch.setattr(config, "GLOW", False)
    monkeypatch.setattr(config, "SHOW_SCANLINES", False)
    play_through_every_screen()


@pytest.mark.parametrize("on", ((PAD, PAD), (KEYBOARD, KEYBOARD)))
def test_the_pause_menu_renders(on):
    pygame.init()
    surface = pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
    mt = Match(random.Random(0))
    renderer = Renderer(surface, devices(*on))
    script = [FrameInput(confirm=True, activity=True)] + [FrameInput()] * 30 + [FrameInput(any_button=True)]
    for inp in script + [FrameInput()] * 200 + [FrameInput(pause=True)]:
        renderer.draw(mt, mt.update(1 / 60, inp), 1 / 60)
    assert mt.paused
    renderer.draw(mt, mt.update(1 / 60, FrameInput(nav=(0, 1))), 1 / 60)
