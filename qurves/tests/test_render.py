import random

import pygame

from qurves import config, render
from qurves import match as m
from qurves.match import FrameInput, Match
from qurves.render import Renderer, cell_px


def test_cells_map_inside_the_arena_below_the_hud():
    assert cell_px((0, 0)) == (3, config.HUD_HEIGHT + 3)
    x, y = cell_px((config.GRID_W - 1, config.GRID_H - 1))
    assert x < config.INTERNAL_WIDTH and y < config.INTERNAL_HEIGHT


def play_through_every_screen():
    pygame.init()
    surface = pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
    mt = Match(random.Random(0))
    renderer = Renderer(surface)

    def frame(inp=None):
        events = mt.update(1 / 60, inp or FrameInput())
        renderer.draw(mt, events, 1 / 60)

    seen = set()
    frame()
    seen.add(mt.state)
    frame(FrameInput(confirm=True, activity=True))
    for _ in range(200):  # the countdown, into the round
        frame()
        seen.add(mt.state)
    for pl in mt.round.players.values():
        pl.meter = 100.0
    frame(FrameInput(split={"p1": True, "p2": True}, activity=True))
    for _ in range(900):  # splits, decoherence, the head-on crash, the next rounds
        frame()
        seen.add(mt.state)
    mt.scores = {"p1": config.ROUNDS_TO_WIN, "p2": 1}
    mt.match_winner = "p1"
    mt.state, mt.t = m.MATCH_RESULT, 2.0
    frame()
    seen.add(mt.state)
    return seen


def test_every_screen_renders_without_errors():
    seen = play_through_every_screen()
    assert seen >= {m.TITLE, m.COUNTDOWN, m.ROUND, m.ROUND_RESULT, m.MATCH_RESULT}


def test_it_still_renders_with_glow_and_scanlines_off(monkeypatch):
    monkeypatch.setattr(config, "GLOW", False)
    monkeypatch.setattr(config, "SHOW_SCANLINES", False)
    play_through_every_screen()
