"""The HOW TO PLAY card, shown before every match started from the setup
screen (match.TUTORIAL; a rematch or the next round skips it).

Pure (no pygame), like match.py: the card's words, and the looping demo.
The demo is a scripted pill on a small 4-wire board run by the real Board
rules: it slides left, turns twice, soft-drops onto an X and a Z error, and
both pairs cancel. render.py draws it, and lights each control on the
drawing of the cabinet's buttons while the demo uses it.
"""

from __future__ import annotations

from gate_drop.board import Board, Event, Gate, Grid, Piece, PlayerInput

DEMO_COLS, DEMO_ROWS = 4, 8
DEMO_ERRORS = (((1, 7), "X"), ((2, 7), "Z"))
DEMO_PILL = ("Z", "X")  # spawns over wires 2 and 3, the wrong way round for the errors below
DEMO_SPAWN_X = 2
DEMO_FALL = 0.4  # seconds per row: slower than the game, so each step can be followed
DEMO_LOOP = 3.4  # seconds, then it starts over
# (seconds into the loop, control): a tap, or from "down" on, a held soft drop.
# The drop starts just after a fall step, so it is seen falling, not snapping down.
SCRIPT = ((0.45, "left"), (0.7, "a"), (0.95, "a"), (1.25, "down"))
LIT_TIME = 0.25  # how long a tapped control stays lit on the drawing

HEADING = "HOW TO PLAY"
GOAL = {
    1: ("STACK GATE PILLS ON THE WIRES.", "TWO SAME GATES ON A WIRE CANCEL.", "CANCEL EVERY ERROR BUG TO WIN!"),
    2: ("STACK GATE PILLS ON THE WIRES.", "TWO SAME GATES ON A WIRE CANCEL.", "CLEAR YOUR BUGS BEFORE YOUR RIVAL!"),
}
# The cabinet's 2x3 cluster as printed, top row L X R, bottom row Y B A, and
# what the game does with each button it uses (the rest are drawn unlit).
CLUSTER = (("L", "X", "R"), ("Y", "B", "A"))
CONTROLS = (("STICK", "MOVE / DROP"), ("A", "ROTATE RIGHT"), ("B", "ROTATE LEFT"), ("START", "PAUSE"))
PROMPT = "PRESS ANY BUTTON TO START"
KEYBOARD_PROMPT = "PRESS ANY KEY TO START"  # when everyone is on the keyboard


def caption(demo: "Demo", a: str = "A", stick: str = "STICK") -> tuple[str, ...]:
    """What the demo is showing, a line or two under its well. `a` and
    `stick` name the controls for the player's device ("B", "WASD")."""
    if demo.solved or demo.board.phase == "flash":
        return ("SAME GATES", "CANCEL!")
    if demo.t >= SCRIPT[-1][0]:
        return (f"{stick} DOWN:", "DROP")
    if demo.t >= SCRIPT[1][0]:
        return (f"{a}: ROTATE",)
    if demo.t >= SCRIPT[0][0]:
        return (f"{stick}: MOVE",)
    return ("A PILL FALLS",)


class Demo:
    """The scripted mini-round. update() steps it and returns the board's
    events, so the renderer can flash, burst and pop up as in the game."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.t = 0.0
        board = Board([], seed=0)
        board.grid = Grid(DEMO_COLS, DEMO_ROWS)
        for pos, kind in DEMO_ERRORS:
            board.grid.set(pos, Gate(kind, error=True))
        board.next = Piece(tuple(Gate(k, pill=1) for k in DEMO_PILL), DEMO_SPAWN_X, 0)
        board.fall_interval = DEMO_FALL
        self.board = board
        self._sent: set[int] = set()

    @property
    def solved(self) -> bool:
        return self.board.errors_left() == 0

    def control(self) -> str | None:
        """The control the demo is using right now: "left", "a" or "down"."""
        for when, name in SCRIPT:
            if name == "down":
                if self.t >= when and (self.board.piece is not None or self.t < when + LIT_TIME):
                    return name
            elif when <= self.t < when + LIT_TIME:
                return name
        return None

    def update(self, dt: float) -> list[Event]:
        self.t += dt
        if self.t >= DEMO_LOOP:
            self.reset()
            return []
        if self.solved and self.board.phase == "settle":
            return []  # hold the cleared board; the next pill would be a random one
        move, cw = 0, False
        for i, (when, name) in enumerate(SCRIPT):
            if self.t >= when and i not in self._sent and name != "down":
                self._sent.add(i)
                move, cw = (-1 if name == "left" else move), (cw or name == "a")
        soft = self.t >= SCRIPT[-1][0]
        return self.board.update(dt, PlayerInput(move=move, cw=cw, soft=soft))
