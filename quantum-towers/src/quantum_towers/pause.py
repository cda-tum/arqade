"""The pause menu's state, kept out of main.py's game loop so it can be unit
tested like player.py.

Follows the cabinet-wide convention ("Pausing" in ../AGENTS.md): Start
pauses, either pad. In the menu the stick moves the selection, A picks an
item, and Start or B resumes. A and B are gate buttons during play (RESET
and H); they only mean pick/resume while the game is paused.

Start + Select (the quit combo) and the idle timeout are not handled here:
main.py checks both before asking the menu anything, paused or not.
"""

from __future__ import annotations

from dataclasses import astuple, dataclass

PAUSE_ITEMS = ("RESUME", "QUIT TO TITLE")


@dataclass(frozen=True)
class PauseButtons:
    """What's held this frame, both pads (and the dev keyboard) combined."""

    start: bool = False
    confirm: bool = False  # A
    back: bool = False  # B
    up: bool = False
    down: bool = False

    def any_held(self) -> bool:
        return any(astuple(self))


# Everything counts as already held before the first frame, so a button
# only acts once it has been released and pressed again -- otherwise the
# Start (or A) that started the match from the title would pause it on its
# very first frame.
_ALL_HELD = PauseButtons(start=True, confirm=True, back=True, up=True, down=True)


class PauseMenu:
    def __init__(self) -> None:
        self.paused = False
        self.selected = 0  # index into PAUSE_ITEMS
        self._previous = _ALL_HELD

    def update(self, held: PauseButtons) -> str:
        """Feed one frame's held buttons. Returns:

          - "play": not paused, run the game as normal this frame.
          - "paused": the game stays frozen this frame. This includes the
            frame the menu is closed on, so the A or B that resumed it
            never reaches the game as a RESET or H press.
          - "title": QUIT TO TITLE was picked.
        """
        previous, self._previous = self._previous, held

        def pressed(name: str) -> bool:
            return getattr(held, name) and not getattr(previous, name)

        if not self.paused:
            if pressed("start"):
                self.paused = True
                self.selected = 0
                return "paused"
            return "play"

        if pressed("start") or pressed("back"):
            self.paused = False
            return "paused"
        if pressed("up"):
            self.selected = (self.selected - 1) % len(PAUSE_ITEMS)
        if pressed("down"):
            self.selected = (self.selected + 1) % len(PAUSE_ITEMS)
        if pressed("confirm"):
            self.paused = False
            if PAUSE_ITEMS[self.selected] == "QUIT TO TITLE":
                return "title"
        return "paused"
