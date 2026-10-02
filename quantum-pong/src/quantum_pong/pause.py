"""Pause menu state, following the cabinet's pause convention (see "Pausing"
in ../AGENTS.md): Start pauses a match from either pad and freezes it, the
stick moves the selection, A picks an item, and Start or B resumes.

Pure logic (no pygame), unit tested. main.py feeds it one frame of
edge-detected input and only steps the match while `update` says PLAY.
"""

from __future__ import annotations

from dataclasses import dataclass

PAUSE_ITEMS = ("RESUME", "QUIT TO TITLE")

# What the game loop should do this frame.
PLAY = "play"  # step the match as normal
PAUSED = "paused"  # freeze everything, draw the menu over the frozen field
QUIT_TO_TITLE = "quit_to_title"  # end the match, back to the title screen


@dataclass
class PauseInput:
    """One frame of pause-relevant input, already edge-detected (True only on
    the frame a button goes down), so a held button acts once."""

    pause: bool = False  # Start pressed, either pad (or the keyboard pause key)
    back: bool = False  # B pressed
    confirm: bool = False  # A pressed
    nav: int = 0  # -1 up / 1 down, on the frame the stick leaves the centre

    @property
    def any(self) -> bool:
        """Any input at all -- keeps the idle timeout from firing while
        someone is actually using the menu."""
        return self.pause or self.back or self.confirm or self.nav != 0


def nav_edge(previous: int, current: int) -> int:
    """The stick's direction (-1/0/1) on the frame it changes to a new
    non-zero direction, else 0 -- holding the stick moves the selection once."""
    return current if current != 0 and current != previous else 0


@dataclass
class PauseMenu:
    paused: bool = False
    index: int = 0  # into PAUSE_ITEMS

    def update(self, inp: PauseInput) -> str:
        """Advance one frame; returns PLAY, PAUSED or QUIT_TO_TITLE."""
        if not self.paused:
            if inp.pause:
                self.paused = True
                self.index = 0
                return PAUSED
            return PLAY

        if inp.pause or inp.back:
            self.paused = False
            return PLAY
        if inp.nav:
            self.index = (self.index + inp.nav) % len(PAUSE_ITEMS)
        if inp.confirm:
            if PAUSE_ITEMS[self.index] == "RESUME":
                self.paused = False
                return PLAY
            self.paused = False
            return QUIT_TO_TITLE
        return PAUSED
