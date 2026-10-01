"""Kitchen tiles that hold items or do something when used.

Each station is one map tile. What it accepts, whether B taps or holds it,
and how long a hold takes live here; the world applies the effects (it owns
the clock, the noise model and the order book).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from overquqed.quantum import QState

# map char -> station kind
KINDS = {
    "=": "counter", "F": "fridge", "X": "x", "H": "h", "Z": "z",
    "c": "control", "t": "target", "R": "sink", "B": "bin", "P": "pass",
    ">": "belt", "<": "belt",
}
TAP_GATES = {"x": "X", "z": "Z"}  # B tap applies the gate at once
HOLD_TIMES = {"h": 0.6, "press": 1.5, "sink": 1.0}  # seconds at gate_scale 1
BELT_SPEED = 1.25  # tiles per second
JAM_TIME = 5.0  # cosmic-ray hit

STATION_NAMES = {
    "counter": "Counter", "fridge": "Dilution Fridge", "x": "Pauli-X Flipper",
    "h": "Hadamard Blender", "z": "Phase Stirrer", "control": "CNOT Waffle Iron",
    "target": "CNOT Waffle Iron", "sink": "Reset Sink", "bin": "Bin", "pass": "Pass",
    "belt": "Conveyor",
}


class Item:
    """Something a chef can carry: a qubit bowl / linked tray (a QState), or
    a stack of dirty empty bowls (levels with a limited fridge)."""

    _next_uid = 1

    def __init__(self, state: QState | None = None, dirty: int = 0) -> None:
        self.state = state
        self.dirty = dirty
        self.uid = Item._next_uid
        Item._next_uid += 1
        self.anims: list[tuple[int, str, float, tuple[float, float, float]]] = []
        self.link_flash = -99.0  # world time the CNOT last linked it
        self.view: ItemView | None = None

    @property
    def is_qubit(self) -> bool:
        return self.state is not None

    @property
    def n(self) -> int:
        return self.state.n if self.state is not None else self.dirty

    def __repr__(self) -> str:
        if self.state is None:
            return f"<Item dirty x{self.dirty}>"
        return f"<Item n={self.state.n} {self.view.tokens if self.view else ''}>"


@dataclass
class ItemView:
    """What the renderer shows, refreshed at ~10 Hz and after every gate."""

    tokens: tuple[str, ...]
    prefix: str
    fidelity: float  # to the ideal noise-free state
    blochs: list[tuple[float, float, float]]
    entanglement: float


@dataclass
class Station:
    kind: str
    x: int
    y: int
    char: str
    item: Item | None = None
    progress: float = 0.0  # hold progress 0..1
    jam_until: float = -1.0
    belt_dir: int = 0  # +1 = '>', -1 = '<'
    belt_offset: float = 0.0  # 0..1 of the way to the next belt tile
    partner: "Station | None" = field(default=None, repr=False)  # c <-> t
    last_used: float = -99.0  # for the "gate flash" above the station

    @property
    def pos(self) -> tuple[int, int]:
        return self.x, self.y

    @property
    def holds_items(self) -> bool:
        return self.kind not in ("fridge", "bin", "pass")

    def accepts(self, item: Item) -> bool:
        if not self.holds_items:
            return False
        if self.item is not None:
            # dirty stacks merge on counters
            return self.kind == "counter" and not item.is_qubit and not self.item.is_qubit
        if self.kind in ("x", "h", "z", "control", "target"):
            return item.is_qubit
        return True

    def jammed(self, t: float) -> bool:
        return t < self.jam_until
