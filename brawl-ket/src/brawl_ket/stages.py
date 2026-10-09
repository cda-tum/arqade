"""The backdrops a round is fought in. Visual only: the floor line, the stage's width and
everything the fight reads are the same in each.

Each stage is drawn once, MARGIN px bigger than the screen on every side (for the shake),
and comes with a list of small lights (rect, colour) that blink on top of it. A match
picks one at random (match.py, STAGES), so it isn't always the same room:

- lab: the quantum lab with its racks of qubit chips (the original);
- cryo: a cryostat room, a superconducting quantum computer's gold "chandelier" (the
  dilution refrigerator's plates, rods and coax lines) hanging in the middle;
- optics: a white laser lab, beams crossing an optical table;
- office: the open-plan TUM Quantum Space, its name and the MQT logo on the glass wall.

Every stage keeps the fighters readable: no green or purple (the basis colours) in a
large area, darker or calmer than the fighters, and a solid floor band at FLOOR_Y.
"""

from __future__ import annotations

import math

import pygame

from . import palette as P
from .config import FLOOR_Y, INTERNAL_HEIGHT, INTERNAL_WIDTH, STAGES
from .fonts import load_font, load_image

W, H = INTERNAL_WIDTH, INTERNAL_HEIGHT
MARGIN = 8                  # the stage is this much bigger on every side, for the shake

Lights = list[tuple[pygame.Rect, tuple]]


def make_stage(name: str = "lab") -> tuple[pygame.Surface, Lights]:
    """The named stage, MARGIN px bigger than the screen on every side, and its lights
    (in screen coordinates, without the margin)."""
    surf = pygame.Surface((W + 2 * MARGIN, H + 2 * MARGIN))
    lights: Lights = []
    dict(zip(STAGES, (_lab, _cryo, _optics, _office)))[name](surf, lights)
    return surf, [(r.move(-MARGIN, -MARGIN), c) for r, c in lights]


def _box(surf, rect, color, radius: int = 3, ink: int = 2) -> None:
    rect = pygame.Rect(rect)
    pygame.draw.rect(surf, P.INK, rect.inflate(2 * ink, 2 * ink), border_radius=radius + ink)
    pygame.draw.rect(surf, color, rect, border_radius=radius)


def _text(surf, text: str, size: int, color, center, outline=P.INK) -> None:
    f = load_font(size)
    ink = f.render(text, False, outline)
    core = f.render(text, False, color)
    r = core.get_rect(center=center)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 2)):
        surf.blit(ink, r.move(dx, dy))
    surf.blit(core, r)


# --- the lab (the original) -------------------------------------------------------------------

WALL = (40, 32, 80)
WALL_TILE = (48, 40, 96)
RACK = (56, 48, 112)
RACK_SLOT = (88, 80, 152)
FLOOR_TOP = (72, 64, 128)
FLOOR_TILE = (56, 48, 104)
FLOOR_SHINE = (96, 88, 160)


def _tiled_floor(surf, top, tile, shine) -> None:
    m = MARGIN
    floor = FLOOR_Y + m
    surf.fill(P.INK, (0, floor - 4, W + 2 * m, H + 2 * m - floor + 4))
    for x in range(-16, W + 2 * m, 32):
        pygame.draw.rect(surf, top, (x + 1, floor - 2, 30, 14))
        surf.fill(shine, (x + 3, floor, 26, 2))
        pygame.draw.rect(surf, tile, (x + 1, floor + 14, 30, H + 2 * m - floor - 14))
        surf.fill(P.shade(tile, 0.8), (x + 13, floor + 22, 6, 6))


def _lab(surf, lights: Lights) -> None:
    m = MARGIN
    surf.fill(WALL)
    floor = FLOOR_Y + m
    for y in range(0, floor, 16):              # the tiled wall
        for x in range(-(y // 16 % 2) * 16, W + 2 * m, 32):
            surf.fill(WALL_TILE, (x, y, 30, 14))
    for i, x in enumerate(range(40 + m, W + m, 120)):     # racks of qubit chips
        rack = pygame.Rect(x, 82 + m, 60, 172)
        pygame.draw.rect(surf, P.INK, rack.inflate(4, 4), border_radius=5)
        pygame.draw.rect(surf, RACK, rack, border_radius=4)
        surf.fill(P.lighten(RACK, 0.15), (rack.x + 4, rack.y + 2, rack.w - 8, 2))
        for k in range(5):
            slot = pygame.Rect(rack.x + 8, rack.y + 14 + k * 30, 44, 8)
            surf.fill(P.INK, slot.inflate(2, 2))
            surf.fill(P.GOLD if (i + k) % 3 == 0 else RACK_SLOT, slot)
            for q in range(3):                  # status lights under each chip
                spot = pygame.Rect(slot.x + 4 + q * 7, slot.bottom + 5, 4, 3)
                surf.fill(P.INK, spot.inflate(2, 2))
                lights.append((spot, (P.GOOD, P.SKY, P.GOLD)[(i + k + q) % 3]))
        # a cable down to the floor
        pygame.draw.line(surf, P.INK, (rack.centerx, rack.bottom), (rack.centerx, floor), 3)
    pygame.draw.line(surf, P.shade(WALL, 0.8), (0, floor - 18), (W + 2 * m, floor - 18), 2)
    _tiled_floor(surf, FLOOR_TOP, FLOOR_TILE, FLOOR_SHINE)


# --- the cryo chamber -----------------------------------------------------------------------------

CRYO_WALL = (24, 32, 56)
CRYO_PANEL = (32, 40, 72)
STEEL = (120, 136, 160)
COPPER = (216, 144, 72)
GOLD_PLATE = (232, 184, 72)
COAX = (176, 192, 216)


def _can(surf, x: int, top: int, bottom: int, w: int) -> None:
    """A closed cryostat can: a steel cylinder with flanges and a shine."""
    body = pygame.Rect(x - w // 2, top, w, bottom - top)
    _box(surf, body, STEEL, radius=10)
    surf.fill(P.lighten(STEEL, 0.4), (body.x + 6, body.y + 10, 4, body.h - 20))
    surf.fill(P.shade(STEEL, 0.7), (body.right - 10, body.y + 10, 4, body.h - 20))
    for y in (top + 18, top + 70, bottom - 30):
        _box(surf, (body.x - 4, y, w + 8, 7), P.shade(STEEL, 0.85), radius=2)


def _cryo(surf, lights: Lights) -> None:
    m = MARGIN
    floor = FLOOR_Y + m
    surf.fill(CRYO_WALL)
    for x in range(0, W + 2 * m, 64):          # wall panels
        _box(surf, (x + 4, 30, 56, floor - 54), CRYO_PANEL, radius=2, ink=1)
    # the ceiling beam the fridge hangs from
    _box(surf, (-4, 24, W + 2 * m + 8, 14), P.shade(STEEL, 0.6), radius=0)
    for x in range(12, W + 2 * m, 40):
        pygame.draw.circle(surf, P.lighten(STEEL, 0.2), (x, 31), 2)
    # pipes along the wall, and the two closed cryostats either side
    for y, c in ((60, P.shade(STEEL, 0.75)), (70, P.shade(COPPER, 0.8))):
        pygame.draw.line(surf, P.INK, (0, y), (W + 2 * m, y), 7)
        pygame.draw.line(surf, c, (0, y), (W + 2 * m, y), 4)
    for x in (74, W + 2 * m - 74):
        _can(surf, x, 96, floor - 4, 64)
        pygame.draw.line(surf, P.INK, (x, 38), (x, 96), 9)
        pygame.draw.line(surf, P.shade(STEEL, 0.8), (x, 38), (x, 96), 5)
        for k in range(6):                     # frost on the can
            surf.fill(P.lighten(COAX, 0.5), (x - 22 + (k * 13) % 44, 140 + (k * 37) % 120, 3, 2))
    # the gas handling panel: gauges with blinking lights, and the mixing chamber's readout
    panel = pygame.Rect(148, 112, 72, 92)
    _box(surf, panel, P.shade(STEEL, 0.55), radius=3)
    for i, (gx, gy) in enumerate(((166, 134), (202, 134))):
        pygame.draw.circle(surf, P.INK, (gx, gy), 11)
        pygame.draw.circle(surf, P.lighten(STEEL, 0.6), (gx, gy), 9)
        ang = 0.8 + i * 1.3
        pygame.draw.line(surf, P.BAD, (gx, gy), (gx + round(7 * math.cos(ang)), gy - round(7 * math.sin(ang))), 2)
    for i in range(4):
        spot = pygame.Rect(158 + i * 14, 158, 6, 4)
        surf.fill(P.INK, spot.inflate(2, 2))
        lights.append((spot, (P.SKY, P.GOLD, P.SKY, P.BAD)[i]))
    readout = pygame.Rect(156, 172, 56, 22)
    _box(surf, readout, P.INK, radius=2, ink=1)
    _text(surf, "10mK", 8, P.SKY, readout.center)
    # the chandelier: gold plates getting smaller downwards, joined by rods, coax lines
    # winding down between them, and the chip at the bottom
    cx = (W + 2 * m) // 2
    plates = ((66, 208), (106, 176), (142, 144), (174, 114), (202, 86))
    for (y0, w0), (y1, w1) in zip(plates, plates[1:]):
        for side in (-1, 1):
            for x0, x1 in ((cx + side * (w0 // 2 - 10), cx + side * (w1 // 2 - 8)),):
                pygame.draw.line(surf, P.INK, (x0, y0), (x1, y1), 5)
                pygame.draw.line(surf, P.shade(GOLD_PLATE, 0.85), (x0, y0), (x1, y1), 3)
        for k in range(-3, 4):                 # the coax lines, kinked at each stage
            a = (cx + k * (w0 // 8), y0 + 4)
            b = (cx + k * (w1 // 8) + (4 if k % 2 else -4), (y0 + y1) // 2)
            c = (cx + k * (w1 // 8), y1)
            pygame.draw.lines(surf, P.INK, False, [a, b, c], 3)
            pygame.draw.lines(surf, COAX if k % 2 else P.shade(COAX, 0.75), False, [a, b, c], 1)
    for x in (cx - 60, cx, cx + 60):           # hung from the ceiling beam
        pygame.draw.line(surf, P.INK, (x, 38), (x, 66), 7)
        pygame.draw.line(surf, P.shade(STEEL, 0.9), (x, 38), (x, 66), 3)
    for y, w in plates:
        plate = pygame.Rect(cx - w // 2, y, w, 9)
        _box(surf, plate, GOLD_PLATE, radius=3)
        surf.fill(P.lighten(GOLD_PLATE, 0.5), (plate.x + 4, plate.y + 1, plate.w - 8, 2))
        surf.fill(P.shade(GOLD_PLATE, 0.7), (plate.x + 2, plate.bottom - 2, plate.w - 4, 1))
    # the mixing chamber and the chip mount under it
    _box(surf, (cx - 16, 214, 32, 20), P.shade(GOLD_PLATE, 0.9), radius=3)
    _box(surf, (cx - 10, 238, 20, 12), P.shade(COPPER, 0.9), radius=2)
    surf.fill(P.INK, (cx - 6, 241, 12, 6))
    lights.append((pygame.Rect(cx - 2, 242, 4, 3), P.SKY))
    # the floor: steel grating
    surf.fill(P.INK, (0, floor - 4, W + 2 * m, H + 2 * m - floor + 4))
    for x in range(-8, W + 2 * m, 24):
        pygame.draw.rect(surf, P.shade(STEEL, 0.55), (x + 1, floor - 2, 22, 12))
        surf.fill(P.shade(STEEL, 0.8), (x + 3, floor, 18, 2))
        pygame.draw.rect(surf, P.shade(STEEL, 0.4), (x + 1, floor + 12, 22, H + 2 * m - floor - 12))
        for y in range(floor + 16, H + 2 * m, 8):
            surf.fill(P.shade(STEEL, 0.3), (x + 4, y, 16, 2))


# --- the laser lab ------------------------------------------------------------------------------

ROOM = (176, 184, 200)          # a white room, dimmed a little so the fighters still pop
ROOM_PANEL = (192, 200, 216)
TABLE = (56, 64, 80)
BEAMS = ((232, 64, 72), (240, 136, 40), (248, 200, 48))     # red, orange, yellow: never the basis colours


def _beam(surf, pts, color) -> None:
    """A laser beam: a soft glow round a bright core."""
    pts = [(round(x), round(y)) for x, y in pts]
    pygame.draw.lines(surf, P.lighten(color, 0.55), False, pts, 7)
    pygame.draw.lines(surf, color, False, pts, 3)
    pygame.draw.lines(surf, P.lighten(color, 0.75), False, pts, 1)


def _mirror(surf, x: int, y: int, tilt: int) -> None:
    """A mirror on a post: a short silver bar, tilted ±45 degrees."""
    pygame.draw.line(surf, P.INK, (x, y), (x, y + 14), 4)
    pygame.draw.line(surf, P.MIST, (x, y + 2), (x, y + 14), 2)
    pygame.draw.line(surf, P.INK, (x - 5, y - 5 * tilt), (x + 5, y + 5 * tilt), 5)
    pygame.draw.line(surf, P.WHITE, (x - 4, y - 4 * tilt), (x + 4, y + 4 * tilt), 2)


def _optics(surf, lights: Lights) -> None:
    m = MARGIN
    floor = FLOOR_Y + m
    surf.fill(ROOM)
    for x in range(0, W + 2 * m, 80):          # clean-room wall panels and ceiling lights
        _box(surf, (x + 4, 36, 72, 170), ROOM_PANEL, radius=2, ink=1)
        _box(surf, (x + 16, 8, 48, 8), P.WHITE, radius=2, ink=1)
    # a laser warning sign
    sign = [(300 + m, 52), (326 + m, 96), (274 + m, 96)]
    pygame.draw.polygon(surf, P.INK, [(sign[0][0], sign[0][1] - 4), (sign[1][0] + 5, sign[1][1] + 3),
                                      (sign[2][0] - 5, sign[2][1] + 3)])
    pygame.draw.polygon(surf, P.GOLD, sign)
    _text(surf, "!", 16, P.INK, (300 + m, 82), outline=P.GOLD)
    _text(surf, "LASER", 8, P.INK, (300 + m, 110), outline=ROOM)
    # beams high across the room, between periscope mirrors on the wall
    _beam(surf, [(40, 140), (230, 140), (230, 60), (420, 60), (420, 140), (W + 2 * m - 40, 140)], BEAMS[0])
    _beam(surf, [(70, 176), (370, 176), (370, 96), (W + 2 * m - 80, 96)], BEAMS[1])
    _beam(surf, [(20, 72), (150, 72), (150, 188), (270, 188), (270, 116), (W + 2 * m - 20, 116)], BEAMS[2])
    _beam(surf, [(W + 2 * m - 20, 160), (500, 160), (500, 76), (W + 2 * m - 20, 76)], BEAMS[0])
    for x, y, t in ((230, 140, 1), (230, 60, -1), (420, 60, 1), (420, 140, -1), (370, 176, -1), (370, 96, 1),
                    (150, 72, 1), (150, 188, -1), (270, 188, 1), (270, 116, -1), (500, 160, 1), (500, 76, -1)):
        _mirror(surf, x, y - 7, t)
    # the optical table: a dark top full of holes, on legs, lasers and optics on it
    top = pygame.Rect(-4, 226, W + 2 * m + 8, 14)
    _box(surf, top, TABLE, radius=0)
    for x in range(6, W + 2 * m, 10):
        surf.fill(P.shade(TABLE, 0.6), (x, 231, 2, 2))
    for x in range(30, W + 2 * m, 150):
        _box(surf, (x, 242, 16, floor - 248), P.shade(TABLE, 0.8), radius=1)
        _box(surf, (x - 4, floor - 12, 24, 8), P.shade(TABLE, 0.7), radius=1)
    # lasers (boxes with a coloured aperture) and the beams bouncing along the table
    for x, color in ((24, BEAMS[0]), (W + 2 * m - 70, BEAMS[2])):
        _box(surf, (x, 204, 46, 20), P.INK, radius=2, ink=1)
        surf.fill(P.shade(color, 0.8), (x + 4, 208, 30, 3))
        lights.append((pygame.Rect(x + 36, 210, 4, 4), color))
    _beam(surf, [(70, 214), (180, 214), (180, 196), (300, 196), (300, 214), (360, 214)], BEAMS[0])
    _beam(surf, [(W + 2 * m - 70, 214), (520, 214), (520, 200), (420, 200), (420, 214), (380, 214)], BEAMS[2])
    for x, y, t in ((180, 214, 1), (180, 196, -1), (300, 196, 1), (300, 214, -1),
                    (520, 214, -1), (520, 200, 1), (420, 200, -1), (420, 214, 1)):
        _mirror(surf, x, y - 7, t)
    # a beam splitter cube where the two meet, and a detector
    _box(surf, (362, 206, 14, 14), P.lighten(P.SKY, 0.5), radius=1)
    _box(surf, (384, 204, 12, 18), P.SLATE, radius=1)
    lights.append((pygame.Rect(388, 210, 4, 4), P.GOLD))
    # the floor: pale tiles
    _tiled_floor(surf, (152, 160, 184), (128, 136, 160), (200, 208, 224))


# --- the office: TUM Quantum Space --------------------------------------------------------------
# After a photo of the real wall: a white wall over a glass partition with thin light frames, a
# concrete room behind it (a ring lamp, a bright window), the QUANTUMSPACE decal on the glass
# (a big charcoal Q crossed by a blue orbit, the TUM logo above), whiteboards below the glass.

OFFICE_WALL = (208, 208, 216)
CONCRETE = (160, 152, 144)
CONCRETE_DARK = (136, 128, 120)
MULLION = (216, 216, 224)
BOARD = (224, 228, 236)
CHARCOAL = (56, 56, 64)
TUM_BLUE = (48, 96, 176)        # the TUM blue, on the GBA grid
MARKER = (40, 72, 160)


DECAL = load_image("quantum_space.png")     # the whole decal, built by tools/make_decal.py
DECAL_U = (95, 45)                          # its first U's centre, at the capitals' top


def _quantum_space(surf, lamp_center) -> None:
    """The QUANTUMSPACE decal: the MQT logo's Q and lettering, laid out as on the wall
    (tools/make_decal.py builds it). On the wall, the first U's centre is a little right of
    the ring lamp's centre and about 51 game px below it."""
    surf.blit(DECAL, (lamp_center[0] + 3 - DECAL_U[0], lamp_center[1] + 51 - DECAL_U[1]))


def _chair(surf, x: int, floor: int, facing: int) -> None:
    """An office chair, side on: a backrest, the seat, the gas lift and a five-star base."""
    seat = pygame.Rect(0, 0, 26, 7)
    seat.midbottom = (x, floor - 30)
    _box(surf, (x - 3, floor - 30, 6, 18), P.shade(P.SLATE, 0.6), radius=1)          # the gas lift
    _box(surf, (x - 15, floor - 12, 30, 4), P.shade(P.SLATE, 0.5), radius=1)         # the base
    for dx in (-14, 0, 14):
        pygame.draw.circle(surf, P.INK, (x + dx, floor - 5), 3)
    _box(surf, seat, P.SLATE, radius=3)
    back = pygame.Rect(0, 0, 8, 22)
    back.bottomleft = (x - facing * 14 - 4, seat.top + 2)
    _box(surf, back, P.SLATE, radius=3)


def _desk(surf, x: int, floor: int) -> None:
    """A desk: a light wooden top on white legs, two monitors, a keyboard."""
    for k in (0, 1):
        mon = pygame.Rect(x + 8 + k * 38, floor - 86, 34, 24)
        _box(surf, mon, P.INK, radius=2, ink=1)
        surf.fill(P.shade(TUM_BLUE, 0.7), mon.inflate(-4, -4))
        surf.fill(P.lighten(TUM_BLUE, 0.3), (mon.x + 4, mon.y + 4, 14, 2))
        surf.fill(P.INK, (mon.centerx - 1, mon.bottom, 3, 6))
    _box(surf, (x + 20, floor - 59, 30, 3), P.MIST, radius=1)                         # the keyboard
    _box(surf, (x, floor - 56, 88, 6), (208, 176, 128), radius=1)
    for lx in (x + 4, x + 78):
        _box(surf, (lx, floor - 50, 5, 46), P.lighten(BOARD, 0.2), radius=1)


def _office(surf, lights: Lights) -> None:
    m = MARGIN
    floor = FLOOR_Y + m
    width = W + 2 * m
    glass_top, glass_bottom = 38, 196
    surf.fill(OFFICE_WALL)
    # behind the glass: a concrete room, a ring lamp, a bright window on the right
    room = pygame.Rect(0, glass_top, width, glass_bottom - glass_top)
    surf.fill(CONCRETE, room)
    for x in range(0, width, 70):
        surf.fill(CONCRETE_DARK, (x, glass_top, 2, room.h))
    for k in range(40):                         # the concrete's pores
        surf.fill(CONCRETE_DARK, ((k * 97) % width, glass_top + 6 + (k * 53) % (room.h - 12), 2, 2))
    window = pygame.Rect(width - 150, glass_top + 40, 150, room.h - 40)
    surf.fill((200, 216, 232), window)
    for x in range(window.x, width, 30):
        pygame.draw.line(surf, CONCRETE_DARK, (x, window.y), (x + 20, window.bottom), 3)
    surf.fill((176, 168, 160), (0, glass_bottom - 50, 190, 50))        # a cupboard beyond
    lamp = pygame.Rect(0, 0, 150, 32)          # the ring lamp, as wide as the wall's
    lamp.center = (222, glass_top + 18)          # so the decal below it is centred
    pygame.draw.ellipse(surf, P.lighten(P.CREAM, 0.4), lamp.inflate(6, 4), 6)
    pygame.draw.ellipse(surf, P.WHITE, lamp, 3)
    # the glass: a faint sheen, thin light frames
    for x in range(30, width, 160):
        pygame.draw.line(surf, P.lighten(CONCRETE, 0.35), (x, glass_top + 4), (x + 40, glass_bottom - 4), 2)
    for x in (0, 168, 418, width - 6):
        surf.fill(MULLION, (x, glass_top, 3, room.h))
    surf.fill(MULLION, (0, glass_top - 4, width, 4))
    _quantum_space(surf, lamp.center)
    # below the glass: whiteboards, with scribbles, magnets and a marker tray
    boards = pygame.Rect(0, glass_bottom, width, floor - glass_bottom)
    surf.fill(BOARD, boards)
    for x in (0, 168, 418, width - 6):
        surf.fill(P.shade(BOARD, 0.85), (x, glass_bottom, 2, boards.h))
    f = load_font(8)
    for text, x, y in (("|0>", 272, 250), ("H|0>=|+>", 300, 270), ("<psi|", 380, 206)):
        surf.blit(f.render(text, False, MARKER), (x, y))
    for y in (218, 232):                        # a little circuit
        pygame.draw.line(surf, MARKER, (300, y), (380, y), 1)
    pygame.draw.rect(surf, MARKER, (318, 212, 12, 12), 1)
    pygame.draw.line(surf, MARKER, (350, 218), (350, 232), 1)
    pygame.draw.circle(surf, MARKER, (350, 218), 2)
    pygame.draw.circle(surf, MARKER, (350, 232), 4, 1)
    for i, (x, y, c) in enumerate(((520, 206, P.BAD), (536, 210, P.GOLD), (528, 222, P.SKY), (104, 208, P.GOLD))):
        pygame.draw.circle(surf, P.INK, (x, y), 5)
        pygame.draw.circle(surf, c, (x, y), 4)
    surf.fill(P.shade(BOARD, 0.8), (346, 292, 44, 4))                   # the marker tray
    for k, c in enumerate((MARKER, P.INK, P.BAD, MARKER)):
        surf.fill(c, (350 + k * 9, 278, 5, 14))
    # the open-plan floor in front of them: desks and chairs
    for x, facing in ((20, 1), (150, -1), (424, 1), (552, -1)):
        _desk(surf, x, floor)
        _chair(surf, x + 44 + facing * 30, floor, facing)
    # the floor: grey carpet tiles
    _tiled_floor(surf, (120, 120, 136), (96, 96, 112), (144, 144, 160))
