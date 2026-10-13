"""Title menu state, following the cabinet's button convention (see "Button
convention" in ../AGENTS.md): the stick moves between PLAY and QUIT, A picks
the selected item, and Start always starts a match whatever is selected --
it is the one button a visitor tries first, so it must never quit. B does
nothing here: the title is the first page, there is nothing to go back to.

QUIT ends the game process, which hands the cabinet back to its game list
(EmulationStation, or the launcher's menu on a PC), the same way Start +
Select does.

Pure logic (no pygame), unit tested. main.py feeds it one frame of
edge-detected input, like the pause menu.
"""

from __future__ import annotations

from dataclasses import dataclass

TITLE_ITEMS = ("PLAY", "QUIT")

# What the title screen should do this frame.
STAY = "stay"
START = "start"
QUIT = "quit"


@dataclass
class TitleInput:
    """One frame of title input, already edge-detected."""

    start: bool = False  # Start pressed, either pad (or Space / P)
    confirm: bool = False  # A pressed (or Enter)
    back: bool = False  # B pressed -- deliberately ignored
    nav: int = 0  # -1 up / 1 down, on the frame the stick leaves the centre


@dataclass
class TitleMenu:
    index: int = 0  # into TITLE_ITEMS; PLAY is preselected

    def update(self, inp: TitleInput) -> str:
        """Advance one frame; returns STAY, START or QUIT."""
        if inp.start:
            return START
        if inp.nav:
            self.index = (self.index + inp.nav) % len(TITLE_ITEMS)
        if inp.confirm:
            return QUIT if TITLE_ITEMS[self.index] == "QUIT" else START
        return STAY
