"""The HOW TO PLAY card, shown before every match started from the title.

Pure (no pygame), like pause.py, so it is unit tested: game.py feeds it one
frame at a time and draws what demo() describes with the game's own sprites.

The card goes away on any new button press from either pad (or any key,
without --no-keyboard), but not in its first MIN_SHOW seconds: the A or
Start that picked the mode, or its bounce, must not skip it unseen. Stick
movement never dismisses it.
"""

from __future__ import annotations

MIN_SHOW = 0.3   # seconds in which presses are ignored
LOOP = 5.0       # length of the demo scene, which then starts over

# The demo, in coordinates relative to the centre of its panel: three errors
# in a row, P1's color-code ship below them. Red corrects red; the purple Y
# turns blue when hit with red (X·Y ~ Z in either mode), blue then corrects
# it; blue corrects the last one.
INVADER_Y = -80
SHIP_Y = 100
SHOT_SPEED = 600          # px/s (the game's is 640)
INVADERS = ((-110, "X"), (0, "Y"), (110, "Z"))
FLASH = 0.2               # how long a hit error blinks white
BURST = 0.35              # how long a corrected error's burst lasts

# (time, what): "fire" from where the ship is, "swap" to the next color
# (the ship's colors cycle X -> Z -> Y, as in the game), "move" to an x.
SCRIPT = (
    (0.0, "move", -110),
    (0.5, "fire", None),
    (1.0, "move", 0),
    (1.6, "fire", None),
    (2.2, "swap", None),
    (2.6, "fire", None),
    (3.1, "move", 110),
    (3.7, "fire", None),
    (4.4, "move", -110),      # back to the start, ready for the next loop
)
MOVE_TIME = 0.45          # seconds per move
LIT = 0.2                 # how long a button shows as pressed
COLORS = ("X", "Z", "Y")  # P1's triangle

CAPTIONS = (               # (from time, text)
    (0.0, "RED SHOT: RED ERROR"),
    (1.3, "PURPLE: RED, THEN BLUE"),
    (3.0, "BLUE SHOT: BLUE ERROR"),
    (4.3, "WAVE CLEAN!"),
)


class Tutorial:
    def __init__(self):
        self.t = 0.0

    def open(self):
        self.t = 0.0

    def step(self, dt: float, pressed: bool) -> bool:
        """One frame: pressed is a new button press from any pad (or a key)
        this frame. True when the card is dismissed."""
        self.t += dt
        return pressed and self.t > MIN_SHOW


def _ship_x(t: float) -> float:
    x = float(SCRIPT[0][2])
    for at, what, to in SCRIPT:
        if what == "move" and at <= t:   # moves never overlap
            x += (to - x) * min(1.0, (t - at) / MOVE_TIME)
    return x


def demo(t: float) -> dict:
    """The demo scene at time t (looping every LOOP seconds).

    Returns ship_x, ship_col, invaders [(x, y, col, flash)], the corrected
    ones' bursts [(x, y, col, age)], shots [(x, y, col)], the lit buttons
    ({"a", "b"}) and the caption."""
    t = t % LOOP
    ci = 0
    cols = {x: c for x, c in INVADERS}
    flash = {x: 0.0 for x, _ in INVADERS}
    gone = {}
    shots, lit = [], set()
    for at, what, _ in SCRIPT:
        if at > t:
            break
        if what == "swap":
            ci = (ci + 1) % len(COLORS)
            if t - at < LIT: lit.add("b")
        elif what == "fire":
            if t - at < LIT: lit.add("a")
            x, col = _ship_x(at), COLORS[ci]
            hit_at = at + (SHIP_Y - 20 - INVADER_Y) / SHOT_SPEED
            if t < hit_at:
                shots.append((x, SHIP_Y - 20 - (t - at) * SHOT_SPEED, col))
                continue
            target = min(cols, key=lambda ix: abs(ix - x))
            if target in gone:
                continue
            if cols[target] == col:
                gone[target] = hit_at
            elif cols[target] == "Y":
                cols[target] = "Z" if col == "X" else "X"
                flash[target] = max(0.0, FLASH - (t - hit_at))
    invaders = [(x, INVADER_Y, cols[x], flash[x]) for x, _ in INVADERS if x not in gone]
    bursts = [(x, INVADER_Y, cols[x], t - at) for x, at in gone.items() if t - at < BURST]
    caption = [c for at, c in CAPTIONS if at <= t][-1]
    return dict(ship_x=_ship_x(t), ship_col=COLORS[ci], invaders=invaders, bursts=bursts,
                shots=shots, lit=lit, caption=caption)
