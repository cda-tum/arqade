"""Drawing the kitchen: tiles, appliances, Bloch Bowls, chefs, overlays.

The static kitchen (floor, walls, counters, appliance bodies, symbol plates)
is pre-rendered once per level into one background surface; each frame
only blits that, then the dynamic bits on top: items, chefs, belts, hold
rings, highlights and effects.

Bloch Bowl projection (textbook view, slightly tilted): +x points toward the
viewer (down-left on screen), +y to the right, +z up. So |0> points straight
up, |1> straight down, |+> front-left and |-> back-right on the equator.
"""

from __future__ import annotations

import math
from functools import lru_cache

import pygame

from overquqed import circuit, palette as P, sprites
from overquqed.config import INTERNAL_HEIGHT, INTERNAL_WIDTH, KITCHEN_Y, TILE
from overquqed.fonts import text
from overquqed.ket import ket_surface
from overquqed.quantum import GATE_ROTATIONS, rotate
from overquqed.sprites import mix, shade
from overquqed.stations import Item, Station
from overquqed.world import ANIM_TIME, HALF_H, Chef, World

SYMBOLS = {"x": "X", "h": "H", "z": "Z"}
BOWL_R = 8
TRAY_R = 6
TRAY_PITCH = 16


def tile_px(tx: int, ty: int) -> tuple[int, int]:
    return tx * TILE, KITCHEN_Y + ty * TILE


def map_to_screen(x: float, y: float) -> tuple[int, int]:
    return round(x), round(y) + KITCHEN_Y


# --- Bloch bowls ------------------------------------------------------------------


def project(v, r: float) -> tuple[float, float]:
    x, y, z = v
    return r * (0.92 * y - 0.5 * x), r * (0.42 * x - 0.92 * z)


def arrow_color(v) -> tuple[int, int, int]:
    x, _, z = v
    if z > 0.55:
        return P.KET_0
    if z < -0.55:
        return P.KET_1
    if x > 0.55:
        return P.KET_PLUS
    if x < -0.55:
        return P.KET_MINUS
    return P.NOISE


@lru_cache(maxsize=None)
def sphere(r: int, stale: int = 0) -> pygame.Surface:
    """Glass sphere on a little stand. `stale` 0..3 frosts it over."""
    d = 2 * r + 1
    surf = pygame.Surface((d + 2, d + 5), pygame.SRCALPHA)
    c = (r + 1, r + 1)
    glass = mix((214, 238, 255), (196, 196, 204), stale / 3)
    pygame.draw.circle(surf, (*glass, 235), c, r)
    # darker lower half: reads as a sphere, and the equator separates the
    # "front" (|+>) and "back" (|->) halves
    lower = pygame.Surface((d + 2, d + 2), pygame.SRCALPHA)
    pygame.draw.circle(lower, (*shade(glass, 0.88), 235), c, r)
    surf.blit(lower, (0, c[1]), pygame.Rect(0, c[1], d + 2, r + 1))
    eq = pygame.Rect(1, r + 1 - max(1, round(r * 0.42)), d, max(2, round(r * 0.84)) + 1)
    pygame.draw.ellipse(surf, (*shade(glass, 0.62), 255), eq, 1)
    pygame.draw.circle(surf, P.INK, c, r, 1)
    # stand
    pygame.draw.rect(surf, P.INK, (c[0] - 4, d, 9, 4))
    pygame.draw.rect(surf, (176, 124, 84), (c[0] - 3, d, 7, 2))
    # glint
    for dx, dy in ((0, 0), (1, 0), (0, 1)):
        surf.set_at((c[0] - r // 2 + dx, c[1] - r // 2 - 1 + dy), (255, 255, 255))
    if stale:
        for i in range(stale * 4):
            a = i * 2.4
            px = round(c[0] + math.cos(a) * (r - 2) * ((i % 3) / 3 + 0.3))
            py = round(c[1] + math.sin(a) * (r - 2) * ((i % 3) / 3 + 0.3))
            surf.set_at((px, py), (250, 252, 255))
    return surf


def ease(p: float) -> float:
    p = min(1.0, max(0.0, p))
    return p * p * (3 - 2 * p)


def bowl_vector(item: Item, q: int, t: float):
    """Current arrow for bowl q, mid-rotation if a gate just hit it."""
    v = item.view.blochs[q]
    for aq, gate, t0, before in item.anims:
        if aq == q and t - t0 < ANIM_TIME:
            axis, angle = GATE_ROTATIONS[gate]
            return rotate(before, axis, angle * ease((t - t0) / ANIM_TIME))
    return v


def draw_bowl(surf, cx: int, cy: int, v, r: int, fidelity: float, t: float, seed: int) -> None:
    stale = 0 if fidelity > 0.95 else 1 if fidelity > 0.88 else 2 if fidelity > 0.8 else 3
    sp = sphere(r, stale)
    surf.blit(sp, (cx - r - 1, cy - r - 1))
    length = math.sqrt(sum(c * c for c in v))
    if length < 0.12:
        surf.fill(P.NOISE, (cx - 1, cy - 1, 2, 2))
    else:
        dx, dy = project(v, r - 1)
        tip = (round(cx + dx), round(cy + dy))
        col = arrow_color(v) if length > 0.5 else mix(arrow_color(v), P.NOISE, 0.6)
        pygame.draw.line(surf, P.INK, (cx, cy + 1), (tip[0], tip[1] + 1), 2)
        pygame.draw.line(surf, col, (cx, cy), tip, 2)
        surf.fill(mix(col, (255, 255, 255), 0.5), (tip[0] - 1, tip[1] - 1, 2, 2))
    if stale >= 2:
        # grey static crawling over a stale bowl
        k = int(t * 10) + seed * 7
        for i in range(2 + stale * 2):
            a = (k * 37 + i * 101) % 360
            rr = ((k * 13 + i * 29) % 100) / 100 * (r - 1)
            px = round(cx + math.cos(math.radians(a)) * rr)
            py = round(cy + math.sin(math.radians(a)) * rr)
            surf.set_at((px, py), (200, 200, 205))


def item_width(item: Item) -> int:
    if item.is_qubit and item.n > 1:
        return item.n * TRAY_PITCH + 3
    return 2 * BOWL_R + 2


def draw_item(surf, item: Item, cx: int, cy: int, t: float, show_bar: bool) -> None:
    """Draw an item centred on (cx, cy): bowl, linked tray or dirty stack.
    Labels are drawn in a later pass (draw_item_label) so they sit on top."""
    if not item.is_qubit:
        _draw_dirty(surf, item, cx, cy)
        return
    view = item.view
    if item.n == 1:
        draw_bowl(surf, cx, cy, bowl_vector(item, 0, t), BOWL_R, view.fidelity, t, item.uid)
    else:
        n = item.n
        w = n * TRAY_PITCH + 3
        x0 = cx - w // 2
        # tray plank
        pygame.draw.rect(surf, P.INK, (x0, cy + TRAY_R - 1, w, 5))
        pygame.draw.rect(surf, (196, 140, 90), (x0 + 1, cy + TRAY_R, w - 2, 3))
        centers = [x0 + 2 + TRAY_PITCH // 2 + i * TRAY_PITCH for i in range(n)]
        # the gold link: brighter the more entangled
        ent = view.entanglement
        pulse = 0.75 + 0.25 * math.sin(t * 6)
        link = mix((120, 110, 100), P.GOLD, min(1.0, ent * pulse + 0.1))
        flash = t - item.link_flash < 0.7
        for a, b in zip(centers, centers[1:]):
            # the thread between the bowls, arching over when entangled
            if ent > 0.1:
                mid = (a + b) // 2
                top = cy - TRAY_R - 4
                pts = [(a, cy - TRAY_R + 1), (mid - 3, top), (mid + 3, top), (b, cy - TRAY_R + 1)]
                pygame.draw.lines(surf, P.INK, False, [(x, y + 1) for x, y in pts], 3)
                pygame.draw.lines(surf, link, False, pts, 2)
            else:
                pygame.draw.line(surf, (120, 110, 100), (a, cy), (b, cy), 1)
        for q, x in enumerate(centers):
            draw_bowl(surf, x, cy, bowl_vector(item, q, t), TRAY_R, view.fidelity, t, item.uid + q)
        # first qubit marker: the one single-qubit stations act on
        pygame.draw.rect(surf, P.WHITE, (centers[0] - 2, cy + TRAY_R + 4, 5, 1))
        if flash:
            k = int((t - item.link_flash) * 20)
            for i in range(6):
                a = (i * 60 + k * 17) % 360
                rr = 5 + (k + i) % 6
                sx = round((centers[0] + centers[-1]) / 2 + math.cos(math.radians(a)) * rr * 1.6)
                sy = round(cy + math.sin(math.radians(a)) * rr)
                surf.fill(P.GOLD if i % 2 else P.WHITE, (sx, sy, 2, 2))
    if show_bar:
        w = max(14, item_width(item) - 4)
        bx, by = cx - w // 2, cy + (BOWL_R + 6 if item.n == 1 else TRAY_R + 8)
        f = view.fidelity
        col = P.GOOD if f >= 0.9 else P.WARN if f >= 0.8 else P.BAD
        pygame.draw.rect(surf, P.INK, (bx - 1, by - 1, w + 2, 4))
        fill = round(w * max(0.0, min(1.0, (f - 0.5) / 0.5)))
        pygame.draw.rect(surf, (60, 50, 70), (bx, by, w, 2))
        pygame.draw.rect(surf, col, (bx, by, fill, 2))
        # threshold tick at F = 0.8
        tx = bx + round(w * 0.6)
        surf.set_at((tx, by - 1), P.WHITE)


def draw_item_label(surf, item: Item, cx: int, cy: int) -> None:
    if not item.is_qubit or item.view is None:
        return
    k = ket_surface(item.view.tokens, item.view.prefix)
    top = cy - (BOWL_R if item.n == 1 else TRAY_R) - k.get_height() - 2
    surf.blit(k, (cx - k.get_width() // 2, top))


def _draw_dirty(surf, item: Item, cx: int, cy: int) -> None:
    for i in range(min(item.dirty, 4)):
        y = cy + 3 - i * 3
        pygame.draw.ellipse(surf, P.INK, (cx - 7, y - 3, 14, 7))
        pygame.draw.ellipse(surf, (200, 200, 190), (cx - 6, y - 2, 12, 5))
        surf.fill((140, 110, 80), (cx - 2 + i, y - 1, 3, 1))
    if item.dirty > 1:
        surf.blit(text(f"x{item.dirty}", 8, P.WHITE, shadow=P.INK), (cx + 6, cy - 6))


# --- the static kitchen --------------------------------------------------------------


def _outline_edges(s, world: World, tx: int, ty: int, px: int, py: int) -> None:
    for (dx, dy), rect in (
        ((-1, 0), (px, py, 1, TILE)), ((1, 0), (px + TILE - 1, py, 1, TILE)),
    ):
        if world.walkable(tx + dx, ty + dy):
            s.fill(P.INK, rect)


def _floor(s, tx, ty, px, py) -> None:
    base = P.FLOOR_A if (tx + ty) % 2 == 0 else P.FLOOR_B
    s.fill(base, (px, py, TILE, TILE))
    s.fill(shade(base, 0.93), (px, py, TILE, 1))
    s.fill(shade(base, 0.93), (px, py, 1, TILE))
    s.set_at((px + 5, py + 6), shade(base, 1.04))
    s.set_at((px + 16, py + 15), shade(base, 1.04))


def _wall(s, world: World, tx, ty, px, py) -> None:
    below = world.tiles[ty + 1][tx] if ty + 1 < world.h else None
    face = below is None or below != "#"
    if not face:
        s.fill(P.WALL, (px, py, TILE, TILE))
        s.fill(shade(P.WALL, 1.15), (px, py, TILE, 2))
        return
    if ty == 0:
        # back wall: dark cap, then a pale tiled backsplash
        s.fill(P.WALL, (px, py, TILE, 7))
        s.fill(P.WALL_TOP, (px, py + 5, TILE, 2))
        splash = (176, 214, 206)
        s.fill(splash, (px, py + 7, TILE, TILE - 7))
        for gy in (py + 12, py + 18):
            s.fill(shade(splash, 0.85), (px, gy, TILE, 1))
        for gx in (px + 7, px + 19):
            s.fill(shade(splash, 0.85), (gx, py + 7, 1, 5))
        for gx in (px + 1, px + 13):
            s.fill(shade(splash, 0.85), (gx, py + 13, 1, 5))
        s.fill(shade(splash, 0.7), (px, py + TILE - 1, TILE, 1))
    elif ty == world.h - 1:
        # low service wall towards the dining room
        s.fill(P.WALL_TOP, (px, py, TILE, 6))
        s.fill(shade(P.WALL_TOP, 1.2), (px, py, TILE, 1))
        s.fill(P.INK, (px, py + 6, TILE, 1))
        brick = (150, 70, 64)
        s.fill(brick, (px, py + 7, TILE, TILE - 7))
        for row, gy in enumerate(range(py + 7, py + TILE, 5)):
            s.fill(shade(brick, 0.78), (px, gy, TILE, 1))
            off = 0 if row % 2 else 6
            for gx in range(px + off, px + TILE, 12):
                s.fill(shade(brick, 0.78), (gx, gy, 1, 5))
        s.fill(P.INK, (px, py + TILE - 1, TILE, 1))
    else:
        # interior divider (ion-trap zones): top + a short face
        s.fill(P.WALL, (px, py, TILE, TILE - 8))
        s.fill(shade(P.WALL, 1.15), (px, py, TILE, 2))
        s.fill(P.WALL_TOP, (px, py + TILE - 8, TILE, 8))
        s.fill(P.INK, (px, py + TILE - 1, TILE, 1))
        # electrode stripes: it's an ion trap after all
        for gx in (px + 4, px + 12, px + 20):
            s.fill((255, 206, 72), (gx, py + TILE - 6, 2, 3))


def _counter(s, world: World, st: Station, px, py, top=P.COUNTER_TOP, front=P.COUNTER) -> bool:
    """Counter block; returns whether it has a visible front face."""
    below = world.tiles[st.y + 1][st.x] if st.y + 1 < world.h else "#"
    face = below not in "=FXHZctRBP<>"
    top_h = 16 if face else TILE
    s.fill(top, (px, py, TILE, top_h))
    s.fill(mix(top, (255, 255, 255), 0.25), (px, py, TILE, 1))
    for gy in (py + 5, py + 11):
        s.fill(shade(top, 0.92), (px + 2, gy, 9, 1))
        s.fill(shade(top, 0.92), (px + 14, gy + 2, 8, 1))
    if face:
        s.fill(P.INK, (px, py + 16, TILE, 1))
        s.fill(front, (px, py + 17, TILE, 7))
        s.fill(shade(front, 0.75), (px, py + TILE - 1, TILE, 1))
    _outline_edges(s, world, st.x, st.y, px, py)
    return face


def _plate(s, px, py, face: bool, draw) -> None:
    cy = py + 19 if face else py + 17
    draw(px + TILE // 2, cy)


def _station(s, world: World, st: Station, px: int, py: int) -> None:
    k = st.kind
    if k == "counter":
        _counter(s, world, st, px, py)
    elif k == "fridge":
        _counter(s, world, st, px, py)
        body = pygame.Rect(px + 1, py - 9, 22, 33)
        pygame.draw.rect(s, P.INK, body)
        pygame.draw.rect(s, (220, 236, 246), body.inflate(-2, -2))
        s.fill((170, 196, 216), (px + 2, py + 2, 20, 1))  # door split
        s.fill((170, 196, 216), (px + 20, py - 8, 2, 31))  # side shade
        s.fill(P.METAL_DARK, (px + 17, py - 5, 2, 5))  # handles
        s.fill(P.METAL_DARK, (px + 17, py + 5, 2, 7))
        # frost + snowflake
        for fx, fy in ((px + 4, py - 6), (px + 8, py - 7), (px + 12, py - 6)):
            s.fill((255, 255, 255), (fx, fy, 2, 1))
        sx, sy = px + 8, py - 2
        for dx, dy in ((0, -2), (0, 2), (-2, 0), (2, 0), (0, 0), (-1, -1), (1, 1), (1, -1), (-1, 1)):
            s.set_at((sx + dx, sy + dy), P.KET_0)
        k0 = ket_surface(("0",), scale=1)
        s.blit(k0, (px + 2, py + 8))
    elif k in SYMBOLS:
        face = _counter(s, world, st, px, py)
        if k == "x":  # stove + flip pan
            pygame.draw.rect(s, P.INK, (px + 2, py + 1, 20, 14))
            pygame.draw.rect(s, (70, 70, 84), (px + 3, py + 2, 18, 12))
            pygame.draw.circle(s, (230, 90, 40), (px + 11, py + 8), 6, 1)
            pygame.draw.circle(s, P.INK, (px + 11, py + 8), 6)
            pygame.draw.circle(s, (60, 64, 76), (px + 11, py + 8), 5)
            pygame.draw.line(s, P.INK, (px + 17, py + 8), (px + 23, py + 5), 3)
            pygame.draw.line(s, (150, 100, 70), (px + 17, py + 8), (px + 22, py + 5), 1)
        elif k == "h":  # blender base; the jar is drawn around the item
            pygame.draw.rect(s, P.INK, (px + 5, py + 9, 14, 7))
            pygame.draw.rect(s, (80, 170, 110), (px + 6, py + 10, 12, 5))
            s.fill((255, 255, 255), (px + 8, py + 12, 2, 1))
            s.fill((255, 90, 80), (px + 15, py + 12, 2, 1))
        elif k == "z":  # pot
            pygame.draw.rect(s, P.INK, (px + 2, py + 2, 20, 13))
            pygame.draw.rect(s, (150, 80, 170), (px + 3, py + 3, 18, 11))
            pygame.draw.rect(s, (190, 130, 210), (px + 3, py + 3, 18, 2))
            pygame.draw.rect(s, (60, 40, 70), (px + 5, py + 5, 14, 5))
        _plate(s, px, py, face, lambda cx, cy: circuit.draw_gate_box(s, SYMBOLS[k], cx, cy))
    elif k in ("control", "target"):
        face = _counter(s, world, st, px, py)
        pygame.draw.rect(s, P.INK, (px + 2, py + 1, 20, 14))
        pygame.draw.rect(s, (90, 96, 110), (px + 3, py + 2, 18, 12))
        for gx in range(px + 5, px + 20, 4):
            for gy in range(py + 4, py + 13, 4):
                s.fill((60, 64, 76), (gx, gy, 2, 2))
        s.fill((255, 206, 72), (px + 3, py + 13, 18, 1))

        def plate(cx, cy):
            pygame.draw.rect(s, P.INK, (cx - 5, cy - 5, 11, 10))
            pygame.draw.rect(s, P.WHITE, (cx - 4, cy - 4, 9, 8))
            if k == "control":
                circuit.draw_control(s, cx, cy)
            else:
                circuit.draw_target(s, cx, cy)

        _plate(s, px, py, face, plate)
    elif k == "sink":
        face = _counter(s, world, st, px, py, top=P.METAL, front=P.METAL_DARK)
        pygame.draw.rect(s, P.INK, (px + 3, py + 3, 18, 11))
        pygame.draw.rect(s, (120, 150, 180), (px + 4, py + 4, 16, 9))
        pygame.draw.rect(s, (90, 120, 150), (px + 4, py + 4, 16, 2))
        s.fill(P.INK, (px + 11, py, 3, 5))
        s.fill(P.METAL, (px + 12, py + 1, 1, 3))
        k0 = ket_surface(("0",))
        _plate(s, px, py, face, lambda cx, cy: s.blit(k0, (cx - k0.get_width() // 2, cy - 5)))
    elif k == "bin":
        below = world.tiles[st.y + 1][st.x] if st.y + 1 < world.h else "#"
        if below == "#" or st.y == 1:
            _counter(s, world, st, px, py)
        else:
            _floor(s, st.x, st.y, px, py)
        pygame.draw.rect(s, P.INK, (px + 4, py + 2, 16, 20))
        pygame.draw.rect(s, (110, 130, 120), (px + 5, py + 5, 14, 16))
        for gx in (px + 8, px + 12, px + 16):
            s.fill((80, 100, 90), (gx, py + 7, 1, 12))
        pygame.draw.rect(s, (150, 170, 160), (px + 3, py + 2, 18, 3))
        s.fill(P.INK, (px + 3, py + 5, 18, 1))
    elif k == "pass":
        face = _counter(s, world, st, px, py, top=(210, 214, 222), front=(200, 60, 60))
        if face:
            for gx in range(px, px + TILE, 6):
                s.fill((250, 240, 230), (gx, py + 18, 3, 5))
        if st.x % 2 == 0:
            pygame.draw.circle(s, P.INK, (px + 12, py + 9), 4)
            pygame.draw.circle(s, P.GOLD, (px + 12, py + 9), 3)
            s.fill(P.INK, (px + 8, py + 12, 9, 2))
            s.set_at((px + 11, py + 7), (255, 255, 230))
    elif k == "belt":
        pygame.draw.rect(s, P.INK, (px, py + 2, TILE, 20))
        pygame.draw.rect(s, (60, 62, 74), (px, py + 3, TILE, 18))
        s.fill(P.METAL, (px, py + 2, TILE, 2))
        s.fill(P.METAL, (px, py + 20, TILE, 2))


def build_background(world: World) -> pygame.Surface:
    bg = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
    bg.fill(P.HUD_BG)
    for ty in range(world.h):
        for tx in range(world.w):
            px, py = tile_px(tx, ty)
            ch = world.tiles[ty][tx]
            if ch == "#":
                _wall(bg, world, tx, ty, px, py)
            elif ch in ".12":
                _floor(bg, tx, ty, px, py)
    # stations after walls so tall ones (the fridge) can overlap the wall above
    for ty in range(world.h):
        for tx in range(world.w):
            st = world.station_at((tx, ty))
            if st is not None:
                _station(bg, world, st, *tile_px(tx, ty))
    # the CNOT wire: control dot and target joined across the counters
    for c in world.stations_of("control"):
        t = c.partner
        if t is not None and t.y == c.y and abs(t.x - c.x) > 1:
            y = tile_px(c.x, c.y)[1] + 19
            x0 = tile_px(min(c.x, t.x), c.y)[0] + 18
            x1 = tile_px(max(c.x, t.x), c.y)[0] + 6
            pygame.draw.line(bg, P.INK, (x0, y), (x1, y), 1)
    # dining room
    top = KITCHEN_Y + world.h * TILE
    for y in range(top, INTERNAL_HEIGHT, 6):
        row = (y - top) // 6
        c = P.DINING_A if row % 2 == 0 else P.DINING_B
        bg.fill(c, (0, y, INTERNAL_WIDTH, 6))
        off = (row * 37) % 60
        for x in range(off, INTERNAL_WIDTH, 60):
            bg.fill(shade(c, 0.8), (x, y, 1, 6))
    # shadow under the service wall
    bg.fill(shade(P.DINING_B, 0.6), (0, top, INTERNAL_WIDTH, 3))
    # entrance door on the left, exit on the right
    for x0 in (2, INTERNAL_WIDTH - 20):
        door = pygame.Rect(x0, top + 8, 18, INTERNAL_HEIGHT - top - 8)
        pygame.draw.rect(bg, P.INK, door)
        pygame.draw.rect(bg, (96, 58, 44), door.inflate(-4, -2).move(0, 1))
        pygame.draw.rect(bg, (120, 76, 56), (door.x + 4, door.y + 5, door.w - 8, 12))
        bg.fill(P.GOLD, (door.right - 6 if x0 < 100 else door.x + 4, door.y + 26, 2, 2))
    # a rug under the queue
    pass_xs = [s.x for s in world.stations_of("pass")]
    if pass_xs:
        rx0, rx1 = (min(pass_xs) - 1) * TILE, (max(pass_xs) + 2) * TILE
        rug = pygame.Rect(rx0, top + 10, rx1 - rx0, 32)
        pygame.draw.rect(bg, P.INK, rug)
        pygame.draw.rect(bg, (170, 60, 70), rug.inflate(-2, -2))
        pygame.draw.rect(bg, (230, 170, 90), rug.inflate(-6, -6), 1)
    return bg


# --- per-frame overlays ---------------------------------------------------------------


@lru_cache(maxsize=None)
def ring(progress_step: int, steps: int = 24, r: int = 8) -> pygame.Surface:
    """Hold-progress ring, `progress_step`/`steps` full, clockwise from top."""
    surf = pygame.Surface((2 * r + 3, 2 * r + 3), pygame.SRCALPHA)
    c = r + 1
    frac = progress_step / steps
    for y in range(2 * r + 3):
        for x in range(2 * r + 3):
            d = math.hypot(x - c, y - c)
            if r - 1.5 <= d <= r + 0.7:
                a = (math.atan2(x - c, -(y - c)) / (2 * math.pi)) % 1.0
                surf.set_at((x, y), P.GOLD if a <= frac else (60, 50, 70))
            elif r + 0.7 < d <= r + 1.6 or r - 2.5 <= d < r - 1.5:
                surf.set_at((x, y), P.INK)
    return surf


def draw_button_hint(surf, letter: str, cx: int, cy: int, color) -> None:
    pygame.draw.circle(surf, P.INK, (cx, cy), 6)
    pygame.draw.circle(surf, color, (cx, cy), 5)
    g = text(letter, 8, P.INK)
    surf.blit(g, (cx - 3, cy - 3))


def station_item_pos(st: Station) -> tuple[int, int]:
    px, py = tile_px(st.x, st.y)
    offset = st.belt_offset * TILE * st.belt_dir if st.kind == "belt" else 0
    return round(px + TILE // 2 + offset), py + (8 if st.kind != "belt" else 11)


def held_item_pos(chef: Chef) -> tuple[int, int]:
    """Carried overhead, so the item never hides the chef (and vice versa)."""
    x, y = map_to_screen(chef.x, chef.y)
    return x + chef.facing[0] * 2, y - 25


def chef_sprite(chef: Chef, color, t: float) -> pygame.Surface:
    frames = sprites.chef_frames(color)
    d = {(0, 1): "down", (0, -1): "up", (1, 0): "right", (-1, 0): "left"}[chef.facing]
    f = 1 + int(chef.walk * 8) % 2 if chef.moving else 0
    return frames[(d, f)]


class KitchenView:
    """Draws one World. Keeps the pre-rendered background."""

    def __init__(self, world: World) -> None:
        self.world = world
        self.bg = build_background(world)
        self.show_bars = not world.noise.is_noiseless
        self.dining_top = KITCHEN_Y + world.h * TILE

    def draw(self, surf, t: float, active: set[int], colors, hints: bool = True) -> None:
        w = self.world
        surf.blit(self.bg, (0, 0))
        self._dynamic_stations(surf, t)
        labels: list[tuple[Item, int, int]] = []
        for st in w.stations.values():
            if st.item is not None:
                cx, cy = station_item_pos(st)
                if st.kind == "h":
                    self._blender_jar(surf, st, cx, cy, t, back=True)
                draw_item(surf, st.item, cx, cy, t, self.show_bars)
                if st.kind == "h":
                    self._blender_jar(surf, st, cx, cy, t, back=False)
                labels.append((st.item, cx, cy))
        self._cosmic(surf, t)
        for chef in sorted(w.chefs, key=lambda c: c.y):
            color = colors[chef.idx]
            x, y = map_to_screen(chef.x, chef.y)
            pygame.draw.ellipse(surf, shade(P.FLOOR_B, 0.7), (x - 7, y + HALF_H - 3, 14, 5))
            spr = chef_sprite(chef, color, t)
            bob = 1 if chef.working and int(t * 10) % 2 else 0
            surf.blit(spr, (x - 8, y + HALF_H - 22 + bob))
            if chef.held is not None:
                hx, hy = held_item_pos(chef)
                draw_item(surf, chef.held, hx, hy + bob, t, self.show_bars)
                labels.append((chef.held, hx, hy + bob))
        for chef in w.chefs:
            if chef.idx in active and hints:
                self._target_hint(surf, chef, colors[chef.idx], t)
        for item, cx, cy in labels:
            draw_item_label(surf, item, cx, cy)
        for chef in w.chefs:
            if chef.idx in active:
                x, y = map_to_screen(chef.x, chef.y)
                col = colors[chef.idx]
                tip = y + HALF_H - 26 - (1 if int(t * 3) % 2 else 0)
                pygame.draw.polygon(surf, P.INK, [(x - 4, tip - 4), (x + 4, tip - 4), (x, tip + 1)])
                pygame.draw.polygon(surf, col, [(x - 3, tip - 3), (x + 3, tip - 3), (x, tip)])

    def _blender_jar(self, surf, st: Station, cx: int, cy: int, t: float, back: bool) -> None:
        jar = pygame.Rect(cx - 9, cy - 10, 18, 19)
        if back:
            pygame.draw.rect(surf, (200, 230, 240), jar)
        else:
            pygame.draw.rect(surf, P.INK, jar, 1)
            surf.fill((255, 255, 255), (jar.x + 2, jar.y + 2, 1, 6))
            pygame.draw.rect(surf, P.INK, (cx - 7, jar.y - 2, 14, 3))
            if st.progress > 0:
                k = int(t * 30)
                for i in range(3):
                    a = (k * 40 + i * 120) % 360
                    surf.fill(P.WHITE, (round(cx + 6 * math.cos(math.radians(a))), round(cy + 3 * math.sin(math.radians(a))), 2, 1))

    def _dynamic_stations(self, surf, t: float) -> None:
        w = self.world
        for st in w.stations.values():
            px, py = tile_px(st.x, st.y)
            if st.kind == "belt":
                shift = int(t * 24) % 8
                for i in range(-1, 4):
                    gx = px + ((i * 8 + shift * st.belt_dir) % 32) - 4
                    if px <= gx <= px + TILE - 4:
                        pts = [(gx, py + 7), (gx + 3, py + 12), (gx, py + 17)] if st.belt_dir > 0 else [
                            (gx + 3, py + 7), (gx, py + 12), (gx + 3, py + 17)]
                        pygame.draw.lines(surf, (110, 114, 130), False, pts, 2)
            if st.kind == "fridge" and w.supply is not None:
                lbl = text(str(w.supply), 8, P.BAD if w.supply == 0 else P.INK)
                surf.blit(lbl, (px + 13, py - 3))
            if st.jammed(w.t):
                k = int(t * 12)
                for i in range(5):
                    sx = px + (k * 7 + i * 11) % TILE
                    sy = py + (k * 5 + i * 13) % TILE
                    surf.fill((255, 255, 120) if i % 2 else (180, 220, 255), (sx, sy, 2, 2))
            if st.progress > 0:
                r = ring(min(24, int(st.progress * 24)))
                surf.blit(r, (px + TILE // 2 - r.get_width() // 2, py - 12))
            if t - st.last_used < 0.9 and st.kind in ("x", "h", "z", "control"):
                self._gate_flash(surf, st, t)

    def _gate_flash(self, surf, st: Station, t: float) -> None:
        age = self.world.t - st.last_used
        px, py = tile_px(st.x, st.y)
        cy = py - 6 - round(age * 10)
        cx = px + TILE // 2
        if st.kind == "control":
            t_st = st.partner
            if t_st is not None:
                cx = (px + tile_px(t_st.x, t_st.y)[0]) // 2 + TILE // 2
            pygame.draw.line(surf, P.WHITE, (cx - 12, cy - 4), (cx + 12, cy - 4))
            pygame.draw.line(surf, P.WHITE, (cx - 12, cy + 5), (cx + 12, cy + 5))
            pygame.draw.line(surf, P.INK, (cx, cy - 4), (cx, cy + 5))
            circuit.draw_control(surf, cx, cy - 4)
            circuit.draw_target(surf, cx, cy + 5)
            return
        pygame.draw.line(surf, P.WHITE, (cx - 12, cy), (cx + 12, cy))
        circuit.draw_gate_box(surf, SYMBOLS[st.kind], cx, cy)

    def _target_hint(self, surf, chef: Chef, color, t: float) -> None:
        w = self.world
        st = w.station_at(chef.target)
        if st is None:
            return
        px, py = tile_px(st.x, st.y)
        # corner brackets in the chef's colour
        for (x, y, dx, dy) in ((px, py, 1, 1), (px + TILE - 1, py, -1, 1), (px, py + TILE - 1, 1, -1),
                               (px + TILE - 1, py + TILE - 1, -1, -1)):
            surf.fill(color, (min(x, x + dx * 4), y, 5, 1))
            surf.fill(color, (x, min(y, y + dy * 4), 1, 5))
        # button prompt
        hint = None
        if chef.held is None:
            if st.kind == "fridge" or st.item is not None:
                hint = "A"
            if st.item is not None and st.kind in ("x", "h", "z", "sink", "control", "target"):
                ready = st.kind not in ("control", "target") or (
                    st.partner is not None and st.item is not None and st.partner.item is not None)
                if ready:
                    hint = "B"
        elif st.kind in ("pass", "bin") or st.accepts(chef.held):
            hint = "A"
        if hint and int(t * 2.5) % 3 != 2:
            draw_button_hint(surf, hint, px + TILE - 3, py + 3, (120, 230, 120) if hint == "A" else (250, 120, 110))

    def _cosmic(self, surf, t: float) -> None:
        c = self.world.cosmic
        if c is None:
            return
        if c.center is not None:
            on = int(t * 8) % 2 == 0
            for (tx, ty) in c.area():
                px, py = tile_px(tx, ty)
                overlay = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
                overlay.fill((255, 60, 60, 110 if on else 50))
                surf.blit(overlay, (px, py))
            cx, cy = tile_px(*c.center)
            if on:
                surf.blit(sprites.bubble_bang(), (cx + 8, cy - 14))
        age = self.world.t - c.last_hit
        if age < 0.5 and c.last_center is not None:
            cx, cy = tile_px(*c.last_center)
            flash = pygame.Surface((TILE * 3, TILE * 3), pygame.SRCALPHA)
            flash.fill((255, 255, 255, round(220 * (1 - age / 0.5))))
            surf.blit(flash, (cx - TILE, cy - TILE))
            for i in range(10):
                a = i * 36 + age * 400
                rr = 6 + age * 90
                surf.fill((180, 230, 255), (round(cx + 12 + math.cos(math.radians(a)) * rr),
                                            round(cy + 12 + math.sin(math.radians(a)) * rr), 2, 2))
