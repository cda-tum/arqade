"""The HOW TO PLAY card's scene: a real Fight, played from a script. Pure (no pygame).

Before every match from the select screen (not a rematch) the card shows the colour
rule in action, looping every LOOP frames, P1 TRIO (green) against P2 QUINT:

  1. A: TRIO's jab is green, QUINT is green: it hurts (X!).
  2. Y: QUINT switches basis and turns purple (the white flash, the H).
  3. A again: the green jab bounces off purple (the ping).
  4. B: TRIO's heavy is the other colour, purple: it hurts (Z!).

Everything on screen is the game's own: the fight's rules decide hit or bounce, and
the renderer draws its puppets and effects. Between presses TRIO walks back into reach.
"""

from __future__ import annotations

from .fight import Event, Fight
from .fighter import IDLE, FighterInput
from .moves import QUINT, TRIO

LOOP = 280                  # frames: the scene restarts (4.7 s)
START_X = {"p1": 266, "p2": 336}
REACH = 66                  # px between the two: TRIO walks in until it is this close
CAPTION_LEAD = 20           # a step's caption shows this many frames before its press

# (frame, who, button, caption index): the scene's presses
SCRIPT = (
    (24, "p1", "a", 0),
    (100, "p2", "y", 1),
    (140, "p1", "a", 2),
    (200, "p1", "b", 3),
)


class Lesson:
    """The looping scene. step() once per frame; `fight` and `caption` are what to draw."""

    def __init__(self) -> None:
        self.t = 0
        self.fight = self._new_fight()

    @staticmethod
    def _new_fight() -> Fight:
        fight = Fight({"p1": TRIO, "p2": QUINT})
        for key, x in START_X.items():
            fight.fighters[key].x = float(x)
        return fight

    @property
    def caption(self) -> int:
        """Which step's line is lit: the latest whose press is at most CAPTION_LEAD frames off."""
        lit = 0
        for frame, _who, _button, index in SCRIPT:
            if self.t >= frame - CAPTION_LEAD:
                lit = index
        return lit

    def inputs(self) -> dict[str, FighterInput]:
        """This frame's presses, or TRIO walking back into reach between them."""
        inp = {"p1": IDLE, "p2": IDLE}
        for frame, who, button, _index in SCRIPT:
            if self.t == frame:
                inp[who] = FighterInput(**{button: True})
                return inp
        p1, p2 = self.fight.fighters["p1"], self.fight.fighters["p2"]
        near_press = any(abs(self.t - frame) <= 3 for frame, *_ in SCRIPT)
        if p2.x - p1.x > REACH and p1.action in ("idle", "walk") and not near_press:
            inp["p1"] = FighterInput(dx=1)     # never pushing in as B is pressed: that would throw
        return inp

    def step(self) -> list[Event]:
        if self.t >= LOOP:
            self.t = 0
            self.fight = self._new_fight()
        events = self.fight.step(self.inputs())
        self.t += 1
        return events
