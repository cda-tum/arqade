"""Render a scripted Gate Drop match to PNGs, to check the look without a cabinet.

    cd gate-drop && uv run python tools/snapshot.py OUT_DIR
"""

from __future__ import annotations

import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from gate_drop import config  # noqa: E402
from gate_drop import match as m  # noqa: E402
from gate_drop.board import Gate, PlayerInput  # noqa: E402
from gate_drop.match import FrameInput, Match  # noqa: E402
from gate_drop.render import Renderer  # noqa: E402

DT = 1 / 60


def main(out_dir: str) -> None:
    pygame.init()
    os.makedirs(out_dir, exist_ok=True)
    surface = pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
    mt = Match(random.Random(4))
    renderer = Renderer(surface)
    rng = random.Random(2)

    def play():
        def pick():
            return PlayerInput(move=rng.choice((-1, 0, 0, 0, 0, 1)), cw=rng.random() < 0.04,
                               ccw=rng.random() < 0.02, soft=rng.random() < 0.35)
        return FrameInput(players={"p1": pick(), "p2": pick()}, activity=True)

    def frame(inp=None):
        renderer.draw(mt, mt.update(DT, inp or FrameInput(activity=True)), DT)

    def run(seconds, script=None):
        for _ in range(round(seconds / DT)):
            frame(script() if script else None)

    def shot(name):
        size = (config.INTERNAL_WIDTH * 3, config.INTERNAL_HEIGHT * 3)
        pygame.image.save(pygame.transform.scale(surface, size), os.path.join(out_dir, name))
        print("wrote", name)

    run(1.6)
    shot("1-title.png")
    frame(FrameInput(confirm=True, activity=True))
    run(0.5)
    shot("2-countdown.png")
    run(config.COUNTDOWN)
    mt.boards["p2"].noise_queue += ["X", "Z", "Y", "X", "Z"]
    run(22, play)
    shot("3-mid-game.png")
    for _ in range(3000):  # wait for a flash on either board, mid-chain
        frame(play())
        if mt.state == m.ROUND and any(b.phase == "flash" for b in mt.boards.values()):
            break
    shot("4-flash.png")
    if mt.state == m.ROUND:
        board = mt.boards["p1"]
        for pos, c in list(board.grid.items()):
            if isinstance(c, Gate) and c.error:
                board.grid.set(pos, None)
    run(0.4)
    shot("5-round-result.png")
    mt.scores = {"p1": config.ROUNDS_TO_WIN, "p2": 1}
    mt.match_winner = "p1"
    mt.state, mt.t = m.MATCH_RESULT, 2.0
    frame()
    shot("6-match-result.png")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "snapshots")
