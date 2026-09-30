"""Original pixel art, defined in code (no image assets).

Characters are palette-index grids (one char per pixel, "." transparent);
tiles and appliances are drawn procedurally with pygame primitives straight
onto the 480x360 internal surface, so every pixel is an art pixel. All of it
is built once and cached.
"""

from __future__ import annotations

from functools import lru_cache

import pygame

from overquqed import palette as P


def shade(c, f):
    return tuple(max(0, min(255, round(v * f))) for v in c)


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def grid_surface(rows: list[str], cmap: dict[str, tuple]) -> pygame.Surface:
    w = max(len(r) for r in rows)
    surf = pygame.Surface((w, len(rows)), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != "." and ch != " ":
                surf.set_at((x, y), cmap[ch])
    return surf


# --- chefs --------------------------------------------------------------------
# 16 x 22. Rows 0-6 hat, 7-11 head, 12-16 body, 17-21 legs (frame dependent).

_HAT = [
    "....ooo..ooo....",
    "...oWWWooHHHo...",
    "..oWWHHHHHHHHo..",
    ".oWWHHHhHHhHHho.",
    ".oWHHHHhHHhHHho.",
    "..ohhhhhhhhhho..",
    "...obbbbbbbbo...",
]
_HEAD_DOWN = [
    "..okssssssssko..",
    "..osseesseesso..",
    "..osseesseesso..",
    "..osrsssssssro..",
    "...oossssssoo...",
]
_HEAD_UP = [
    "..okkkkkkkkkko..",
    "..okkkkkkkkkko..",
    "..okkkkkkkkkko..",
    "..oKkkkkkkkkKo..",
    "...ooKKKKKKoo...",
]
_HEAD_RIGHT = [
    "..okkkksssssso..",
    "..okkkssssseeo..",
    "..okkksssssseo..",
    "..okkssssssrso..",
    "...ooosssssoo...",
]
_BODY_DOWN = [
    "...occccccccco..",
    ".oocaacccccaacoo",
    ".oscaaaaaaaacso.",
    ".ooaaaaaaaaaaoo.",
    "..oaaaaaaaaaao..",
]
_BODY_UP = [
    "...occccccccco..",
    ".ooccCcccccCccoo",
    ".osccccccccccso.",
    ".ooccaccccaccoo.",
    "..oCCCCCCCCCCo..",
]
_BODY_RIGHT = [
    "....occcccaao...",
    "...occcCccaao...",
    "...occsscaaao...",
    "...oCcccaaaao...",
    "...oaaaaaaaao...",
]
_LEGS_FRONT = [
    [  # stand
        "..oppppppppppo..",
        "...oppo..oppo...",
        "...oppo..oppo...",
        "...offo..offo...",
        "...oooo..oooo...",
    ],
    [  # step A
        "..oppppppppppo..",
        "...oppo..oppo...",
        "...offo..oppo...",
        "...oooo..offo...",
        "..........oooo..",
    ],
    [  # step B
        "..oppppppppppo..",
        "...oppo..oppo...",
        "...oppo..offo...",
        "...offo..oooo...",
        "..oooo..........",
    ],
]
_LEGS_SIDE = [
    [
        "...oppppppppo...",
        ".....oppppo.....",
        ".....oppppo.....",
        ".....offffo.....",
        ".....oooooo.....",
    ],
    [
        "...oppppppppo...",
        "....oppo.oppo...",
        "...oppo...oppo..",
        "..offo.....offo.",
        "..ooo.......ooo.",
    ],
    [
        "...oppppppppo...",
        ".....oppppo.....",
        ".....oppppo.....",
        ".....offffo.....",
        ".....oooooo.....",
    ],
]


def _chef_cmap(color) -> dict[str, tuple]:
    return {
        "o": P.INK,
        "H": color, "h": shade(color, 0.72), "W": mix(color, (255, 255, 255), 0.55),
        "b": shade(color, 0.45),
        "s": (255, 206, 160), "r": (246, 140, 130), "e": P.INK,
        "k": (110, 66, 44), "K": (78, 44, 30),
        "c": (250, 248, 244), "C": (204, 208, 222),
        "a": shade(color, 0.85),
        "p": (60, 56, 84), "f": (40, 30, 34),
    }


@lru_cache(maxsize=None)
def chef_frames(color: tuple) -> dict[tuple[str, int], pygame.Surface]:
    cmap = _chef_cmap(color)
    frames: dict[tuple[str, int], pygame.Surface] = {}
    for direction in ("down", "up", "right"):
        head = {"down": _HEAD_DOWN, "up": _HEAD_UP, "right": _HEAD_RIGHT}[direction]
        body = {"down": _BODY_DOWN, "up": _BODY_UP, "right": _BODY_RIGHT}[direction]
        legs = _LEGS_SIDE if direction == "right" else _LEGS_FRONT
        for f in range(3):
            rows = _HAT + head + body + legs[f]
            frames[(direction, f)] = grid_surface(rows, cmap)
    for f in range(3):
        frames[("left", f)] = pygame.transform.flip(frames[("right", f)], True, False)
    return frames


# --- guests ---------------------------------------------------------------------
# 16 x 22 base body; each guest recolours it and adds an accessory overlay.

_GUEST_BASE = [
    "................",
    "................",
    "................",
    "................",
    ".....oooooo.....",
    "....okkkkkko....",
    "...okkkkkkkko...",
    "...okssssssko...",
    "...osseesseso...",
    "...osseesseso...",
    "...osrssssrso...",
    "....ossssssoo...",
    "...oJJJJJJJJo...",
    "..oJJjJJJJjJJo..",
    "..osJJJJJJJJso..",
    "..ooJJJJJJJJoo..",
    "...oJJJJJJJJo...",
    "...oLLLLLLLLo...",
    "...oLLo..oLLo...",
    "...oLLo..oLLo...",
    "...offo..offo...",
    "...oooo..oooo...",
]

_GUEST_LOOKS = {
    # key: (skin, hair, jumper, jumper detail, legs)
    "surface": ((255, 206, 160), (40, 40, 60), (90, 150, 250), (250, 250, 255), (60, 60, 90)),
    "steane": ((230, 180, 140), (200, 200, 210), (120, 80, 170), (170, 130, 220), (60, 50, 80)),
    "grover": ((255, 214, 170), (150, 90, 40), (60, 150, 90), (120, 200, 140), (70, 60, 50)),
    "dj": ((200, 150, 110), (30, 30, 30), (220, 120, 60), (250, 190, 110), (60, 50, 60)),
    "alice": ((255, 210, 180), (240, 180, 60), (240, 100, 140), (255, 170, 200), (80, 60, 90)),
    "bob": ((170, 120, 90), (50, 30, 20), (60, 120, 220), (130, 180, 250), (50, 50, 70)),
    "knill": ((240, 196, 160), (120, 60, 40), (80, 80, 110), (140, 140, 180), (50, 50, 60)),
    "shor": ((255, 214, 190), (240, 150, 60), (200, 70, 80), (250, 140, 140), (70, 50, 60)),
    "chefket": ((255, 206, 160), (90, 60, 40), (250, 248, 244), (255, 206, 72), (60, 56, 84)),
}


def _guest_accessory(key: str, surf: pygame.Surface, look) -> None:
    ink = P.INK
    if key == "surface":
        # checkerboard jumper (a surface-code lattice)
        for y in range(12, 17):
            for x in range(3, 13):
                if surf.get_at((x, y))[3] and surf.get_at((x, y))[:3] == look[2]:
                    if (x + y) % 2:
                        surf.set_at((x, y), (250, 250, 255))
    elif key == "steane":
        # tall hat with 7 dots
        pygame.draw.rect(surf, ink, (3, 0, 10, 6))
        pygame.draw.rect(surf, (70, 60, 140), (4, 1, 8, 4))
        pygame.draw.rect(surf, ink, (2, 5, 12, 1))
        for i, (x, y) in enumerate(((5, 2), (7, 2), (9, 2), (11, 2), (6, 3), (8, 3), (10, 3))):
            surf.set_at((x - 1, y), (255, 230, 90))
    elif key == "grover":
        # magnifying glass in hand
        pygame.draw.circle(surf, ink, (14, 12), 3)
        pygame.draw.circle(surf, (170, 220, 255), (14, 12), 2)
        pygame.draw.line(surf, ink, (13, 15), (12, 17))
    elif key == "dj":
        # two-faced coin badge
        pygame.draw.circle(surf, ink, (8, 14), 3)
        pygame.draw.rect(surf, (255, 210, 70), (6, 13, 2, 3))
        pygame.draw.rect(surf, (200, 205, 215), (8, 13, 2, 3))
    elif key == "knill":
        # teleporter backpack straps + glowing pack peeking out
        pygame.draw.rect(surf, ink, (0, 11, 4, 7))
        pygame.draw.rect(surf, (90, 230, 250), (1, 12, 2, 5))
        pygame.draw.line(surf, (60, 60, 80), (5, 12), (5, 16))
    elif key == "shor":
        # cat ears
        for x0 in (3, 10):
            pygame.draw.polygon(surf, ink, [(x0, 6), (x0 + 1, 2), (x0 + 3, 5)])
            pygame.draw.line(surf, (250, 170, 170), (x0 + 1, 4), (x0 + 1, 5))
    elif key == "chefket":
        # the mentor wears a gold-band toque
        pygame.draw.rect(surf, ink, (3, 0, 10, 6))
        pygame.draw.rect(surf, (255, 255, 255), (4, 0, 8, 5))
        pygame.draw.rect(surf, P.GOLD, (4, 4, 8, 1))


@lru_cache(maxsize=None)
def guest_frames(key: str) -> tuple[pygame.Surface, pygame.Surface]:
    """(idle, step) frames for one guest look."""
    skin, hair, jumper, detail, legs = _GUEST_LOOKS[key]
    cmap = {
        "o": P.INK, "k": hair, "s": skin, "e": P.INK, "r": mix(skin, (240, 110, 110), 0.5),
        "J": jumper, "j": detail, "L": legs, "f": (40, 30, 34),
    }
    base = grid_surface(_GUEST_BASE, cmap)
    _guest_accessory(key, base, (skin, hair, jumper, detail, legs))
    step = base.copy()
    pygame.draw.rect(step, (0, 0, 0, 0), (3, 18, 10, 4))
    legs_rows = ["...oLLo..oLLo...", "...offo..oLLo...", "...oooo..offo...", "..........oooo.."]
    step.blit(grid_surface(legs_rows, cmap), (0, 18))
    return base, step


@lru_cache(maxsize=None)
def portrait(key: str) -> pygame.Surface:
    """16x16 head crop of a guest for tickets and the tutorial box."""
    idle = guest_frames(key)[0]
    surf = pygame.Surface((16, 16), pygame.SRCALPHA)
    surf.blit(idle, (0, 0), pygame.Rect(0, 0, 16, 16))
    return surf


# --- small icons ----------------------------------------------------------------


@lru_cache(maxsize=None)
def star(filled: bool, size: int = 1) -> pygame.Surface:
    rows = [
        "....o....",
        "...oYo...",
        "oooYYYooo",
        "oYYYWYYYo",
        ".oYYYYYo.",
        "..oYYYo..",
        ".oYYoYYo.",
        ".oYo.oYo.",
        ".oo...oo.",
    ]
    col = (255, 210, 60) if filled else (90, 80, 100)
    surf = grid_surface(rows, {"o": P.INK, "Y": col, "W": (255, 250, 200) if filled else col})
    if size != 1:
        surf = pygame.transform.scale(surf, (9 * size, 9 * size))
    return surf


@lru_cache(maxsize=None)
def bubble_bang() -> pygame.Surface:
    rows = [
        ".ooooo.",
        "oWWRWWo",
        "oWWRWWo",
        "oWWRWWo",
        "oWWWWWo",
        "oWWRWWo",
        ".ooooo.",
        "...oo..",
        "...o...",
    ]
    return grid_surface(rows, {"o": P.INK, "W": (255, 255, 255), "R": (230, 50, 60)})


@lru_cache(maxsize=None)
def heart() -> pygame.Surface:
    rows = [".oo.oo.", "oRRoRRo", "oRRRRRo", ".oRRRo.", "..oRo..", "...o..."]
    return grid_surface(rows, {"o": P.INK, "R": (250, 80, 110)})


@lru_cache(maxsize=None)
def angry() -> pygame.Surface:
    rows = ["o.o.o", ".ooo.", "ooRoo", ".ooo.", "o.o.o"]
    return grid_surface(rows, {"o": (230, 50, 50), "R": (255, 200, 60)})
