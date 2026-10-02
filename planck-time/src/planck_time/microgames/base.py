"""The microgame contract.

A microgame is one small class: it declares its VERB, its INPUT and the
CAPTION shown afterwards, steps its rules on a PlayerInput, ends in success
or failure, knows how to play itself perfectly (bot), and draws itself onto
a 240x160 GBA-sized surface. Everything random comes from the seed, so both
players' instances of the same microgame stay identical, and the rules are
pure: pygame only appears in draw().

The session (session.py) creates an instance per player with the same seed,
calls update() every frame for at most `duration` seconds, and then
timeout() if the game is still unresolved. tests/test_microgames.py checks
every registered microgame against this contract.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from planck_time import config

W, H = config.SCREEN_W, config.SCREEN_H
INPUTS = ("stick", "a", "mash", "stick+a")


def play_time(level: int) -> float:
    """Seconds a microgame lasts at a level: 5 s, 10% less per level, at least 2.5 s."""
    return max(config.PLAY_TIME_MIN, config.PLAY_TIME * config.PLAY_TIME_FACTOR ** level)


@dataclass(frozen=True)
class PlayerInput:
    stick: tuple[float, float] = (0.0, 0.0)  # analog, deadzoned, -1..1, y positive = down
    step: tuple[int, int] = (0, 0)  # a stick push this frame, auto-repeated (cursor and grid moves)
    a: bool = False  # A pressed this frame
    a_held: bool = False


IDLE = PlayerInput()


class Microgame:
    VERB = "VERB!"
    INPUT = "stick"
    CAPTION = ""
    BOSS = False  # bosses are longer, come after every BOSS_EVERY wins, and score more
    appearance = 0  # how many times this microgame has already come up this session (see spawn)
    POINTS = 1  # scored for a success

    @classmethod
    def spawn(cls, seed: int, level: int, duration: float, appearance: int = 0) -> "Microgame":
        """An instance that knows it is the session's (appearance + 1)-th of
        its kind, set before __init__ runs, so a microgame can introduce an
        idea the first time and build on it later. Subclasses keep the plain
        (seed, level, duration) constructor."""
        game = cls.__new__(cls)
        game.appearance = appearance
        game.__init__(seed, level, duration)
        return game

    @classmethod
    def duration_for(cls, level: int) -> float:
        """How long this game lasts at a level."""
        return play_time(level)

    def __init__(self, seed: int, level: int, duration: float) -> None:
        self.rng = random.Random(seed)
        self.level = level
        self.duration = duration
        self.speed = 1.0 + config.SPEED_PER_LEVEL * level
        self.t = 0.0
        self.result: bool | None = None
        self.won_at: float | None = None
        self.ended_at: float | None = None

    # --- the frame loop -------------------------------------------------------------------

    def update(self, dt: float, inp: PlayerInput) -> None:
        if self.result is None:
            self.step(dt, inp)
        self.t += dt

    def step(self, dt: float, inp: PlayerInput) -> None:
        """The rules, one frame at a time. Call win() or fail() to end."""

    def win(self) -> None:
        if self.result is None:
            self.result = True
            self.won_at = self.ended_at = self.t

    def fail(self) -> None:
        if self.result is None:
            self.result = False
            self.ended_at = self.t

    def timeout(self) -> None:
        """The time is up and the game is unresolved. Most games fail then;
        survive-until-the-end games (SHIELD!, REFRESH!) win instead."""
        self.fail()

    @property
    def since_end(self) -> float:
        """Seconds since the game was won or lost (0 while it runs)."""
        return 0.0 if self.ended_at is None else self.t - self.ended_at

    # --- the bot and the drawing --------------------------------------------------------

    def bot(self) -> PlayerInput:
        """Perfect play from the current state."""
        return IDLE

    def draw(self, surf) -> None:
        """Draw onto a 240x160 surface."""


class Boss(Microgame):
    """A boss: one long game with phases. It lasts DURATION seconds at level 0,
    shrinking with the object speed, so a faster level is a shorter fight."""

    BOSS = True
    POINTS = 3
    DURATION = 18.0

    @classmethod
    def duration_for(cls, level: int) -> float:
        return cls.DURATION / (1.0 + config.SPEED_PER_LEVEL * level)


REGISTRY: list[type[Microgame]] = []
BOSSES: list[type[Microgame]] = []


def register(cls: type[Microgame]) -> type[Microgame]:
    REGISTRY.append(cls)
    return cls


def register_boss(cls: type[Microgame]) -> type[Microgame]:
    BOSSES.append(cls)
    return cls
