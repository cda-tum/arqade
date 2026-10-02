"""Qlimbers (quantum-towers): two stone towers racing up into a dusk sky.

The composition is a low-angle shot near the top of the race. P1's tower
(cyan climber, left) is nearer and taller -- the climber clings to the
gold band of the winning floor, speed streaks trailing below -- while
P2's (orange, right) stands further back and a floor behind, firing the
game's attack beam across the gap at the leader. Both towers lean in
towards a vanishing point above the frame, the setting sun backlights the
gap between them, and the game's own clouds drift below
the climbers so it reads as "high up".

Everything on the towers is the game's real drawing code, rendered at the
game's internal resolution and nearest-upscaled like the cabinet does:
`visuals._draw_tower_body` (stone, floor bands, gold/slate target panels
with `notation.render_state` kets, crenellated roof), `visuals.draw_climber`
in its climbing and attack poses, `visuals.draw_muzzle_flash`, and the
cloud puffs of `visuals._draw_cloud`. Colours come from `config`. The only
replicated piece is main.py's `_draw_attack_beam` (line plus spark), which
has to be drawn in final coordinates since it spans both towers.
"""

from __future__ import annotations

import math
import random
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "quantum-towers/src"))

from quantum_towers import config, fonts, visuals  # noqa: E402
from quantum_towers.quantum import State  # noqa: E402

ROM = "quantum_towers"

_R = 1 / math.sqrt(2)
# The last two floors' targets. Both players climb the same target chain,
# so P2's slate "next" panel shows the gold one P1 is about to match.
T15 = State(0j, 1j)  # i|1>
T16 = State(_R + 0j, _R + 0j)  # |+>

TITLE_STOPS = [(255, 245, 170), config.COLOR_HINT, config.COLOR_TARGET, (215, 110, 30)]


# --- the game's tower, rendered at internal resolution -----------------------


_MARGIN = 34  # room beside a tower's wall for the climber and the muzzle flash


def _tower_sprite(width: int, floor: int, below: int, current: State, nxt: State,
                  color: kit.Color, side: str, t: float, climb: float | None = None,
                  attack: float | None = None, haze: tuple[int, int, int, int] | None = None
                  ) -> tuple[pygame.Surface, tuple[int, int]]:
    """One tower plus its climber, like visuals.draw_tower() but cut so the
    crenellated roof sits at the sprite's top, with `below` cleared floors
    under the climber (more can run off the bottom of the frame). `side` is
    the climber's wall: "right" for P1, "left" for P2. `haze` (RGBA) is laid
    over the stone only, not the climber, to push a tower back in depth.
    Returns the sprite and the climber's chest position (for the beam)."""
    band = config.TOWER_BAND_HEIGHT
    margin = _MARGIN
    above = config.TOWER_HEIGHT + 1 - floor  # bands from the climber's floor to the roof
    rect = pygame.Rect(margin, 12, width, (above + below) * band)  # 12 px for crenellations
    surf = pygame.Surface((width + 2 * margin, rect.bottom), pygame.SRCALPHA)
    ladder = [fonts.load_font(8)]
    # camera exactly on the player's floor, as when a climb has settled
    visual_floor = floor - below
    visuals._draw_tower_body(surf, rect, floor, visual_floor, current, nxt, ladder)
    if haze:
        veil = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        veil.fill(haze)
        veil.blit(surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)  # clip to the stone's alpha
        surf.blit(veil, (0, 0))
    wall_x, facing = (rect.right, -1) if side == "right" else (rect.left, 1)
    # feet at the bottom of the gold "current" band, like draw_tower()
    feet_y = rect.bottom - (floor + 1 - visual_floor) * band
    # the climber gets a 1 px dark outline (the game's text-outline colour),
    # so the figure stays readable against the busy sunset behind it
    fig = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    visuals.draw_climber(fig, wall_x, feet_y, color, t, facing, climb, attack)
    surf.blit(kit.dilate(fig, 1, config.COLOR_TEXT_SHADOW, square=True), (0, 0))
    surf.blit(fig, (0, 0))
    chest = (wall_x - facing * 10, feet_y - 20)
    if attack is not None:
        visuals.draw_muzzle_flash(surf, chest[0] - facing * 16, chest[1], color, attack)
    return surf, chest


# --- perspective --------------------------------------------------------------


def _keystone(layer: pygame.Surface, vanish: tuple[float, float]) -> pygame.Surface:
    """Squeeze each row of `layer` towards the vanishing point, so vertical
    edges converge upwards (a low-angle shot). Rows are scaled with nearest
    neighbour, which keeps the pixel art crisp."""
    w, h = layer.get_size()
    vx, vy = vanish
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    step = 2
    for y in range(0, h, step):
        s = (y - vy) / (h - vy)
        row = layer.subsurface((0, y, w, min(step, h - y)))
        if row.get_bounding_rect().width == 0:
            continue
        nw = max(1, round(w * s))
        out.blit(pygame.transform.scale(row, (nw, row.get_height())), (round(vx - vx * s), y))
    return out


def _project(p: tuple[float, float], size: int, vanish: tuple[float, float]) -> tuple[float, float]:
    vx, vy = vanish
    s = (p[1] - vy) / (size - vy)
    return vx + (p[0] - vx) * s, p[1]


# --- sky -----------------------------------------------------------------------


def _sky(size: int) -> pygame.Surface:
    """Dusk version of the game's sky: night navy (the title screen's
    COLOR_BACKGROUND) at the top, warm sun-glow at the horizon."""
    sky = kit.gradient((size, size), [
        config.COLOR_BACKGROUND, (22, 22, 52), (52, 40, 92), (140, 70, 96),
        kit.shade(config.COLOR_TARGET, 0.95), kit.shade(config.COLOR_SUN, 1.0),
    ]).convert()
    rng = random.Random(7)
    for _ in range(140):  # stars, only in the dark upper half
        x, y = rng.randrange(size), rng.randrange(round(size * 0.5))
        b = rng.randint(90, 230) * (1 - y / (size * 0.55))
        r = 2 if rng.random() < 0.15 else 1
        pygame.draw.rect(sky, (round(b), round(b), min(255, round(b * 1.1))), (x, y, r * 2, r * 2))
    sun = (size * 0.5, size * 0.80)
    sky.blit(kit.radial((size, size), sun, size * 0.75, (255, 150, 70), 0.55), (0, 0),
             special_flags=pygame.BLEND_ADD)
    pygame.draw.circle(sky, config.COLOR_SUN, sun, size * 0.11)
    sky.blit(kit.radial((size, size), sun, size * 0.22, (255, 240, 200), 0.5), (0, 0),
             special_flags=pygame.BLEND_ADD)
    return sky


def _cloud(k: int, color: kit.Color) -> pygame.Surface:
    """The game's own cloud puff (visuals._draw_cloud), nearest-upscaled like the towers."""
    small = pygame.Surface((80, 44), pygame.SRCALPHA)
    visuals._draw_cloud(small, 30, 24)
    # threshold away gfxdraw's anti-aliased fringe, which would otherwise
    # upscale into a dark ring of half-transparent pixels
    mask = pygame.mask.from_threshold(small, config.COLOR_CLOUD, (60, 60, 60, 255))
    solid = mask.to_surface(setcolor=(*color, 255), unsetcolor=(0, 0, 0, 0))
    return kit.nearest(solid, k)


def _clouds(dst: pygame.Surface, size: int, band: list[tuple[float, float, int, kit.Color]]) -> None:
    for fx, fy, k, c in band:
        kit.blit_center(dst, _cloud(k, c), (fx * size, fy * size))


# --- art -------------------------------------------------------------------------


def _place(sprite: pygame.Surface, k: int, body_left: int, top: int, size: int,
           vanish: tuple[float, float]) -> pygame.Surface:
    """Upscale a tower sprite by `k`, put its body's left edge at `body_left`
    and its roof at `top`, and lean it into the perspective."""
    layer = pygame.Surface((size, size), pygame.SRCALPHA)
    layer.blit(kit.nearest(sprite, k), (body_left - _MARGIN * k, top))
    return _keystone(layer, vanish)


def _scene(size: int) -> pygame.Surface:
    canvas = _sky(size)
    vanish = (size * 0.5, -size * 1.6)
    band = config.TOWER_BAND_HEIGHT

    # far clouds, behind the towers
    _clouds(canvas, size, [
        (0.10, 0.62, 5, (196, 120, 130)), (0.93, 0.58, 4, (190, 115, 135)),
        (0.50, 0.97, 6, (240, 165, 120)),
    ])

    # P2 (right): further back (x4) and a floor behind, firing at the leader
    k2, w2, left2, top2 = 4, 64, 730, 420
    # (a dusky haze on its stone so it sits behind P1's)
    p2, chest2 = _tower_sprite(w2, 14, 1, T15, T16, config.COLOR_PLAYER_2, "left", 0.3,
                               attack=0.55, haze=(60, 40, 90, 60))
    canvas.blit(_place(p2, k2, left2, top2, size, vanish), (0, 0))
    # the gold "current" band glows like the beacon it is
    gold2 = (left2 + w2 * k2 / 2, top2 + (12 + band * 1.5) * k2)
    canvas.blit(kit.radial((size, size), _project(gold2, size, vanish), 170, (120, 70, 10), 0.8),
                (0, 0), special_flags=pygame.BLEND_ADD)

    # mid cloud drifting through the gap
    _clouds(canvas, size, [(0.66, 0.90, 6, (245, 190, 165))])

    # P1 (left): nearer (x5), one confirm away from the winning floor
    k1, w1, left1, top1 = 5, 64, 34, 350
    p1, chest1 = _tower_sprite(w1, 15, 1, T16, T16, config.COLOR_PLAYER_1, "right", 0.0, climb=0.5)
    canvas.blit(_place(p1, k1, left1, top1, size, vanish), (0, 0))
    gold1 = (left1 + w1 * k1 / 2, top1 + (12 + band * 0.5) * k1)
    canvas.blit(kit.radial((size, size), _project(gold1, size, vanish), 220, (130, 80, 10), 0.8),
                (0, 0), special_flags=pygame.BLEND_ADD)

    # speed streaks trailing below P1's climber: the leader is mid-pull-up
    climber1 = _project((left1 - _MARGIN * k1 + chest1[0] * k1, top1 + chest1[1] * k1), size, vanish)
    streaks = pygame.Surface((size, size), pygame.SRCALPHA)
    for dx, y0, length in ((-22, 110, 170), (2, 135, 120), (26, 115, 90)):
        x = climber1[0] + dx
        for i in range(length):  # brightest near the climber, fading out below
            alpha = round(230 * (1 - i / length) ** 1.5)
            pygame.draw.line(streaks, (*kit.lerp(config.COLOR_PLAYER_1, (255, 255, 255), 0.35), alpha),
                             (x, climber1[1] + y0 + i), (x + 5, climber1[1] + y0 + i))
    canvas.blit(kit.glow(streaks, config.COLOR_PLAYER_1, 10, 0.6), (0, 0))
    canvas.blit(streaks, (0, 0))

    # the attack beam: main.py's _draw_attack_beam (a line, plus a spark
    # travelling along it), scaled up, with a white-hot core and a glow
    a = _project((left2 - _MARGIN * k2 + (chest2[0] - 16) * k2, top2 + chest2[1] * k2), size, vanish)
    b = _project((left1 - _MARGIN * k1 + chest1[0] * k1, top1 + chest1[1] * k1), size, vanish)
    t = 0.58
    spark = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    beam = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.line(beam, config.COLOR_PLAYER_2, a, b, 2 * k2)
    pygame.draw.circle(beam, config.COLOR_PLAYER_2, spark, 5 * k2 + 4)
    canvas.blit(kit.glow(beam, (255, 120, 40), 26, 1.0), (0, 0))
    canvas.blit(beam, (0, 0))
    pygame.draw.line(canvas, (255, 220, 170), a, spark, 3)
    pygame.draw.circle(canvas, (255, 240, 210), spark, 5 * k2 - 6)

    # near clouds, in front of both tower bases
    _clouds(canvas, size, [
        (0.20, 1.03, 7, (255, 215, 195)), (0.82, 1.05, 7, (245, 195, 180)),
    ])
    return canvas


def _title(scale: int = 14) -> pygame.Surface:
    shape = kit.text_shape("QLIMBERS", kit.PIXEL_FONT, 8 * scale)
    return kit.wordmark(
        shape, TITLE_STOPS, gap=5, outline=7, extrude=12, extrude_color=(70, 40, 60),
        glow_color=(255, 150, 60), glow_radius=30, glow_strength=0.7, square=True,
    )


def art(size: int) -> pygame.Surface:
    canvas = kit.finish(_scene(size), vignette_strength=0.55)
    title = kit.fit(_title(), size - 60, size * 0.3, smooth=False)
    kit.blit_center(canvas, title, (size / 2, size * 0.14))
    tag = kit.tagline("Race to the top, one qubit at a time", 26, (255, 230, 200), tracking=4)
    kit.blit_center(canvas, tag, (size / 2, size * 0.27))
    return canvas


def marquee() -> pygame.Surface:
    return _title(16)
