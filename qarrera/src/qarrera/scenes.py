"""The tracks' scenes, each from an arqade game, with only what that game
really has (see the logo notes in ../../../AGENTS.md):

- space (Pauli Invaders): the track floats in the game's near-black space
  over a starfield far below, jellyfish invaders hovering in formation in
  the loops.
- chip (Superconductor): the track laid over the game's chip: its lattice
  of Xmon qubits and couplers on the dark substrate, Xmons standing proud
  here and there.
- surf (Ion Surfer): the track floats over the game's blue sea, foam lines
  drifting past, in the warm light of its sunset poster.

A Scene gives the track slab its colours, the light and fog, the ground
plane and the picture painted on it (pygame, tiled), and the voxel props.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import pygame

from qarrera import config
from qarrera.voxels import PAULI


@dataclass(frozen=True)
class Palette:
    bed: tuple
    side: tuple
    edge: tuple
    kerb: tuple
    kerb_alt: tuple
    wire: tuple
    lip: tuple  # the kickers' warning stripes


@dataclass
class Scene:
    key: str
    palette: Palette
    clear: tuple  # the colour behind everything
    light: tuple  # where the sunlight goes (gl coordinates)
    sun: tuple
    ambient: tuple
    fog: tuple
    fog_range: tuple
    ground_z: float
    ground_color: tuple
    ground_tile: float  # world units per repeat of the ground picture
    scroll: tuple = (0.0, 0.0)  # the ground picture drifts (tiles per second)
    props: list = field(default_factory=list)  # (model key, x, y, z, heading, scale)

    def ground_picture(self) -> pygame.Surface:
        return PAINTERS[self.key](random.Random(7))


# --- the pictures painted on the ground (one tile each) ------------------------------------------

def paint_space(rng: random.Random) -> pygame.Surface:
    s = pygame.Surface((256, 256))
    s.fill((5, 6, 13))  # the game's BG
    for _ in range(140):
        x, y = rng.randrange(256), rng.randrange(256)
        if rng.random() < 0.12:
            c = tuple(int(v * 0.7) for v in PAULI[rng.choice("XZY")])
        else:
            g = rng.randint(70, 230)
            c = (g, g, min(255, g + 20))
        s.fill(c, (x, y, 2 if rng.random() < 0.2 else 1, 1))
    return s


SUBSTRATE, SUBSTRATE_EDGE = (13, 17, 32), (40, 52, 84)
COUPLER, QUBIT_IDLE = (48, 62, 96), (86, 104, 146)
GOLD = (255, 214, 102)


def paint_chip(rng: random.Random) -> pygame.Surface:
    """One lattice cell of the chip: an Xmon in the middle, couplers out to
    its neighbours, a faint grid."""
    s = pygame.Surface((128, 128))
    s.fill(SUBSTRATE)
    for i in range(0, 128, 32):
        pygame.draw.line(s, (17, 22, 40), (i, 0), (i, 127))
        pygame.draw.line(s, (17, 22, 40), (0, i), (127, i))
    pygame.draw.line(s, COUPLER, (78, 64), (127, 64), 3)
    pygame.draw.line(s, COUPLER, (0, 64), (50, 64), 3)
    pygame.draw.line(s, COUPLER, (64, 0), (64, 50), 3)
    pygame.draw.line(s, COUPLER, (64, 78), (64, 127), 3)
    for d in (-1, 1):
        s.fill(QUBIT_IDLE, (64 - 12, 64 - 2, 25, 5))
        s.fill(QUBIT_IDLE, (64 - 2, 64 - 12, 5, 25))
    s.fill(GOLD, (4, 4, 8, 4))
    return s


def paint_sea(rng: random.Random) -> pygame.Surface:
    s = pygame.Surface((128, 128))
    s.fill((30, 74, 150))
    for y in range(0, 128, 2):
        if (y // 2) % 9 == 0:
            s.fill((26, 64, 136), (0, y, 128, 2))
    for _ in range(9):  # foam lines
        x0, y0 = rng.randrange(128), rng.randrange(128)
        for k in range(rng.randint(8, 18)):
            x = (x0 + k * 2) % 128
            y = (y0 + int(2 * math.sin(k * 0.6))) % 128
            s.fill((200, 230, 255) if k % 4 else (150, 190, 240), (x, y, 2, 1))
    return s


PAINTERS = {"space": paint_space, "chip": paint_chip, "surf": paint_sea}


# --- the scenes ---------------------------------------------------------------------------------

def _off_track(track, x: float, y: float, room: float) -> bool:
    return all(math.hypot(track.cx[k] - x, track.cy[k] - y) > room + 2 * config.LANE_W
               for k in range(0, track.n, 8))


def scene_for(track) -> Scene:
    env = track.d.env
    xs, ys = track.cx, track.cy
    if env == "space":
        props = []
        loops = [(min(xs) + 250, sum(ys) / len(ys)), (max(xs) - 250, sum(ys) / len(ys))]
        for (cx, cy), kinds in zip(loops, ("XZY", "ZYX")):
            for i, k in enumerate(kinds):
                props.append((f"prop_jelly_{k}", cx - 70 + 70 * i, cy + (30 if i == 1 else -15), 18.0, math.pi / 2, 1.6))
        return Scene("space", Palette(bed=(24, 26, 50), side=(36, 40, 78), edge=(70, 80, 140), kerb=PAULI["X"],
                                      kerb_alt=PAULI["Z"], wire=(110, 140, 240), lip=(255, 211, 107)),
                     clear=(5, 6, 13), light=(-0.45, 0.35, -0.82), sun=(0.85, 0.85, 0.95), ambient=(0.38, 0.38, 0.5),
                     fog=(5, 6, 13), fog_range=(700.0, 1600.0), ground_z=-420.0, ground_color=(255, 255, 255),
                     ground_tile=420.0, props=props)
    if env == "chip":
        rng = random.Random(3)
        props = []
        while len(props) < 14:
            x = rng.uniform(min(xs) - 150, max(xs) + 150)
            y = rng.uniform(min(ys) - 150, max(ys) + 150)
            if _off_track(track, x, y, 40):
                props.append(("prop_xmon", x, y, -9.0, 0.0, 2.0))
        return Scene("chip", Palette(bed=(28, 34, 60), side=(48, 60, 98), edge=(90, 104, 146), kerb=GOLD,
                                     kerb_alt=(250, 250, 255), wire=(90, 210, 255), lip=GOLD),
                     clear=(6, 8, 18), light=(-0.4, 0.45, -0.8), sun=(0.8, 0.82, 0.95), ambient=(0.4, 0.42, 0.55),
                     fog=(6, 8, 18), fog_range=(650.0, 1500.0), ground_z=-9.0, ground_color=(255, 255, 255),
                     ground_tile=96.0, props=props)
    return Scene("surf", Palette(bed=(30, 40, 80), side=(250, 211, 150), edge=(78, 168, 255), kerb=(255, 211, 107),
                                 kerb_alt=(255, 84, 112), wire=(110, 190, 255), lip=(255, 211, 107)),
                 clear=(40, 92, 170), light=(-0.55, 0.2, -0.8), sun=(1.0, 0.86, 0.7), ambient=(0.42, 0.42, 0.55),
                 fog=(255, 170, 130), fog_range=(600.0, 1700.0), ground_z=-16.0, ground_color=(255, 255, 255),
                 ground_tile=150.0, scroll=(0.02, 0.012))
