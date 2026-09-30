"""The four kitchens: ASCII maps plus every per-level tunable.

Legend: # wall  = counter  . floor  F Dilution Fridge  X Pauli-X Flipper
H Hadamard Blender  Z Phase Stirrer  c/t CNOT Waffle Iron control/target
R Reset Sink  B Bin  P Pass  > < conveyor belts  1 2 chef spawns.

Maps are 20 wide and (apart from the tutorial) 9 rows tall. Row 0 is drawn at
the top of the kitchen area (below the HUD); the dining room with the guest
queue is whatever is left below the map, under the pass: 3 rows for a
9-row map.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from overquqed.quantum import Noise


@dataclass(frozen=True)
class Level:
    key: str
    name: str
    blurb: str
    map: tuple[str, ...]
    duration: float  # seconds
    noise: Noise
    gate_scale: float = 1.0  # multiplies hold times (slow ion-trap gates)
    recipes: tuple[str, ...] = ("0", "1", "+")
    guests: tuple[str, ...] = ("surface",)
    spawn_interval: float = 16.0  # seconds between orders at the start...
    spawn_interval_end: float = 11.0  # ...and at the end of the round
    first_order_at: float = 2.0
    patience_scale: float = 1.0
    max_tickets: int = 4
    fridge_capacity: int | None = None  # None = unlimited qubits
    dirty_return_delay: float = 4.0  # served bowls come back to the pass
    two_chef_press: bool = False
    cosmic_rays: bool = False
    stars: tuple[int, int, int] = (60, 140, 220)
    show_hints: bool = True
    tutorial: bool = False
    # 1-player fallback balance: fewer, more patient guests
    solo_spawn_scale: float = 1.4
    solo_patience_scale: float = 1.3


TUTORIAL = Level(
    key="tutorial",
    name="Training Day",
    blurb="Chef Ket shows you the ropes. Under a minute!",
    map=(
        "####################",
        "#==F====X====H===B=#",
        "#..................#",
        "#..1............2..#",
        "#..................#",
        "#======PPPP========#",
        "####################",
    ),
    duration=math.inf,
    noise=Noise(),
    recipes=("0", "1", "+"),
    guests=("surface",),
    stars=(1, 2, 3),
    tutorial=True,
)

SNACK_BAR = Level(
    key="snackbar",
    name="Superconducting Snack Bar",
    blurb="Fast gates, short coherence. Learn gate order!",
    map=(
        "####################",
        "#=F===X======H===F=#",
        "#..................#",
        "#..1....====....2..#",
        "#.......=Z==.......#",
        "#..................#",
        "#..................#",
        "#=B=====PPPP=====B=#",
        "####################",
    ),
    duration=150.0,
    noise=Noise(t1=100.0, t2=45.0),
    recipes=("0", "1", "+", "-"),
    guests=("surface", "steane", "grover", "dj"),
    spawn_interval=13.0,
    spawn_interval_end=8.0,
    stars=(120, 260, 400),
)

TRATTORIA = Level(
    key="trattoria",
    name="Ion Trap Trattoria",
    blurb="Two trap zones, shuttle qubits on the belts. Needs both chefs!",
    map=(
        "####################",
        "#=F==X===##==H==Z=B#",
        "#........##........#",
        "#..1.....>>......2.#",
        "#........##........#",
        "#........<<........#",
        "#........##........#",
        "#=R==ct==##==PPPP==#",
        "####################",
    ),
    duration=150.0,
    noise=Noise(t1=200.0, t2=120.0),
    gate_scale=2.0,
    recipes=("0", "1", "+", "-", "Phi+"),
    guests=("surface", "grover", "dj", "alicebob", "knill"),
    spawn_interval=17.0,
    spawn_interval_end=12.0,
    patience_scale=1.3,
    fridge_capacity=4,
    stars=(100, 220, 340),
)

COSMIC_CAFE = Level(
    key="cosmic",
    name="Cosmic Cafe",
    blurb="Two-chef Waffle Iron. Watch out for cosmic rays!",
    map=(
        "####################",
        "#=F=X===H====Z==F==#",
        "#..................#",
        "#..1.....=c==t=..2.#",
        "#..................#",
        "#..................#",
        "#..B...........R...#",
        "#=====PPPPPPP======#",
        "####################",
    ),
    duration=180.0,
    noise=Noise(t1=100.0, t2=45.0),
    recipes=("0", "+", "-", "1", "Phi+", "Phi-", "Psi+", "GHZ", "Psi-"),
    guests=("surface", "steane", "grover", "dj", "alicebob", "knill", "shor"),
    spawn_interval=15.0,
    spawn_interval_end=10.0,
    patience_scale=1.2,
    two_chef_press=True,
    cosmic_rays=True,
    stars=(140, 300, 460),
)

LEVELS: tuple[Level, ...] = (TUTORIAL, SNACK_BAR, TRATTORIA, COSMIC_CAFE)
LEVELS_BY_KEY = {lv.key: lv for lv in LEVELS}
