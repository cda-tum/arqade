"""Where the game is running, and the few things that differ because of it.

Keep browser-only branches small and in one place: everything else should
behave the same on the cabinet, on a PC and in the browser.
"""

from __future__ import annotations

import sys


def is_browser() -> bool:
    """True when running as WebAssembly in a browser (pygbag)."""
    return sys.platform == "emscripten"


# Browsers stop running the page while its tab is hidden. On return, the next
# frame would report the whole time away as one step, so balls would jump and
# timers would fire at once. Longer frames than this are clamped in the
# browser; on the cabinet and PC frame times are left alone.
MAX_BROWSER_FRAME_SECONDS = 0.1


def frame_seconds(raw_seconds: float) -> float:
    """The frame time a game loop should use, given what its clock measured."""
    if is_browser():
        return min(raw_seconds, MAX_BROWSER_FRAME_SECONDS)
    return raw_seconds
