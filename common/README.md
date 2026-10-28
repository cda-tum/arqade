# arqade-common

Code shared by the Arqade games:

- `arqade_common.input`: named pad buttons (A, B, X, Y, L, R, Start, Select)
  across the cabinet's arcade sticks, browser gamepads and Xbox pads; the
  shared two-player keyboard layout; pads assigned to players as they connect;
  which device each player last used, and button names for on-screen hints.
- `arqade_common.keycaps`: keys drawn as keycaps, so hints for keyboard
  players show the key (a "B" cap) rather than a pad button letter.
- `arqade_common.runtime`: `is_browser()` and the few browser-only tweaks.
- `arqade_common.web`: optional events to a web page that embeds a game.

It must keep working with both pygame 2.5.2 (the cabinet's Python) and
pygame-ce (desktop and browser), so use only APIs both have.

Games use it as a path dependency (`arqade-common = { path = "../common" }`).
Deploys and web builds copy `src/arqade_common/` next to the game's package.
