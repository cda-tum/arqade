"""The pause menu (Start during play, see "Pausing" in ../AGENTS.md).

Pure (no pygame), so it is unit tested. game.py feeds it one frame of input
and acts on what it returns; the game itself is frozen simply by not calling
update() while paused.
"""

from __future__ import annotations

ITEMS = ("RESUME", "QUIT TO TITLE")


class PauseMenu:
    def __init__(self):
        self.index = 0

    def open(self):
        """Every pause starts on RESUME."""
        self.index = 0

    @property
    def item(self) -> str:
        return ITEMS[self.index]

    def step(self, *, move: int, pick: bool, resume: bool) -> str | None:
        """One frame: move is -1 (up) / 0 / +1 (down), pick is A, resume is
        Start or B. Returns "resume", "title", "move" or None."""
        if resume:
            return "resume"
        if pick:
            return "resume" if self.item == "RESUME" else "title"
        if move:
            self.index = (self.index + move) % len(ITEMS)
            return "move"
        return None
