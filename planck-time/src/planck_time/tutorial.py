"""The HOW TO PLAY card, shown once before a run started from the title.

The words (GOAL, per mode) and the demo: a handheld that plays real
microgames with their own bots, on a loop, through the same beats as the
game (the verb and its input, the fuse burning, NICE!). Pure like the
microgames themselves; render.py draws it, and lights the stick and A on
the button drawing as the demo uses them.
"""

from __future__ import annotations

from planck_time import config
from planck_time.microgames import REGISTRY, PlayerInput, play_time

GOAL = {  # lines of at most 33 characters: the right-hand column at 8 px
    1: ("TINY GAMES, A FEW SECONDS EACH.",
        "READ THE WORD, DO IT BEFORE",
        "THE FUSE BURNS OUT. A MISS COSTS",
        "A HEART. HOW MANY CAN YOU CLEAR?"),
    2: ("BOTH OF YOU GET THE SAME GAME.",
        "READ THE WORD, DO IT BEFORE",
        "THE FUSE BURNS OUT. A MISS COSTS",
        "A HEART. THE LAST ONE LEFT WINS!"),
}

DEMO_GAMES = ("VOTE!", "MEASURE!")  # stick + A, then A alone
INTRO, PLAY, RESULT = "intro", "play", "result"
INTRO_TIME = 1.1  # the demo's beats: shorter than the game's, it loops
RESULT_TIME = 1.0
REACT = 0.35  # the demo player looks before it moves
STICK_SHOW = 0.18  # how long a stick push or an A press stays lit on the drawing
A_SHOW = 0.2


class Demo:
    """Real microgames played by their bots, one after another, forever."""

    def __init__(self) -> None:
        self.round = 0
        self.stick = (0, 0)  # the last stick push, while it shows
        self.stick_left = 0.0
        self.a_left = 0.0
        self._deal()

    def _deal(self) -> None:
        verb = DEMO_GAMES[self.round % len(DEMO_GAMES)]
        cls = next(c for c in REGISTRY if c.VERB == verb)
        self.game = cls(11 + self.round, 0, play_time(0))
        self.phase = INTRO
        self.t = 0.0

    @property
    def time_left(self) -> float:
        """0..1 of the fuse, as the game's own."""
        if self.phase == INTRO:
            return 1.0
        return max(0.0, 1.0 - self.game.t / self.game.duration)

    def update(self, dt: float) -> None:
        self.t += dt
        self.stick_left = max(0.0, self.stick_left - dt)
        self.a_left = max(0.0, self.a_left - dt)
        g = self.game
        if self.phase == INTRO:
            if self.t >= INTRO_TIME:
                self.phase, self.t = PLAY, 0.0
        elif self.phase == PLAY:
            inp = g.bot() if g.t >= REACT and g.result is None else PlayerInput()
            if inp.step != (0, 0):
                self.stick, self.stick_left = inp.step, STICK_SHOW
            if inp.a:
                self.a_left = A_SHOW
            g.update(dt, inp)
            done = g.result is not None and g.since_end >= config.WIN_LINGER
            if done or g.t >= g.duration:
                if g.result is None:
                    g.timeout()
                self.phase, self.t = RESULT, 0.0
        else:
            g.update(dt, PlayerInput())  # the win animation plays on under NICE!
            if self.t >= RESULT_TIME:
                self.round += 1
                self._deal()
