"""DECOHERENCE, the monster behind SYNDROME!: a blob of static noise with a
ragged edge, two big eyes and a jagged mouth. It is the noise that throws
every error, so it gets the boss's whole face: it winds up and spits, it
flinches when a fix lands, grins at a wrong press, laughs at a logical
error, and dissolves into pixels when the qubit survives.

All of it is drawn here, from game time alone (never the wall clock or the
global random), so both players' screens and every replay look the same.
The body is pre-rendered: a few noise textures, each cut to a few shapes
(rest, swelling, squashed), and the static "flickers" by blitting the next
texture every few frames. The face is a handful of primitives on top. The
art is built on the first call; render.Renderer warms it at start-up, so the
Pi never pays for it mid-game.
"""

from __future__ import annotations

import math
import random

import pygame

from planck_time import palette as P
from planck_time.pixel import blit_center, outlined

RX, RY = 40, 21  # the body's half-width and half-height at rest
VARIANTS = 3  # noise textures, cycled for the static's flicker...
FLICKER = 10  # ...this many times a second
SPIKE = 0.12  # the ragged edge's tufts, as a share of the radius
SHAPES = {  # (x, y) scale of the body
    "rest": (1.0, 1.0),
    "swell1": (1.04, 1.05), "swell2": (1.08, 1.10), "swell3": (1.12, 1.15),  # winding up
    "squash": (1.16, 0.80),  # flinching
    "wide": (1.08, 0.90),  # laughing
}
SWELLS = ("rest", "swell1", "swell2", "swell3")
KEY = (255, 0, 255)  # transparent in the sprites
HOLE = (1, 2, 3)  # the stencil's see-through colour
SIZE = (2 * round(RX * 1.16 * (1 + SPIKE)) + 10, 2 * round(RY * 1.15 * (1 + SPIKE)) + 10)
TILE = 4  # the dissolve breaks the body into squares this big

_ART: dict | None = None


# --- building the art (once) ----------------------------------------------------------


def _noise(seed: int) -> pygame.Surface:
    """Dithered violet with pink static sprinkled through it: lighter on top,
    darker underneath, a few bright scan streaks."""
    rng = random.Random(seed)
    w, h = SIZE
    top = (bytes(P.lighten(P.VIOLET, 0.25)), bytes(P.VIOLET))
    mid = (bytes(P.VIOLET), bytes(P.shade(P.VIOLET, 0.8)))
    low = (bytes(P.shade(P.VIOLET, 0.7)), bytes(P.shade(P.VIOLET, 0.55)))
    static = tuple(bytes(c) for c in (P.PINK, P.PINK, P.lighten(P.PINK, 0.4), P.NIGHT, P.shade(P.VIOLET, 0.45)))
    rows = []
    for y in range(h):
        v = (y - h / 2) / (RY * 1.15)
        pair = top if v < -0.5 else low if v > 0.3 else mid
        row = [static[rng.randrange(len(static))] if rng.random() < 0.16 else pair[(x + y) & 1] for x in range(w)]
        if rng.random() < 0.12:  # a scan streak
            x0, n = rng.randrange(w - 8), rng.randint(3, 7)
            row[x0:x0 + n] = [bytes(P.lighten(P.PINK, 0.5))] * n
        rows.append(b"".join(row))
    return pygame.image.frombytes(b"".join(rows), SIZE, "RGB")


def _edge(variant: int, sx: float, sy: float, grow: int = 0) -> list[tuple[float, float]]:
    """The ragged outline: an ellipse, flatter underneath, with tufts that move
    from texture to texture so the edge crackles too."""
    rng = random.Random(100 + variant)
    cx, cy = SIZE[0] / 2, SIZE[1] / 2
    n = 42
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        jag = rng.uniform(-0.03, 0.03)
        if (i + variant) % 3 == 0:
            jag += SPIKE * rng.uniform(0.4, 1.0)
        y = math.sin(a) * (RY * sy * (1 + jag) + grow)
        if y > 0:
            y *= 0.9
        pts.append((cx + math.cos(a) * (RX * sx * (1 + jag) + grow), cy + y))
    return pts


def _sprite(noise: pygame.Surface, variant: int, sx: float, sy: float) -> pygame.Surface:
    surf = pygame.Surface(SIZE)
    surf.fill(KEY)
    pygame.draw.polygon(surf, P.INK, _edge(variant, sx, sy, grow=2))
    stencil = pygame.Surface(SIZE)
    stencil.fill(KEY)
    pygame.draw.polygon(stencil, HOLE, _edge(variant, sx, sy))
    stencil.set_colorkey(HOLE)
    fill = noise.copy()
    fill.blit(stencil, (0, 0))
    fill.set_colorkey(KEY)
    surf.blit(fill, (0, 0))
    surf.set_colorkey(KEY, pygame.RLEACCEL)
    return surf


def _tiles(sprite: pygame.Surface) -> list:
    """The body cut into TILE squares, each with how it flies off: the edge
    goes first, the middle last, everything drifting up and out."""
    rng = random.Random(7)
    w, h = SIZE
    cx, cy = w / 2, h / 2
    plain = sprite.copy()
    plain.set_colorkey(None)
    tiles = []
    for ty in range(0, h - TILE + 1, TILE):
        for tx in range(0, w - TILE + 1, TILE):
            colors = [tuple(plain.get_at((tx + i, ty + j)))[:3] for j in range(TILE) for i in range(TILE)]
            solid = [c for c in colors if c != KEY]
            if len(solid) < TILE * TILE // 2:
                continue
            tile = pygame.Surface((TILE, TILE))
            tile.blit(plain, (0, 0), (tx, ty, TILE, TILE))
            tile.set_colorkey(KEY)
            dx, dy = tx + TILE / 2 - cx, ty + TILE / 2 - cy
            reach = math.hypot(dx / RX, dy / RY)
            a = math.atan2(dy, dx) + rng.uniform(-0.6, 0.6)
            speed = rng.uniform(15, 60)
            tiles.append((tile, tx - cx, ty - cy, math.cos(a) * speed, math.sin(a) * speed - rng.uniform(15, 45),
                          0.28 * max(0.0, 1.0 - reach) + rng.uniform(0.0, 0.08), rng.uniform(0.35, 0.75),
                          rng.choice(solid)))
    return tiles


def _art() -> dict:
    global _ART
    if _ART is None:
        noises = [_noise(11 + v) for v in range(VARIANTS)]
        bodies = {(v, name): _sprite(noises[v], v, *scale)
                  for v in range(VARIANTS) for name, scale in SHAPES.items()}
        flash = pygame.Surface(SIZE)
        flash.fill(KEY)
        pygame.draw.polygon(flash, P.WHITE, _edge(0, 1.0, 1.0, grow=2))
        flash.set_colorkey(KEY, pygame.RLEACCEL)
        shocked = bodies[(0, "rest")].copy()
        c = (SIZE[0] // 2, SIZE[1] // 2)
        _eyes(shocked, c, 1.0, 1.0, "x", None)
        _open_mouth(shocked, c[0], c[1] + 9, 14, 8)
        _ART = {"bodies": bodies, "flash": flash, "tiles": _tiles(shocked)}
    return _ART


def prepare() -> None:
    """Build the art now (it's a few tens of ms on the Pi), not on first use."""
    _art()


# --- the face ---------------------------------------------------------------------------


def _eyes(surf, center, sx: float, sy: float, kind: str, look_at, t: float = 0.0) -> None:
    """kind: open, red (glowing, angry), squint (smug), x (hurt), shut (^ ^, laughing).
    The pupils look towards look_at (a point on surf), or ahead if it's None."""
    cx, cy = center
    for side in (-1, 1):
        ex, ey = round(cx + side * 15 * sx), round(cy - 5 * sy)
        if kind == "x":
            for color, width in ((P.INK, 4), (P.WHITE, 2)):
                pygame.draw.line(surf, color, (ex - 5, ey - 5), (ex + 5, ey + 5), width)
                pygame.draw.line(surf, color, (ex - 5, ey + 5), (ex + 5, ey - 5), width)
            continue
        if kind == "shut":
            pts = ((ex - 6, ey + 3), (ex, ey - 3), (ex + 6, ey + 3))
            pygame.draw.lines(surf, P.INK, False, pts, 4)
            pygame.draw.lines(surf, P.WHITE, False, pts, 2)
            continue
        red = kind == "red"
        squint = kind == "squint"
        eye = pygame.Rect(0, 0, 14, 8 if squint else 15)
        eye.center = (ex, ey + (3 if squint else 0))
        if red:
            glow = P.lighten(P.BAD, 0.5) if int(t * 12) % 2 else P.BAD
            pygame.draw.ellipse(surf, glow, eye.inflate(8, 8), 1)
        pygame.draw.ellipse(surf, P.INK, eye.inflate(4, 4))
        pygame.draw.ellipse(surf, P.BAD if red else P.WHITE, eye)
        if look_at is None:
            lx, ly = 0.0, 0.2
        else:
            lx = max(-1.0, min(1.0, (look_at[0] - ex) / 50))
            ly = max(-1.0, min(1.0, (look_at[1] - ey) / 50))
        pw, ph = (3, 5) if red else (5, 4) if squint else (5, 6)
        px = eye.centerx + round(lx * (eye.w // 2 - pw // 2 - 2))
        py = eye.centery + round(ly * max(0, eye.h // 2 - ph // 2 - 2))
        surf.fill(P.INK, (px - pw // 2, py - ph // 2, pw, ph))
        if red:
            surf.fill(P.lighten(P.GOLD, 0.4), (px, py - 1, 1, 2))  # a hot core
        else:
            surf.fill(P.WHITE, (px - pw // 2, py - ph // 2, 1, 1))
        if red or squint:  # brows, low on the inside
            pygame.draw.line(surf, P.INK, (ex + side * 8, eye.top - 5), (ex - side * 7, eye.top - 1), 3)


def _closed_mouth(surf, mx: int, my: int) -> None:
    """A jagged seam: the teeth clenched."""
    pts = [(mx + x, my + (2 if (x // 4) % 2 else -1)) for x in range(-14, 15, 4)]
    pygame.draw.lines(surf, P.INK, False, pts, 3)
    for x, y in pts[1:-1:2]:
        surf.fill(P.WHITE, (x - 1, y - 2, 2, 1))


def _open_mouth(surf, mx: int, my: int, w: int, h: int, glow: float = 0.0) -> None:
    """An open maw with a row of teeth top and bottom; `glow` lights a charge
    at the back of it."""
    rect = pygame.Rect(mx - w, my - h // 2, 2 * w, h)
    pygame.draw.ellipse(surf, P.INK, rect.inflate(4, 4))
    pygame.draw.ellipse(surf, P.shade(P.BAD, 0.45), rect)
    if glow > 0:
        r = round(1 + 4 * glow)
        pygame.draw.circle(surf, P.PINK, (mx, my + 1), r + 1)
        pygame.draw.circle(surf, P.WHITE, (mx, my + 1), max(1, r - 1))
    if h < 5:
        return
    tooth = 2 + h // 6
    for x in range(mx - w + 4, mx + w - 3, 5):
        u = (x - mx) / w
        edge = (h / 2) * math.sqrt(max(0.0, 1 - u * u))
        top, bottom = round(my - edge), round(my + edge)
        pygame.draw.polygon(surf, P.WHITE, ((x - 2, top), (x + 2, top), (x, top + tooth)))
        if x + 2 < mx + w - 4:
            pygame.draw.polygon(surf, P.WHITE, ((x, bottom), (x + 4, bottom), (x + 2, bottom - tooth + 1)))


def _grin(surf, mx: int, my: int) -> None:
    """A wide crescent of teeth, corners up."""
    xs = range(-20, 21, 4)
    top = [(mx + x, my - 1 - round(7 * (x / 20) ** 2)) for x in xs]
    bottom = [(mx + x, my + 6 - round(10 * (x / 20) ** 2)) for x in reversed(xs)]
    pygame.draw.polygon(surf, P.INK, top + bottom)
    pygame.draw.polygon(surf, P.INK, top + bottom, 2)
    for x, y in top[1:-1]:
        pygame.draw.polygon(surf, P.WHITE, ((x - 2, y + 1), (x + 2, y + 1), (x, y + 4)))


# --- the whole monster ---------------------------------------------------------------------


def draw(surf: pygame.Surface, center, t: float, mood: str = "idle", k: float = 0.0, look_at=None) -> None:
    """The monster at `center`, in a mood:

      idle     resting, bobbing gently, pupils on look_at
      windup   k 0..1 towards spitting: it swells, its eyes glow red, its mouth opens
      spit     k 0..1 through the bolt: mouth wide, eyes red
      flinch   k 0..1 after a fix: squashed, X-eyes, "OW!"
      grin     k 0..1 after a wrong press
      laugh    k = seconds since the logical error: bouncing, mouth wide, "HA!"
      angry    the portrait's: red eyes and a snarl
    """
    art = _art()
    cx, cy = center
    variant = int(t * FLICKER) % VARIANTS
    shape, dx, dy = "rest", 0, round(1.5 * math.sin(t * 3))
    eyes, mouth, opening, glow = "open", "closed", 0.0, 0.0
    if mood == "windup":
        shape = SWELLS[min(3, int(k * 4))]
        if k > 0.6:
            dx = 1 if int(t * 30) % 2 else -1  # trembling
        if k > 0.3:
            eyes = "red"
        if k > 0.15:
            mouth, opening, glow = "open", k, max(0.0, k - 0.5) * 2
    elif mood == "spit":
        dy -= round(2 * (1 - k))
        eyes, mouth, opening = "red", "open", 1.0
    elif mood == "flinch":
        shape = "squash" if k < 0.5 else "rest"
        dy = -round(4 * (1 - k))
        eyes, mouth, opening = "x", "open", 0.35
    elif mood == "grin":
        dy -= round(abs(math.sin(t * 16)))
        eyes, mouth = "squint", "grin"
    elif mood == "laugh":
        shape = "wide" if int(k * 8) % 2 else "rest"
        dy = -round(4 * abs(math.sin(k * 12)))
        eyes, mouth, opening = "shut", "laugh", 1.0
    elif mood == "angry":
        if int(t * 20) % 3 == 0:
            dx = 1
        eyes, mouth, opening = "red", "open", 0.55 + 0.3 * math.sin(t * 5)
    sx, sy = SHAPES[shape]
    body = art["bodies"][(variant, shape)]
    x, y = cx + dx, cy + dy
    surf.blit(body, (x - SIZE[0] // 2, y - SIZE[1] // 2))
    _eyes(surf, (x, y), sx, sy, eyes, look_at, t)
    mx, my = x, round(y + 9 * sy)
    if mouth == "closed":
        _closed_mouth(surf, mx, my)
    elif mouth == "grin":
        _grin(surf, mx, my)
    elif mouth == "laugh":
        _open_mouth(surf, mx, my + 1, 19, 13)
    else:
        _open_mouth(surf, mx, my, round(11 + 5 * opening), round(2 + 10 * opening), glow)
    if mood == "flinch":
        blit_center(surf, outlined("OW!", 8, P.WHITE), (cx + 58, cy - 6 - round(10 * k)))
    elif mood == "laugh":
        side = -1 if int(k * 4) % 2 else 1
        blit_center(surf, outlined("HA!", 8, P.GOLD), (cx + side * 60, cy + 2 - round(3 * abs(math.sin(k * 12)))))


def mouth(center) -> tuple[int, int]:
    """Where the bolt leaves from (resting pose: the attack never depends on the pose)."""
    return center[0], center[1] + 10


def charge(surf: pygame.Surface, center, k: float, t: float) -> None:
    """The wind-up's particles, streaming in to the mouth from all round."""
    mx, my = mouth(center)
    n = 14
    for i in range(n):
        f = (k * 1.6 + i / n) % 1.0  # each one's way in, 0 = far
        r = 52 * (1 - f) + 3
        a = 2 * math.pi * i / n + t * 1.5
        color = (P.PINK, P.WHITE, P.SKY)[i % 3]
        size = 2 if f < 0.7 else 1
        surf.fill(color, (round(mx + math.cos(a) * r * 1.2), round(my + math.sin(a) * r * 0.7), size, size))


def bolt(surf: pygame.Surface, start, end, t: float) -> None:
    """A crackling lightning bolt from start to end, rejagged every other frame."""
    rng = random.Random(int(t * 30) * 7 + 1)
    (x0, y0), (x1, y1) = start, end
    n = 6
    pts = [(x0, y0)]
    for i in range(1, n):
        f = i / n
        pts.append((x0 + (x1 - x0) * f + rng.randint(-6, 6), y0 + (y1 - y0) * f))
    pts.append((x1, y1))
    for color, width in ((P.INK, 5), (P.PINK, 3), (P.WHITE, 1)):
        pygame.draw.lines(surf, color, False, pts, width)


def splash(surf: pygame.Surface, rect: pygame.Rect, since: float, t: float) -> None:
    """The bolt bursting across the whole chip: a crackle racing from the top
    middle both ways round the edge. It is the same wherever the error landed."""
    rng = random.Random(int(t * 30) * 13 + 5)
    reach = min(1.0, since / 0.1)  # how far round the edge it has run
    cx = rect.centerx
    half = rect.w // 2
    top = []
    for x in range(rect.x, rect.right + 1, 8):
        if abs(x - cx) <= reach * half + 4:
            top.append((x, rect.y + rng.randint(-2, 2)))
    if len(top) > 1:
        for color, width in ((P.PINK, 3), (P.WHITE, 1)):
            pygame.draw.lines(surf, color, False, top, width)
    if reach >= 1.0:
        for side in (rect.x, rect.right):
            pts = [(side + rng.randint(-2, 2), y) for y in range(rect.y, rect.bottom + 1, 8)]
            for color, width in ((P.PINK, 3), (P.WHITE, 1)):
                pygame.draw.lines(surf, color, False, pts, width)
        bottom = [(x, rect.bottom + rng.randint(-2, 2)) for x in range(rect.x, rect.right + 1, 8)]
        for color, width in ((P.PINK, 3), (P.WHITE, 1)):
            pygame.draw.lines(surf, color, False, bottom, width)
    for i in range(10):  # sparks off the point of impact
        a = math.pi * (i + 0.5) / 10
        r = 6 + 60 * since
        surf.fill(P.WHITE if i % 2 else P.PINK,
                  (round(cx + math.cos(a) * r * 1.6), round(rect.y - math.sin(a) * r * 0.4), 2, 2))


def dissolve(surf: pygame.Surface, center, since: float) -> None:
    """The finale: a white flash, then the body breaks into squares that drift
    off and crumble into single pixels."""
    art = _art()
    cx, cy = center
    if since < 0.07:
        surf.blit(art["flash"], (cx - SIZE[0] // 2, cy - SIZE[1] // 2))
        return
    for tile, ox, oy, vx, vy, delay, life, color in art["tiles"]:
        s = since - delay
        if s < 0:
            surf.blit(tile, (cx + ox, cy + oy))
            continue
        if s >= life:
            continue
        x, y = cx + ox + vx * s, cy + oy + vy * s + 30 * s * s
        if s < life * 0.4:
            surf.blit(tile, (round(x), round(y)))
        else:
            surf.fill(color, (round(x), round(y), 2 if s < life * 0.7 else 1, 2 if s < life * 0.7 else 1))


def portrait(surf: pygame.Surface, center, t: float) -> None:
    """The monster for the BOSS! card and the intro: the in-game art, snarling."""
    draw(surf, center, t, "angry")
