"""Optional events to the web page that embeds a game.

In the browser, a game can tell the surrounding page what is happening, via
window.parent.postMessage({"type": ..., "id": ...}, "*"). Nobody has to
listen: when the game runs on its own page, or outside a browser, these calls
do nothing. Games must never wait for an answer.

Event types:
    arqade:game-start  a match has started
    arqade:game-end    a match has ended (won, abandoned or timed out)
    arqade:quit        the player asked to leave the game; an embedding page
                       may navigate away, otherwise the game carries on
"""

from __future__ import annotations

import json

from arqade_common.runtime import is_browser

GAME_START = "arqade:game-start"
GAME_END = "arqade:game-end"
QUIT = "arqade:quit"


def post_event(event_type: str, game_id: str) -> None:
    """Send one event to the embedding page, if there is one."""
    if not is_browser():
        return
    try:
        # pygbag exposes the browser's window object as platform.window.
        # The message goes through JSON.parse so the page receives a plain
        # JavaScript object, not a Python proxy.
        import platform

        window = platform.window
        if window.parent is window:
            return  # not embedded: the game has the page to itself
        message = window.JSON.parse(json.dumps({"type": event_type, "id": game_id}))
        window.parent.postMessage(message, "*")
    except Exception:  # noqa: BLE001 -- an event must never crash the game
        pass
