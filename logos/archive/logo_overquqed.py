"""Overquqed key art: two chefs dash in to entangle a Bell pair.

The back of the picture is a real kitchen, drawn by the game's own
render.build_background() from a small custom map (fridge, Pauli-X stove,
Hadamard blender, Phase Stirrer, sink, bin, pass) at x4. In front of it, at
x10, the two chefs from sprites.chef_frames() run in from either side -- P1
in the game's teal, P2 in its pink -- each carrying a Bloch Bowl overhead
(render.draw_bowl: |+> and |0>). Between them, at x8, sits the CNOT Waffle
Iron, cut from a second build_background() kitchen, spitting sparks. A gold
link, drawn the way render.draw_item draws an entangled tray, arcs from bowl
to bowl, and the |Phi+> they are about to make floats at its top in the
wordmark's style, built from ket.ket_surface().

Everything pixel-art is drawn at its native size and scaled up with nearest
neighbour, so it keeps the game's chunky 480x360 look; only the lights and
glows are soft.
"""

from __future__ import annotations

import dataclasses
import math
import random
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "overquqed/src"))

from overquqed import circuit, palette as P, render, sprites  # noqa: E402
from overquqed.config import KITCHEN_Y, TILE  # noqa: E402
from overquqed.ket import ket_surface  # noqa: E402
from overquqed.levels import TUTORIAL  # noqa: E402
from overquqed.world import World  # noqa: E402

ROM = "overquqed"

# Kitchens made for the picture, in the game's own map legend (levels.py):
# the back wall's counter, and a lone CNOT Waffle Iron (c = control half,
# t = target half) for the foreground.
KITCHEN = (
    "############",
    "#F=X=H=Z=RB#",
    "#..........#",
    "#.1......2.#",
    "#..........#",
    "#..........#",
    "#..........#",
    "#===PPPP===#",
    "############",
)
WAFFLE = (
    "####",
    "#ct#",
    "#12#",
    "####",
)
BACK_SCALE = 4  # the kitchen
MID_SCALE = 8  # the Waffle Iron
FRONT_SCALE = 10  # the chefs and their bowls, close to the viewer

# Title colours: the in-game logo (scenes.draw_logo) is white with gold Qs.
CREAM = [(255, 255, 250), (255, 246, 226), (250, 214, 166)]
GOLD = [(255, 246, 170), P.GOLD, (246, 150, 40)]
EXTRUDE = (70, 34, 52)
GLOW = (255, 150, 60)

VEC_PLUS = (1.0, 0.0, 0.0)  # |+>: Bloch arrow toward the viewer
VEC_ZERO = (0.0, 0.0, 1.0)  # |0>: straight up


def _background(level_map) -> pygame.Surface:
    """A full 480x360 frame of a kitchen, exactly as the game pre-renders it."""
    return render.build_background(World(dataclasses.replace(TUTORIAL, map=level_map)))


def _steam(surf: pygame.Surface, x: int, y: int, rng: random.Random, n: int = 7) -> None:
    """Little pixel puffs rising off a pan, thinning as they go."""
    for i in range(n):
        py = y - i * 4 - rng.randint(0, 2)
        px = x + round(3 * math.sin(i * 1.3 + rng.random()))
        a = max(40, 200 - i * 26)
        size = 3 if i < 3 else 2
        puff = pygame.Surface((size, size), pygame.SRCALPHA)
        puff.fill((255, 250, 240, a))
        surf.blit(puff, (px, py))


def _back(size: int) -> pygame.Surface:
    """Kitchen at x4, dimmed and vignetted, with the stove and pot steaming."""
    native = pygame.Surface((256, 256))
    # crop so map row 0 lands 64 px down: the HUD-coloured strip above it is
    # the dark band the title sits on
    native.blit(_background(KITCHEN), (0, 0), pygame.Rect(16, KITCHEN_Y - 64, 256, 256))

    def tile(tx, ty):  # top-left of a map tile inside the crop
        return tx * TILE - 16, ty * TILE + 64

    rng = random.Random(3)
    sx, sy = tile(3, 1)
    _steam(native, sx + 10, sy - 1, rng)
    zx, zy = tile(7, 1)
    _steam(native, zx + 11, zy, rng)

    surf = kit.nearest(native, BACK_SCALE)
    dim = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    dim.fill((*P.BG, 140))
    surf.blit(dim, (0, 0))
    # warm light pooling where the action is
    surf.blit(kit.radial(surf.get_size(), (size / 2, size * 0.55), size * 0.6, (130, 70, 26)), (0, 0),
              special_flags=pygame.BLEND_ADD)
    return kit.finish(surf, vignette_strength=0.8)


def _waffle_iron() -> pygame.Surface:
    """The two-tile CNOT Waffle Iron (grill, gold trim, control dot and
    target plates) cut out of its own kitchen, with sparks flying off it."""
    bg = _background(WAFFLE)
    native = pygame.Surface((2 * TILE + 16, TILE + 16), pygame.SRCALPHA)
    native.blit(bg, (8, 16), pygame.Rect(TILE, KITCHEN_Y + TILE, 2 * TILE, TILE))
    pygame.draw.rect(native, P.INK, (7, 15, 2 * TILE + 2, TILE + 2), 1)
    # glowing grill: the game's (60, 64, 76) waffle cells, heated up
    for gx in range(8 + 5, 8 + 2 * TILE - 4, 4):
        for gy in range(16 + 4, 16 + 13, 4):
            if native.get_at((gx, gy))[:3] == (60, 64, 76):
                native.fill((255, 160, 60) if (gx // 4 + gy // 4) % 2 else (255, 210, 90), (gx, gy, 2, 2))
    return native


def _chef(color, facing: str, frame: int) -> pygame.Surface:
    return sprites.chef_frames(color)[(facing, frame)]


def _bowl(v) -> pygame.Surface:
    """One Bloch Bowl at native size, drawn by the game's draw_bowl."""
    r = render.BOWL_R
    s = pygame.Surface((2 * r + 4, 2 * r + 8), pygame.SRCALPHA)
    render.draw_bowl(s, r + 2, r + 2, v, r, 1.0, 0.0, 0)
    return s


def _front(size: int) -> tuple[pygame.Surface, list[tuple[int, int]]]:
    """Chefs and bowls at x10; returns the layer and the bowls' centres (final px)."""
    k = FRONT_SCALE
    n = -(-size // k)
    native = pygame.Surface((n, n), pygame.SRCALPHA)
    bowls = []
    # (colour, facing, walk frame, feet x, feet y, bowl vector)
    cast = [
        (P.P1, "right", 1, 22, 100, VEC_PLUS),
        (P.P2, "left", 2, round(size / k) - 22, 92, VEC_ZERO),  # mid-leap
    ]
    floor = 100
    for color, facing, frame, fx, fy, vec in cast:
        d = 1 if facing == "right" else -1
        # speed lines and a dust puff trailing behind
        for i, (ly, ln) in enumerate(((fy - 14, 9), (fy - 9, 13), (fy - 4, 7))):
            x0 = fx - d * (11 + i * 2)
            line = pygame.Surface((ln, 1), pygame.SRCALPHA)
            line.fill((255, 246, 226, 150 - i * 30))
            native.blit(line, (x0 - (ln if d > 0 else 0), ly))
        for dx, dy, s in ((-9, -2, 3), (-13, -4, 2), (-6, -1, 2)):
            puff = pygame.Surface((s, s), pygame.SRCALPHA)
            puff.fill((240, 226, 200, 170))
            native.blit(puff, (fx + d * dx - (s if d < 0 else 0), fy + dy))
        # shadow and sprite, placed the way KitchenView.draw places them
        shadow = pygame.Surface((14, 5), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (*kit.shade(P.FLOOR_B, 0.35), 150), (0, 0, 14, 5))
        native.blit(shadow, (fx - 7, floor - 3))
        native.blit(_chef(color, facing, frame), (fx - 8, fy - 22))
        # held overhead: render.held_item_pos, 25 px above the chef's centre
        # (which is 5 px above the feet)
        bx, by = fx + d * 2, fy - 5 - 25
        native.blit(_bowl(vec), (bx - render.BOWL_R - 2, by - render.BOWL_R - 2))
        bowls.append((bx * k, by * k))
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    out.blit(kit.nearest(native, k), (0, 0))
    return out, bowls


def _link(size: int, bowls: list[tuple[int, int]], apex_y: float) -> pygame.Surface:
    """The gold entanglement link, at x4: render.draw_item's tray thread
    (ink under gold) stretched into a big arc from bowl to bowl, with the
    sparkle squares it throws when a CNOT links two bowls."""
    n = size // BACK_SCALE
    native = pygame.Surface((n, n), pygame.SRCALPHA)
    r = render.BOWL_R * FRONT_SCALE / BACK_SCALE
    # leave each bowl from its upper inner shoulder
    (ax, ay), (bx, by) = [(x / BACK_SCALE, y / BACK_SCALE) for x, y in bowls]
    ax, ay = ax + r * 0.6, ay - r * 0.8
    bx, by = bx - r * 0.6, by - r * 0.8
    # quadratic bezier whose midpoint is at apex_y
    mx, my = (ax + bx) / 2, 2 * apex_y / BACK_SCALE - (ay + by) / 2
    pts = []
    for i in range(61):
        t = i / 60
        x = (1 - t) ** 2 * ax + 2 * (1 - t) * t * mx + t * t * bx
        y = (1 - t) ** 2 * ay + 2 * (1 - t) * t * my + t * t * by
        pts.append((round(x), round(y)))
    pygame.draw.lines(native, P.INK, False, [(x, y + 1) for x, y in pts], 4)
    pygame.draw.lines(native, P.GOLD, False, pts, 2)
    for x, y in pts[::6]:
        native.fill((255, 250, 210), (x, y - 1, 1, 1))
    rng = random.Random(11)
    for i in range(34):
        x, y = pts[rng.randrange(len(pts))]
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(4, 16)
        native.fill(P.GOLD if i % 2 else P.WHITE, (round(x + math.cos(a) * rr), round(y + math.sin(a) * rr), 2, 2))
    layer = kit.nearest(native, BACK_SCALE)
    out = pygame.Surface(layer.get_size(), pygame.SRCALPHA)
    out.blit(kit.glow(layer, P.GOLD, 18, 0.55), (0, 0))
    out.blit(layer, (0, 0))
    return out


def _labels(size: int, bowls: list[tuple[int, int]]) -> pygame.Surface:
    """The small in-game ket labels over each bowl (ket_surface, x4)."""
    n = size // BACK_SCALE
    native = pygame.Surface((n, n), pygame.SRCALPHA)
    r = render.BOWL_R * FRONT_SCALE / BACK_SCALE
    for tokens, (x, y) in zip((("+",), ("0",)), bowls):
        k = ket_surface(tokens)
        x, y = x / BACK_SCALE, y / BACK_SCALE - r - 3
        native.blit(k, (round(x - k.get_width() / 2), round(y - k.get_height())))
    return kit.nearest(native, BACK_SCALE)


def _sparks(size: int, center: tuple[float, float]) -> pygame.Surface:
    """Sparks and the CNOT gate flash (render.KitchenView._gate_flash)
    rising off the Waffle Iron, at x4."""
    n = size // BACK_SCALE
    native = pygame.Surface((n, n), pygame.SRCALPHA)
    cx, cy = round(center[0] / BACK_SCALE), round(center[1] / BACK_SCALE)
    rng = random.Random(5)
    for i in range(30):
        a = rng.uniform(math.pi * 1.1, math.pi * 1.9)
        rr = rng.uniform(10, 34)
        x, y = cx + math.cos(a) * rr * 1.5, cy + math.sin(a) * rr
        native.fill((255, 210, 90) if i % 3 else P.WHITE, (round(x), round(y), 2, 2))
    layer = kit.nearest(native, BACK_SCALE)
    # the gate flash is drawn bigger, at x6, so it reads as a CNOT
    flash = pygame.Surface((27, 19), pygame.SRCALPHA)
    pygame.draw.line(flash, P.WHITE, (0, 4), (26, 4))
    pygame.draw.line(flash, P.WHITE, (0, 13), (26, 13))
    pygame.draw.line(flash, P.INK, (13, 4), (13, 13))
    circuit.draw_control(flash, 13, 4)
    circuit.draw_target(flash, 13, 13)
    kit.blit_center(layer, kit.nearest(flash, 6), (center[0], center[1] - 30 * BACK_SCALE))
    out = pygame.Surface(layer.get_size(), pygame.SRCALPHA)
    out.blit(kit.glow(layer, (255, 170, 60), 14, 0.5), (0, 0))
    out.blit(layer, (0, 0))
    return out


def _title_shape(k: int) -> tuple[pygame.Surface, list[int]]:
    """OVERQUQED in Press Start 2P at k x 8 px, and the indices of its Qs."""
    text = "OVERQUQED"
    return kit.text_shape(text, kit.PIXEL_FONT, 8 * k), [i for i, ch in enumerate(text) if ch == "Q"]


def _title(k: int, glow_radius: int = 26) -> pygame.Surface:
    """The ARQADE-style wordmark: cream letters with gold Qs, like the
    in-game logo. Two wordmarks from the same shape share every outline
    pixel, so the gold Q columns are cut from one into the other."""
    shape, qs = _title_shape(k)
    style = dict(gap=k // 4 + 1, outline=k // 3 + 1, extrude=k, extrude_color=EXTRUDE, square=True)
    cream = kit.wordmark(shape, CREAM, **style)
    gold = kit.wordmark(shape, GOLD, **style)
    # no glow in either, so the trimmed image starts exactly at the outline
    off = style["gap"] + style["outline"] - shape.get_bounding_rect().x
    for i in qs:
        col = pygame.Rect(off + i * 8 * k, 0, 8 * k, cream.get_height())
        cream.blit(gold, col, col)
    m = glow_radius * 2
    out = pygame.Surface((cream.get_width() + 2 * m, cream.get_height() + 2 * m), pygame.SRCALPHA)
    out.blit(kit.glow(kit.pad(cream, m), GLOW, glow_radius, 0.65), (0, 0))
    out.blit(cream, (m, m))
    return out


def _ket_emblem(k: int) -> pygame.Surface:
    """|Phi+> from the game's ket.py, as a gold wordmark."""
    shape = kit.nearest(ket_surface(("Phi+",), color=(255, 255, 255), outline=None), k)
    return kit.wordmark(shape, GOLD, gap=k // 3, outline=k // 3 + 1, extrude=k // 2 + 2,
                        extrude_color=EXTRUDE, glow_color=P.GOLD, glow_radius=22, glow_strength=0.7,
                        square=True)


def art(size: int) -> pygame.Surface:
    surf = _back(size)
    front, bowls = _front(size)
    iron = kit.nearest(_waffle_iron(), MID_SCALE)
    iron_rect = iron.get_rect(midbottom=(size // 2, size - 40))
    shadow = pygame.Surface((iron_rect.w, 40), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
    surf.blit(shadow, (iron_rect.x, iron_rect.bottom - 24))
    surf.blit(_sparks(size, (size / 2, iron_rect.y + 16 * MID_SCALE)), (0, 0))
    surf.blit(iron, iron_rect)
    apex = size * 0.47
    surf.blit(_link(size, bowls, apex), (0, 0))
    surf.blit(front, (0, 0))
    surf.blit(_labels(size, bowls), (0, 0))
    kit.blit_center(surf, _ket_emblem(8), (size / 2, apex))
    kit.blit_center(surf, _title(12), (size / 2, size * 0.14))
    kit.blit_center(surf, kit.tagline("a quantum kitchen for two chefs", 26, P.TEXT), (size / 2, size * 0.255))
    return surf


def marquee() -> pygame.Surface:
    """The wordmark flanked by the two chefs running in, P1 left, P2 right."""
    title = _title(16, glow_radius=20)
    k = 9
    p1 = kit.nearest(_chef(P.P1, "right", 1), k)
    p2 = kit.nearest(_chef(P.P2, "left", 2), k)
    gap = -30  # tuck the chefs into the title's glow margin
    w = p1.get_width() + title.get_width() + p2.get_width() + 2 * gap
    h = max(title.get_height(), p1.get_height())
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    out.blit(p1, (0, (h - p1.get_height()) // 2))
    out.blit(title, (p1.get_width() + gap, (h - title.get_height()) // 2))
    out.blit(p2, (w - p2.get_width(), (h - p2.get_height()) // 2))
    return kit.trim(out)
