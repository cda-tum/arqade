"""Render scripted Gate Drop games to PNGs, to check the look without a cabinet.

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
from gate_drop.hiscores import Hiscores  # noqa: E402
from gate_drop.match import FrameInput, Match  # noqa: E402
from gate_drop.render import Renderer  # noqa: E402

DT = 1 / 60


class Shooter:
    def __init__(self, out_dir: str, seed: int) -> None:
        self.out_dir = out_dir
        self.surface = pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
        scores = Hiscores(None)
        for name, score, level in (("QBT", 18200, 6), ("MQT", 9400, 4), ("TUM", 3100, 2)):
            scores.add(name, score, level)
        self.mt = Match(random.Random(seed), scores)
        self.renderer = Renderer(self.surface)
        self.rng = random.Random(seed + 1)

    def frame(self, inp: FrameInput | None = None) -> None:
        self.renderer.draw(self.mt, self.mt.update(DT, inp or FrameInput(activity=True)), DT)

    def press(self, *players, nav=None) -> None:
        fi = FrameInput(activity=True)
        for p in players:
            fi.confirms[p] = True
        for p, d in (nav or {}).items():
            fi.nav[p] = d
        self.frame(fi)

    def play(self, seconds: float) -> None:
        def pick():
            return PlayerInput(move=self.rng.choice((-1, 0, 0, 0, 0, 1)), cw=self.rng.random() < 0.04,
                               ccw=self.rng.random() < 0.02, soft=self.rng.random() < 0.35)
        for _ in range(round(seconds / DT)):
            fi = FrameInput(activity=True)
            fi.players = {"p1": pick(), "p2": pick()}
            self.frame(fi if self.mt.state == m.ROUND else None)

    def run(self, seconds: float) -> None:
        for _ in range(round(seconds / DT)):
            self.frame()

    def shot(self, name: str) -> None:
        size = (config.INTERNAL_WIDTH * 3, config.INTERNAL_HEIGHT * 3)
        pygame.image.save(pygame.transform.scale(self.surface, size), os.path.join(self.out_dir, name))
        print("wrote", name)

    def clear_errors(self, player: str = "p1") -> None:
        board = self.mt.boards[player]
        for pos, c in list(board.grid.items()):
            if isinstance(c, Gate) and c.error:
                board.grid.set(pos, None)


def versus(out_dir: str) -> None:
    sh = Shooter(out_dir, seed=4)
    sh.run(1.6)
    sh.shot("01-title.png")
    sh.press("p1")
    for d in ((1, 0), (1, 0), (0, 1), (1, 0)):  # p2: level 3, speed HI
        sh.press(nav={"p2": d})
    sh.press("p1")
    sh.run(0.3)
    sh.shot("02-setup.png")
    sh.press("p2")
    sh.run(0.5)
    sh.shot("03-countdown.png")
    sh.run(config.COUNTDOWN)
    sh.mt.boards["p2"].noise_queue += [config.NOISE_KIND] * 3
    sh.play(22)
    sh.shot("04-mid-game.png")
    for _ in range(3000):  # wait for a flash on either board, mid-chain
        sh.play(DT)
        if sh.mt.state == m.ROUND and any(b.phase == "flash" for b in sh.mt.boards.values()):
            break
    sh.shot("05-flash.png")
    if sh.mt.state == m.ROUND:
        sh.clear_errors()
    sh.run(0.4)
    sh.shot("06-round-result.png")
    sh.mt.scores = {"p1": config.ROUNDS_TO_WIN, "p2": 1}
    sh.mt.match_winner = "p1"
    sh.mt.state, sh.mt.t = m.MATCH_RESULT, 2.0
    sh.frame()
    sh.shot("07-match-result.png")


def single(out_dir: str) -> None:
    sh = Shooter(out_dir, seed=9)
    sh.press(nav={"p1": (0, 1)})
    sh.press("p1")
    sh.press(nav={"p1": (1, 0)})  # level 2
    sh.run(0.3)
    sh.shot("08-setup-1p.png")
    sh.press("p2")  # either pad readies single player
    sh.run(config.COUNTDOWN + 0.1)
    sh.play(18)
    sh.shot("09-single-player.png")
    if sh.mt.state == m.ROUND:
        sh.clear_errors()
    sh.run(0.4)
    sh.shot("10-level-clear.png")
    sh.run(config.LEVEL_CLEAR_TIME + config.COUNTDOWN + 0.3)
    if sh.mt.state == m.ROUND:
        sh.mt.score = max(sh.mt.score, 5200)
        sh.mt.boards["p1"].topped_out = True
    sh.run(0.4)
    sh.shot("11-game-over.png")
    sh.run(config.GAME_OVER_TIME)
    sh.press(nav={"p1": (0, -1)})
    sh.press("p1")
    sh.run(0.2)
    sh.shot("12-initials.png")
    sh.press("p1")
    sh.press("p1")
    sh.run(0.5)
    sh.shot("13-hiscores.png")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "snapshots"
    os.makedirs(out, exist_ok=True)
    pygame.init()
    versus(out)
    single(out)
