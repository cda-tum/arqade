"""Render a scripted Qurves match to PNGs, to check the look without a cabinet.

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


def main(out_dir: str) -> None:
    pygame.init()
    os.makedirs(out_dir, exist_ok=True)
    surface = pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
    mt = Match(random.Random(7))
    renderer = Renderer(surface)

    def run(seconds, script=None):
        t = 0.0
        while t < seconds:
            inp = script(t) if script else FrameInput(activity=True)
            renderer.draw(mt, mt.update(DT, inp), DT)
            t += DT

    def shot(name):
        size = (config.INTERNAL_WIDTH * 2, config.INTERNAL_HEIGHT * 2)
        pygame.image.save(pygame.transform.scale(surface, size), os.path.join(out_dir, name))
        print("wrote", name)

    run(1.2)
    shot("1-title.png")
    renderer.draw(mt, mt.update(DT, FrameInput(confirm=True, activity=True)), DT)
    run(0.4)
    shot("2-countdown.png")
    run(config.COUNTDOWN)
    for pl in mt.round.players.values():
        pl.meter = 100.0

    def duel(t):
        d1 = UP if 0.5 < t < 1.6 else (RIGHT if t >= 1.6 else None)
        d2 = DOWN if 0.9 < t < 1.3 else (LEFT if t >= 1.3 else None)
        return FrameInput(direction={"p1": d1, "p2": d2},
                          split={"p1": 0.3 <= t < 0.3 + DT, "p2": 0.8 <= t < 0.8 + DT}, activity=True)

    run(1.4, duel)
    shot("3-split.png")
    run(1.2, lambda t: duel(t + 1.4))
    shot("4-later.png")
    mt.scores = {"p1": config.ROUNDS_TO_WIN - 1, "p2": 1}
    for bike in mt.round.players["p2"].bikes:  # every copy, or p2 just collapses
        mt.round.arena.set(rules.add(bike.pos, bike.heading), rules.WALL)
    run(0.3)
    shot("5-round-result.png")
    run(config.ROUND_RESULT_TIME + config.MATCH_RESULT_LOCK + 0.2)
    shot("6-match-result.png")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "snapshots")
