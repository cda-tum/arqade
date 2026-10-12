"""Scripted mini-scenes and the HOW TO PLAY card's rules.

The title screen's legend and the HOW TO PLAY card before a match both show
short scenes played by the game's own rules: a real Board on a small chip,
with fixed pairs, specials and stick moves at fixed times instead of a
player. Pure Python, no pygame, so the scenes are unit tested (each one must
show what its caption says). game.py draws them with draw_board().
"""

from __future__ import annotations

from dataclasses import dataclass, field

from superconductor.lattice import Lattice, edge
from superconductor.rules import Board, Spawn

# Presses in the first moments of the card are ignored, so the A or Start
# that confirmed the menu (or its bounce) can't skip it unseen.
MIN_SHOW = 0.3

INF = float("inf")
GREEN, YELLOW, VIOLET, BLUE = 1, 2, 3, 4  # game.PAIR_COLORS indices


@dataclass(frozen=True)
class Scene:
    """One looping scene: a 3x4 chip, pairs, and what happens when.

    `spawns` are (t, a, b, coherence, color). `script` is (t, action, *args):
    ("move", direction) is a stick push by P1, ("commit", pair_id, route)
    sends another pair's qubit off, ("special", kind, edge_or_nodes) puts a
    special down. The scene starts over after `length` seconds.
    """

    name: str
    color: str  # caption colour, a key game.py knows
    lines: tuple[str, str]
    length: float
    spawns: tuple = ()
    script: tuple = ()


SCENES = {
    "pair": Scene(
        "PAIR", "pair", ("Same colour: one gate to run.", "Draw a route to join them."),
        6.4,
        spawns=((0.1, (1, 0), (1, 3), 30.0, GREEN),),
        script=((1.0, "move", "right"), (1.35, "move", "right"), (1.7, "move", "right")),
    ),
    "coherence": Scene(
        "COHERENCE", "cyan", ("The ring is its time left.", "Empty: the pair is lost."),
        5.6,
        spawns=((0.1, (0, 1), (2, 2), 4.2, YELLOW),),
    ),
    "red_x": Scene(
        "RED X", "red", ("Your route would crash here.", "Wait, or draw around it."),
        6.6,
        spawns=((0.1, (0, 3), (2, 1), 30.0, VIOLET), (0.1, (1, 0), (1, 3), 30.0, GREEN)),
        script=((0.3, "commit", 0, [(0, 3), (0, 2), (0, 1), (1, 1), (2, 1)]),
                (2.0, "move", "right"),  # the violet qubit is on its way here: X
                (3.8, "move", "right"),  # it has gone by
                (4.15, "move", "right")),
    ),
    "miscal": Scene(
        "MISCALIBRATED", "miscal", ("3x slower, and the gate", "comes out worse."),
        6.8,
        spawns=((0.1, (1, 1), (1, 3), 30.0, BLUE),),
        script=((0.0, "special", "miscal", edge((1, 1), (1, 2))),
                (0.9, "move", "right"), (1.25, "move", "right")),
    ),
    "defect": Scene(
        "DEFECT", "red", ("Broken coupler:", "no route can cross it."),
        4.6,
        spawns=((0.1, (1, 0), (1, 3), 30.0, GREEN),),
        script=((0.0, "special", "defect", edge((1, 1), (1, 2))),
                (0.9, "move", "right"), (1.35, "move", "right"),  # blocked
                (1.9, "move", "up"), (2.25, "move", "right"), (2.6, "move", "down"),
                (2.95, "move", "right")),
    ),
    "speed": Scene(
        "SPEED QUBIT", "gold", ("Every qubit passing it", "travels 2x faster."),
        4.8,
        spawns=((0.1, (1, 0), (1, 3), 30.0, VIOLET),),
        script=((0.0, "special", "speed", ((1, 1),)),
                (0.8, "move", "right"), (1.1, "move", "right"), (1.4, "move", "right")),
    ),
    "bell": Scene(
        "BELL PAIR", "bell", ("Step onto one end,", "come out at the other."),
        5.2,
        spawns=((0.1, (0, 0), (2, 3), 30.0, YELLOW),),
        script=((0.0, "special", "bell", ((0, 1), (2, 2))),
                (1.0, "move", "right"), (1.6, "move", "right")),
    ),
}
# The title's legend, most important first, then the specials.
LEGEND = ("pair", "coherence", "red_x", "miscal", "defect", "speed", "bell")
# The HOW TO PLAY card: the core loop, then the one thing that goes wrong.
HOW_TO_PLAY = ("pair", "red_x")


def scripted(spawns) -> object:
    for t, a, b, coherence, _color in spawns:
        yield Spawn(t, a, b, coherence)
    yield Spawn(INF, (0, 0), (2, 3), 30.0)  # never arrives


def make_board(scene: Scene) -> Board:
    return Board(Lattice("square", 3, 4), 0, ("p1",), lives=10 ** 9, specials=False,
                 schedule=scripted(scene.spawns))


@dataclass
class ScenePlayer:
    """Plays a list of scenes one after the other, round and round."""

    order: tuple[str, ...]
    index: int = 0
    time: float = 0.0
    board: Board = field(init=False)
    _done: int = field(init=False, default=0)  # script steps already run

    def __post_init__(self):
        self._start(self.index)

    @property
    def scene(self) -> Scene:
        return SCENES[self.order[self.index]]

    def _start(self, index: int) -> None:
        self.index = index % len(self.order)
        self.time = 0.0
        self._done = 0
        self.board = make_board(self.scene)

    def update(self, dt: float) -> None:
        if self.time + dt >= self.scene.length:
            self._start(self.index + 1)
            return
        self.time += dt
        scene, b = self.scene, self.board
        while self._done < len(scene.script) and scene.script[self._done][0] <= self.time:
            _, action, *args = scene.script[self._done]
            self._done += 1
            if action == "move":
                b.move("p1", args[0])
            elif action == "commit":
                b.commit_route(args[0], args[1])
            elif action == "special":
                kind, where = args
                if kind in ("miscal", "defect"):
                    b.place_special(kind, edge_=where)
                else:
                    b.place_special(kind, nodes=where)
        b.update(dt)
        # the scene's colours, not the first free ones (red would read as the X)
        for pair in b.pairs.values():
            pair.color = scene.spawns[pair.id][4]


def dismisses(kind: str, elapsed: float, keyboard: bool) -> bool:
    """Does an input event close the HOW TO PLAY card?

    `kind` is "button" (any joystick button, either pad), "key" or anything
    else (stick, hat). Only presses after MIN_SHOW seconds count, and keys
    only while the keyboard is on (it is off on the cabinet).
    """
    if elapsed < MIN_SHOW:
        return False
    return kind == "button" or (kind == "key" and keyboard)
