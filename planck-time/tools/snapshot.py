"""Render every Planck Time screen and every microgame to PNGs, to check the
look without a cabinet.

    cd planck-time && uv run python tools/snapshot.py OUT_DIR

Writes one full frame per screen (title, attract, intro, play, result, speed
up, game over, initials, high scores, versus result, pause), and per
microgame a sheet of its screen at the start, mid-game and after the end,
played by its bot.
"""

from __future__ import annotations

import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from planck_time import config  # noqa: E402
from planck_time import session as S  # noqa: E402
from planck_time.hiscores import Hiscores  # noqa: E402
from planck_time.microgames import REGISTRY, PlayerInput, play_time  # noqa: E402
from planck_time.render import Renderer  # noqa: E402
from planck_time.session import FrameInput, Session  # noqa: E402

DT = 1 / 60


class Shooter:
    def __init__(self, out_dir: str, seed: int, mode: int) -> None:
        self.out_dir = out_dir
        self.surface = pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT))
        scores = Hiscores(None)
        for name, score, level in (("QBT", 31, 7), ("MQT", 18, 4), ("TUM", 9, 2)):
            scores.add(name, score, level)
        self.s = Session(random.Random(seed), scores)
        self.s.mode = mode
        self.renderer = Renderer(self.surface)
        self.tag = "solo" if mode == 1 else "versus"

    def frame(self, inp: FrameInput | None = None) -> None:
        self.renderer.draw(self.s, self.s.update(DT, inp or FrameInput(activity=True)), DT)

    def bots(self, skill: dict) -> FrameInput:
        """Each player's bot, or nothing for a player whose skill roll fails."""
        fi = FrameInput(activity=True)
        for p, g in self.s.games.items():
            fi.players[p] = g.bot() if skill[p] else PlayerInput()
        return fi

    def press(self, **kw) -> None:
        self.frame(FrameInput(activity=True, **kw))

    def until(self, state: str, skill=None, limit: float = 30.0) -> None:
        for _ in range(round(limit / DT)):
            if self.s.state == state:
                return
            self.frame(self.bots(skill) if skill and self.s.state == S.PLAY else None)

    def run(self, seconds: float, skill=None) -> None:
        for _ in range(round(seconds / DT)):
            self.frame(self.bots(skill) if skill and self.s.state == S.PLAY else None)

    def shot(self, name: str) -> None:
        path = os.path.join(self.out_dir, f"{self.tag}_{name}.png")
        pygame.image.save(self.surface, path)
        print(path)


def screens(out_dir: str) -> None:
    for mode in (1, 2):
        sh = Shooter(out_dir, 3, mode)
        both = {"p1": True, "p2": True}
        sh.run(0.5)
        sh.shot("title")
        if mode == 1:
            sh.run(config.ATTRACT_DELAY + 1.5, None)
            for _ in range(round((config.ATTRACT_DELAY + 1.5) / DT)):
                sh.frame(FrameInput(activity=False))
            sh.shot("attract")
            sh.press(nav={"p1": (0, 0), "p2": (0, 0)})
        sh.press(confirms={"p1": True, "p2": False})
        sh.run(0.9)
        sh.shot("intro")
        sh.until(S.PLAY)
        sh.run(1.0, both)
        sh.shot("play")
        sh.until(S.RESULT, {"p1": True, "p2": False})
        sh.run(0.4)
        sh.shot("result")
        sh.press(pauses={"p1": True, "p2": False})
        sh.press()
        sh.shot("pause")
        sh.press(pauses={"p1": True, "p2": False})
        sh.until(S.SPEED_UP, both, limit=60)
        sh.run(0.5)
        sh.shot("speed_up")
        if mode == 1:
            sh.until(S.GAME_OVER, {"p1": False, "p2": False}, limit=60)
            sh.run(0.5)
            sh.shot("game_over")
            sh.until(S.NAME_ENTRY)
            sh.press(nav={"p1": (0, -1), "p2": (0, 0)})
            sh.shot("name_entry")
            for _ in range(3):
                sh.press(confirms={"p1": True, "p2": False})
            sh.run(0.3)
            sh.shot("hiscores")
        else:
            sh.until(S.MATCH_RESULT, {"p1": True, "p2": False}, limit=90)
            sh.run(config.MATCH_RESULT_LOCK + 0.2)
            sh.shot("match_result")


def microgames(out_dir: str, names: list[str], seed: int = 3, level: int = 1) -> None:
    for cls in REGISTRY:
        if names and cls.__name__ not in names:
            continue
        frames = []
        for when in (0.0, 0.6, None):
            g = cls(seed, level, play_time(level))
            surf = pygame.Surface((config.SCREEN_W, config.SCREEN_H))
            steps = round((when if when is not None else g.duration) / DT)
            for _ in range(steps):
                g.update(DT, g.bot())
                if when is None and g.result is not None:
                    break
            if when is None:
                if g.result is None:
                    g.timeout()
                for _ in range(15):
                    g.update(DT, PlayerInput())
            g.draw(surf)
            frames.append(surf)
        w, h = config.SCREEN_W, config.SCREEN_H
        sheet = pygame.Surface((3 * w + 20, h))
        for i, f in enumerate(frames):
            sheet.blit(f, (i * (w + 10), 0))
        path = os.path.join(out_dir, f"game_{cls.__name__}.png")
        pygame.image.save(pygame.transform.scale_by(sheet, 2), path)
        print(path, g.result)


def main(argv: list[str]) -> None:
    out_dir = argv[0] if argv else "snapshots"
    os.makedirs(out_dir, exist_ok=True)
    pygame.init()
    pygame.display.set_mode((1, 1))
    names = argv[1:]
    if not names:
        screens(out_dir)
    microgames(out_dir, names)


if __name__ == "__main__":
    main(sys.argv[1:])
