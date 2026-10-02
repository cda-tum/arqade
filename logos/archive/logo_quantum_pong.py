"""Quantum Pong key art: the moment a ball hits an H gate and splits in two.

The ball comes off P1's paddle (left, blue glow), streaks across the field
and hits a big H gate in the middle; two balls fly out of it, one carrying
on towards P2's paddle (right, red glow), one turned back. The other gates
(X, Z, SWAP) hang in the field at smaller scales, for depth. The title sits
above in the game's own Press Start 2P, lettered in a blue-to-red sweep
that follows the cabinet's two sides.

Built from the game itself: the gates and balls are drawn by its own
main._draw_gate / main._draw_ball (at the game's native pixel size, then
integer-upscaled), with its GATE_COLORS, paddle and ball sizes and colours
from config.py, and the two split balls come from gates.apply_h stepped
along by pong.step_ball -- so the "after" trails follow the game's physics.
"""

from __future__ import annotations

import math
import random
import sys

import kit
import pygame

sys.path.insert(0, str(kit.ROOT / "quantum-pong/src"))

from quantum_pong import config, fonts  # noqa: E402
from quantum_pong import main as qp  # noqa: E402
from quantum_pong.gates import Gate, apply_h  # noqa: E402
from quantum_pong.pong import Ball, step_ball  # noqa: E402

ROM = "quantum_pong"

BG = config.COLOR_BACKGROUND
P1_BLUE = (70, 150, 255)
P2_RED = (255, 70, 90)
H_COLOR = config.GATE_COLORS["H"]
# Title sweep: P1 blue, through Z's purple, to P2 red-pink.
TITLE_STOPS = [(110, 200, 255), (175, 130, 255), (255, 110, 150)]


# --- game sprites, drawn by the game's own functions ---------------------------


def gate_sprite(kind: str, k: int) -> pygame.Surface:
    """One gate exactly as main._draw_gate draws it, upscaled k times."""
    label_surfaces = qp._make_gate_label_surfaces(fonts.load_font(10))
    n = config.GATE_RADIUS * 2 + 2
    surf = pygame.Surface((n, n), pygame.SRCALPHA)
    qp._draw_gate(surf, label_surfaces, Gate(kind=kind, x=n / 2, y=n / 2, spawned_at=0.0))
    return kit.nearest(surf, k)


def ball_sprite(k: int) -> pygame.Surface:
    """The ball as main._draw_ball draws it (white with a dark 1px rim)."""
    n = config.BALL_RADIUS * 2 + 2
    surf = pygame.Surface((n, n), pygame.SRCALPHA)
    qp._draw_ball(surf, Ball(x=n / 2, y=n / 2, vx=0, vy=0))
    return kit.nearest(surf, k)


def paddle_sprite(k: int) -> pygame.Surface:
    """A paddle as run_game draws it: PADDLE_WIDTH x PADDLE_HEIGHT, radius 2."""
    surf = pygame.Surface((config.PADDLE_WIDTH, config.PADDLE_HEIGHT), pygame.SRCALPHA)
    pygame.draw.rect(surf, config.COLOR_PADDLE, surf.get_rect(), border_radius=2)
    return kit.nearest(surf, k)


# --- effects -------------------------------------------------------------------


def lit(dst: pygame.Surface, sprite: pygame.Surface, center, color, radius: int, strength=1.0):
    """Blit `sprite` with a soft coloured halo behind it."""
    halo = kit.glow(kit.pad(sprite, radius * 2), color, radius, strength)
    kit.blit_center(dst, halo, center)
    kit.blit_center(dst, sprite, center)


def trail(size, points, color, width: float) -> pygame.Surface:
    """A comet tail along `points` (oldest first): thin and dim at the tail,
    full width and white-hot at the head. Blit it with BLEND_ADD."""
    core = pygame.Surface(size)
    n = len(points)
    for i, (x, y) in enumerate(points):
        t = (i + 1) / n
        w = max(1.0, width * t ** 0.7)
        pygame.draw.circle(core, kit.shade(color, t ** 1.6), (x, y), w)
        pygame.draw.circle(core, kit.shade(kit.lerp(color, (255, 255, 255), 0.7), t ** 2.2), (x, y), w * 0.45)
    out = kit.blur(core, round(width * 2.5))
    out.blit(core, (0, 0), special_flags=pygame.BLEND_ADD)
    out.blit(kit.blur(core, round(width * 6)), (0, 0), special_flags=pygame.BLEND_ADD)
    return out


def path(start, end, steps: int = 120):
    return [(start[0] + (end[0] - start[0]) * i / steps, start[1] + (end[1] - start[1]) * i / steps)
            for i in range(steps + 1)]


def ring(dst: pygame.Surface, center, radius: float, color, width: int):
    """The game's catch/score flash ring (main._draw_flash), soft-lit."""
    layer = pygame.Surface(dst.get_size())
    pygame.draw.circle(layer, color, center, radius, width)
    dst.blit(kit.blur(layer, width * 4), (0, 0), special_flags=pygame.BLEND_ADD)
    dst.blit(layer, (0, 0), special_flags=pygame.BLEND_ADD)


# --- the scene -----------------------------------------------------------------


def background(size: int) -> pygame.Surface:
    """Field, light and the far-away gates; vignette and scanlines go on this."""
    s = size / 1024
    surf = pygame.Surface((size, size))
    surf.fill(BG)

    # coloured light from each player's side
    surf.blit(kit.radial((size, size), (-0.05 * size, 0.62 * size), 0.75 * size, P1_BLUE, 0.55),
              (0, 0), special_flags=pygame.BLEND_ADD)
    surf.blit(kit.radial((size, size), (1.05 * size, 0.78 * size), 0.75 * size, P2_RED, 0.5),
              (0, 0), special_flags=pygame.BLEND_ADD)

    # faint field grid and the game's midline, in COLOR_MIDLINE
    grid = pygame.Surface((size, size))
    step = round(64 * s)
    for x in range(0, size, step):
        pygame.draw.line(grid, kit.shade(config.COLOR_MIDLINE, 0.35), (x, 0), (x, size))
    for y in range(0, size, step):
        pygame.draw.line(grid, kit.shade(config.COLOR_MIDLINE, 0.35), (0, y), (size, y))
    surf.blit(grid, (0, 0), special_flags=pygame.BLEND_ADD)
    mid = pygame.Surface((size, size))
    for y in range(0, size, round(32 * s)):
        pygame.draw.rect(mid, config.COLOR_MIDLINE, (size // 2 - round(3 * s), y, round(6 * s), round(18 * s)))
    surf.blit(kit.blur(mid, 8), (0, 0), special_flags=pygame.BLEND_ADD)
    surf.blit(mid, (0, 0), special_flags=pygame.BLEND_ADD)

    # waiting gates, small and dim = far away
    for kind, pos, dim in [("X", (0.80, 0.49), 0.6), ("Z", (0.17, 0.90), 0.6),
                           ("SWAP", (0.25, 0.47), 0.55)]:
        g = gate_sprite(kind, max(1, round(2 * s)))
        g.fill((*kit.shade((255, 255, 255), dim), 255), special_flags=pygame.BLEND_RGBA_MULT)
        lit(surf, g, (pos[0] * size, pos[1] * size), kit.shade(config.GATE_COLORS[kind], 0.7),
            round(18 * s), 0.6)
    return surf


def sparks(size: int, center, color, count: int, rng: random.Random) -> pygame.Surface:
    """Square pixel sparks flying out of the gate, each with a short streak."""
    s = size / 1024
    layer = pygame.Surface((size, size))
    for _ in range(count):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(120, 300) * s
        x, y = center[0] + math.cos(a) * d, center[1] + math.sin(a) * d
        tail = rng.uniform(20, 60) * s
        c = kit.lerp(color, (255, 255, 255), rng.uniform(0, 0.6))
        f = 1 - (d / s - 120) / 220
        pygame.draw.line(layer, kit.shade(c, 0.35 * f), (x, y),
                         (x - math.cos(a) * tail, y - math.sin(a) * tail), max(1, round(3 * s)))
        k = max(2, round(rng.choice([6, 8, 10]) * s))
        pygame.draw.rect(layer, kit.shade(c, f), (x - k / 2, y - k / 2, k, k))
    out = kit.blur(layer, 6)
    out.blit(layer, (0, 0), special_flags=pygame.BLEND_ADD)
    return out


def action(surf: pygame.Surface) -> None:
    """The rally itself, drawn over the finished background so it stays crisp."""
    size = surf.get_width()
    s = size / 1024
    add = pygame.BLEND_ADD

    # paddles: P1 left (blue), P2 right (red); the game's white paddles, lit
    pk = max(1, round(5 * s))
    p1_c = (0.075 * size, 0.56 * size)
    p2_c = (0.925 * size, 0.86 * size)
    lit(surf, paddle_sprite(pk), p1_c, P1_BLUE, round(34 * s), 1.0)
    lit(surf, paddle_sprite(pk), p2_c, P2_RED, round(34 * s), 1.0)

    # the rally: off P1's paddle (with the game's catch flash ring) into the H gate...
    gate_c = (0.5 * size, 0.70 * size)
    hit = (p1_c[0] + pk * config.PADDLE_WIDTH / 2 + config.BALL_RADIUS * 5 * s, 0.53 * size)
    ring(surf, hit, 40 * s, P1_BLUE, max(2, round(5 * s)))
    ring(surf, hit, 66 * s, kit.shade(P1_BLUE, 0.4), max(2, round(3 * s)))
    surf.blit(trail((size, size), path(hit, gate_c), (110, 170, 255), 18 * s), (0, 0), special_flags=add)

    # ...which splits it with the game's own apply_h; step both halves on
    vx, vy = gate_c[0] - hit[0], gate_c[1] - hit[1]
    norm = math.hypot(vx, vy)
    incoming = Ball(x=gate_c[0], y=gate_c[1], vx=vx / norm * 640 * s, vy=vy / norm * 640 * s)
    heads = []
    for ball, color in zip(apply_h(incoming), [(255, 110, 140), H_COLOR]):
        pts = [(ball.x, ball.y)]
        for _ in range(60):
            ball = step_ball(ball, 1 / 120, size, config.BALL_RADIUS * pk)
            pts.append((ball.x, ball.y))
        surf.blit(trail((size, size), pts, color, 16 * s), (0, 0), special_flags=add)
        heads.append((pts[-1], color))

    # the hero H gate, with its shock rings and sparks
    surf.blit(kit.radial((size, size), gate_c, 0.32 * size, H_COLOR, 0.6), (0, 0), special_flags=add)
    ring(surf, gate_c, 180 * s, kit.shade(H_COLOR, 0.6), max(2, round(4 * s)))
    ring(surf, gate_c, 240 * s, kit.shade(H_COLOR, 0.25), max(2, round(3 * s)))
    surf.blit(sparks(size, gate_c, H_COLOR, 28, random.Random(3)), (0, 0), special_flags=add)
    lit(surf, gate_sprite("H", max(1, round(5 * s))), gate_c, H_COLOR, round(40 * s), 1.0)

    # ball heads last, so they sit on top of everything
    bk = max(1, round(6 * s))
    for (x, y), color in heads:
        lit(surf, ball_sprite(bk), (x, y), color, round(26 * s), 1.2)


# --- lettering ------------------------------------------------------------------


def _title_line(text: str, px: int, s: float) -> pygame.Surface:
    return kit.wordmark(
        kit.text_shape(text, kit.PIXEL_FONT, px), TITLE_STOPS, vertical=False,
        gap=max(2, round(6 * s)), outline=max(2, round(7 * s)),
        extrude=max(2, round(12 * s)), extrude_color=(40, 20, 80),
        glow_color=(140, 90, 255), glow_radius=round(40 * s), glow_strength=0.6,
        square=True,
    )


def art(size: int) -> pygame.Surface:
    s = size / 1024
    out = kit.finish(background(size), vignette_strength=0.65, scan=True)
    action(out)
    top = _title_line("QUANTUM", 120 * s, s)
    big = _title_line("PONG", 200 * s, s)
    kit.blit_center(out, big, (size / 2, 0.315 * size))
    kit.blit_center(out, top, (size / 2, 0.135 * size))
    return out


def marquee() -> pygame.Surface:
    line = _title_line("QUANTUM PONG", 112, 1.0)
    # the four gates underneath, as the game draws them
    chips = [gate_sprite(kind, 2) for kind in ["H", "X", "Z", "SWAP"]]
    gap = 36
    row_w = sum(c.get_width() for c in chips) + gap * (len(chips) - 1)
    h = line.get_height() + chips[0].get_height() + 10
    out = pygame.Surface((max(line.get_width(), row_w), h), pygame.SRCALPHA)
    out.blit(line, ((out.get_width() - line.get_width()) // 2, 0))
    x = (out.get_width() - row_w) // 2
    for c in chips:
        out.blit(c, (x, line.get_height() - 30))
        x += c.get_width() + gap
    return kit.trim(out)
