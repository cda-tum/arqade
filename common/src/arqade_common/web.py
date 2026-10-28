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
    arqade:score       a player entered their initials for a new local high
                       score; also carries "mode", "score" (an int; times in
                       milliseconds) and "initials" (see post_score)
"""

from __future__ import annotations

import json

from arqade_common.runtime import is_browser

GAME_START = "arqade:game-start"
GAME_END = "arqade:game-end"
QUIT = "arqade:quit"
SCORE = "arqade:score"

_INITIALS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


def post_event(event_type: str, game_id: str) -> None:
    """Send one event to the embedding page, if there is one."""
    _post({"type": event_type, "id": game_id})


def post_score(game_id: str, mode: str, score: int, initials: str) -> None:
    """Tell the embedding page about a new high score, if there is a page.

    mode is one of the "scores" modes in the game's game.json; score is the
    same value the game stores locally, as an int (times in milliseconds).
    Initials keep only A-Z and 0-9 (what the site accepts); a name with none
    of those isn't sent.
    """
    if not is_browser():
        return
    try:
        score = int(score)
        initials = "".join(c for c in str(initials).upper() if c in _INITIALS)[:3]
    except (TypeError, ValueError, OverflowError):
        return  # a score event must never crash the game
    if not initials:
        return
    _post({"type": SCORE, "id": game_id, "mode": mode, "score": score, "initials": initials})


def _post(payload: dict) -> None:
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
        message = window.JSON.parse(json.dumps(payload))
        window.parent.postMessage(message, "*")
    except Exception:  # noqa: BLE001 -- an event must never crash the game
        pass
