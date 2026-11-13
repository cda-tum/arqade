import random

import pygame
import pytest
from arqade_common.input import KEYBOARD, PAD, LastDevice

from gate_drop import config
from gate_drop import match as m
from gate_drop.board import Gate, PlayerInput
from gate_drop.hiscores import Hiscores
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
    for wire in range(config.COLS):  # the |q_n> label under each wire fits under its column
        assert sp.ket(wire, (255, 255, 255)).get_width() == config.CELL


def random_play(rng):
    def pick():
        return PlayerInput(move=rng.choice((-1, 0, 0, 0, 1)), cw=rng.random() < 0.05,
                           ccw=rng.random() < 0.03, soft=rng.random() < 0.7)
    fi = FrameInput(activity=True)
    fi.players = {"p1": pick(), "p2": pick()}
    return fi


def any_button():
    fi = FrameInput(activity=True)
    fi.any_button = True
    return fi


def press(*players, back=False, nav=None):
    fi = FrameInput(activity=True)
    for p in players:
        (fi.backs if back else fi.confirms)[p] = True
    for p, d in (nav or {}).items():
        fi.nav[p] = d
    return fi


def devices(p1, p2):
    """Players on these devices, as if each had pressed something on it."""
    d = LastDevice(p1)
    d._devices["p2"] = p2
    return d


# The hints with pads (the cabinet), the keyboard (keycaps) and one of each.
DEVICES = pytest.mark.parametrize("on", ((PAD, PAD), (KEYBOARD, KEYBOARD), (KEYBOARD, PAD), (PAD, KEYBOARD)))


class Harness:
    def __init__(self, on=(PAD, PAD)):
        pygame.init()
        self.surface = pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
        self.mt = Match(random.Random(0), Hiscores(None))
        self.renderer = Renderer(self.surface, devices(*on))
        self.rng = random.Random(1)
        self.seen = set()

    def frame(self, inp=None):
        events = self.mt.update(1 / 60, inp or FrameInput(activity=True))
        self.renderer.draw(self.mt, events, 1 / 60)
        self.seen.add(self.mt.state)

    def play(self, frames):
        for _ in range(frames):
            self.frame(random_play(self.rng) if self.mt.state == m.ROUND else None)

    def clear_errors(self, player="p1"):
        if self.mt.state == m.ROUND:
            for pos, c in list(self.mt.boards[player].grid.items()):
                if isinstance(c, Gate) and c.error:
                    self.mt.boards[player].grid.set(pos, None)


@DEVICES
def test_every_versus_screen_renders_without_errors(on):
    h = Harness(on)
    h.frame()
    h.frame(press("p1"))  # to the setup screen
    h.frame(press("p1", nav={"p2": (1, 0)}))  # p1 ready, p2 changes its level
    h.frame(press("p2"))
    h.play(300)  # five seconds of HOW TO PLAY: more than one loop of its demo
    h.frame(any_button())
    h.play(200)  # the countdown, into the round
    h.mt.boards["p2"].noise_queue += [config.NOISE_KIND] * 3
    h.play(1200)  # twenty seconds of random play on both boards
    pause = press("p1")
    pause.pauses["p1"] = True
    h.frame(pause)
    assert h.mt.paused
    h.play(30)  # the pause menu, drawn over the frozen round
    h.frame(pause)
    h.clear_errors()
    h.play(400)  # a round result, then the next countdown
    h.mt.scores = {"p1": config.ROUNDS_TO_WIN, "p2": 1}
    h.mt.match_winner = "p1"
    h.mt.state, h.mt.t = m.MATCH_RESULT, 2.0
    h.frame()
    assert h.seen >= {m.TITLE, m.SETUP, m.TUTORIAL, m.COUNTDOWN, m.ROUND, m.ROUND_RESULT, m.MATCH_RESULT}


@DEVICES
def test_every_single_player_screen_renders_without_errors(on):
    h = Harness(on)
    h.frame(press(nav={"p1": (0, -1)}))  # 1 player
    h.frame(press("p1"))
    h.frame(press("p1"))  # ready
    h.play(30)  # HOW TO PLAY
    h.frame(any_button())
    h.play(200)  # the countdown, into the round
    h.clear_errors()
    h.play(300)  # level clear, then the next level's countdown
    h.play(200)
    h.play(300)  # some random play on level 2
    if h.mt.state == m.ROUND:
        h.mt.score = 999
        h.mt.boards["p1"].topped_out = True
    h.play(200)  # game over, then the initials
    for _ in range(3):
        h.frame(press("p1"))
    h.play(30)  # the high-score table
    assert h.seen >= {m.SETUP, m.TUTORIAL, m.COUNTDOWN, m.ROUND, m.LEVEL_CLEAR, m.GAME_OVER, m.NAME_ENTRY, m.HISCORES}


def test_the_title_lights_the_picked_row_and_quit_draws():
    h = Harness()
    h.frame(press(nav={"p1": (0, 1)}))
    assert m.TITLE_ITEMS[h.mt.title_index] == "QUIT"
    h.frame()
    assert h.mt.state == m.TITLE


def test_the_how_to_play_demo_restarts_each_time_the_card_opens():
    h = Harness()
    h.frame(press("p1"))
    h.frame(press("p1", "p2"))
    h.frame()
    assert h.mt.state == m.TUTORIAL
    for _ in range(100):
        h.frame()
    assert h.renderer.demo.t > 1.0
    h.mt._to_title()
    h.frame()
    h.frame(press("p1"))
    h.frame(press("p1", "p2"))
    h.frame()
    assert h.renderer.demo.t < 0.1
