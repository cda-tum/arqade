"""Render scripted Qurves matches to PNGs, to check the look without a cabinet.

    cd qurves && uv run python tools/snapshot.py OUT_DIR
"""

from __future__ import annotations

import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from qurves import config, rules  # noqa: E402
from qurves.match import FrameInput, Match  # noqa: E402
from qurves.render import Renderer  # noqa: E402

UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)
DT = 1 / 60


class Shooter:
    def __init__(self, out_dir: str, mode: int, seed: int) -> None:
        self.out_dir = out_dir
        self.surface = pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
        self.match = Match(random.Random(seed))
        self.renderer = Renderer(self.surface)
        if mode == 4:
            self.frame(FrameInput(nav=RIGHT, activity=True))

    def frame(self, inp: FrameInput) -> None:
        self.renderer.draw(self.match, self.match.update(DT, inp), DT)

    def run(self, seconds: float, script=None) -> None:
        t = 0.0
        while t < seconds:
            self.frame(script(t) if script else FrameInput(activity=True))
            t += DT

    def shot(self, name: str) -> None:
        size = (config.INTERNAL_WIDTH * 2, config.INTERNAL_HEIGHT * 2)
        pygame.image.save(pygame.transform.scale(self.surface, size), os.path.join(self.out_dir, name))
        print("wrote", name)

    def gates_ahead(self, player: str, kinds: str, first: int = 3, gap: int = 6) -> None:
        bike = self.match.round.players[player].bikes[0]
        for i, kind in enumerate(kinds):
            n = first + gap * i
            self.match.round.gates.append(
                rules.Gate(kind, (bike.pos[0] + bike.heading[0] * n, bike.pos[1] + bike.heading[1] * n)))


def two_players(out_dir: str) -> None:
    sh = Shooter(out_dir, 2, seed=7)
    sh.run(1.2)
    sh.shot("1-title.png")
    sh.frame(FrameInput(confirm=True, activity=True))
    sh.run(0.4)
    sh.shot("2-countdown.png")
    sh.run(config.COUNTDOWN)
    sh.match.round.gates.clear()
    sh.gates_ahead("p1", "HH", first=3, gap=0)  # one H now; a second, later, for a copy
    sh.match.round.gates.pop()
    sh.gates_ahead("p2", "ZH", first=3, gap=6)

    def duel(t):
        d1 = RIGHT if t > 0.9 else None
        d2 = UP if 1.0 < t < 1.4 else (LEFT if t >= 1.4 else None)
        return FrameInput(stick=(d1, d2), activity=True)

    sh.run(0.7, duel)
    sh.match.round.gates.append(rules.Gate("H", (sh.match.round.players["p1"].bikes[0].pos[0], 30)))
    sh.match.round.gates.append(rules.Gate("X", (60, 60)))
    sh.run(0.9, lambda t: duel(t + 0.7))
    sh.shot("3-copies.png")
    sh.run(1.2, lambda t: duel(t + 1.6))
    sh.shot("4-later.png")
    sh.match.scores = {"p1": config.ROUNDS_TO_WIN - 1, "p2": 1}
    for bike in sh.match.round.players["p2"].bikes:  # every copy, or p2 just collapses
        sh.match.round.arena.set(rules.add(bike.pos, bike.heading), rules.WALL)
    sh.run(0.3)
    sh.shot("5-round-result.png")
    sh.run(config.ROUND_RESULT_TIME + config.MATCH_RESULT_LOCK + 0.2)
    sh.shot("6-match-result.png")


def four_players(out_dir: str) -> None:
    sh = Shooter(out_dir, 4, seed=3)
    sh.run(0.6)
    sh.shot("7-title-4p.png")
    sh.frame(FrameInput(confirm=True, activity=True))
    sh.run(config.COUNTDOWN + 0.1)
    sh.match.round.gates.clear()
    for player, kinds in (("p1", "H"), ("p2", "HZ"), ("p3", "X"), ("p4", "H")):
        sh.gates_ahead(player, kinds)

    def chaos(t):
        return FrameInput(stick=(DOWN if 1.0 < t < 1.3 else None, UP if 1.2 < t < 1.5 else None),
                          pad=(UP if 0.8 < t < 1.0 else None, DOWN if 1.1 < t < 1.3 else None),
                          activity=True)

    sh.run(1.8, chaos)
    sh.shot("8-four-players.png")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "snapshots"
    os.makedirs(out, exist_ok=True)
    pygame.init()
    two_players(out)
    four_players(out)
