import random

import pygame

from gate_drop import config
from gate_drop import match as m
from gate_drop.board import Gate, PlayerInput
from gate_drop.match import FrameInput, Match
from gate_drop.render import Renderer
from gate_drop.sprites import Sprites


def test_every_sprite_builds():
    pygame.init()
    sp = Sprites()
    size = (config.CELL, config.CELL)
    for kind in config.GATE_KINDS:
        for joint in (None, "l", "r", "u", "d"):
            assert sp.gate(kind, joint).get_size() == size
    for role in "ct":
        for joint in ("l", "r"):
            assert sp.cnot(role, joint).get_size() == size
    for kind in config.PAULIS:
        for frame in (0, 1):
            assert sp.bug(kind, frame).get_size() == size


def random_play(rng):
    def pick():
        return PlayerInput(move=rng.choice((-1, 0, 0, 0, 1)), cw=rng.random() < 0.05,
                           ccw=rng.random() < 0.03, soft=rng.random() < 0.7)
    return FrameInput(players={"p1": pick(), "p2": pick()}, activity=True)


def test_every_screen_renders_without_errors():
    pygame.init()
    surface = pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
    mt = Match(random.Random(0))
    renderer = Renderer(surface)
    rng = random.Random(1)
    seen = set()

    def frame(inp=None):
        events = mt.update(1 / 60, inp or FrameInput(activity=True))
        renderer.draw(mt, events, 1 / 60)
        seen.add(mt.state)

    frame()
    frame(FrameInput(confirm=True, activity=True))
    for _ in range(200):  # the countdown, into the round
        frame()
    mt.boards["p2"].noise_queue += ["X", "Z", "Y"]
    for _ in range(1200):  # twenty seconds of random play on both boards
        frame(random_play(rng) if mt.state == m.ROUND else None)
    for pos, c in list(mt.boards["p1"].grid.items()) if mt.boards else []:
        if isinstance(c, Gate) and c.error:
            mt.boards["p1"].grid.set(pos, None)
    for _ in range(400):  # a round result, then the next countdown
        frame()
    mt.scores = {"p1": config.ROUNDS_TO_WIN, "p2": 1}
    mt.match_winner = "p1"
    mt.state, mt.t = m.MATCH_RESULT, 2.0
    frame()
    assert seen >= {m.TITLE, m.COUNTDOWN, m.ROUND, m.ROUND_RESULT, m.MATCH_RESULT}
