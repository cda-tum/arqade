"""Everything on screen: a neon vector look, all procedural.

Expensive things are drawn once and kept: the background, a persistent
board holding every solid trail (each tick only stamps the new segment
onto it, with BLEND_MAX so glows never dim a neighbouring core), one ghost
layer per player, and the scanline overlay. Per frame that is one opaque
blit of the board, the ghost layers only while someone is split, a few
small sprites, and the scanlines.
"""

from __future__ import annotations

import math

import pygame

from qurves import config, rules
from qurves.fonts import load_font
from qurves.fx import Fx
from qurves.match import COUNTDOWN, MATCH_RESULT, ROUND, ROUND_RESULT, TITLE, Match

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
CELL, HUD = config.CELL, config.HUD_HEIGHT
GLOW_R = 5  # how far a trail's glow reaches past its centre line, in px
WHITE = (255, 255, 255)


def scale(color, k: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, round(c * k))) for c in color)


def lighten(color, k: float) -> tuple[int, int, int]:
    return tuple(round(c + (255 - c) * k) for c in color)


def cell_px(c) -> tuple[int, int]:
    """The pixel centre of grid cell c."""
    return (c[0] * CELL + CELL // 2, HUD + c[1] * CELL + CELL // 2)


# --- pre-rendered pieces --------------------------------------------------------------


def _stroke_layers():
    """(radius, brightness) from the outer glow in to the bright core."""
    if config.GLOW:
        return ((5, 0.24), (3, 0.55), (1, 1.0))
    return ((1, 1.0),)


def make_stamps(color, ghost: bool = False) -> dict[bool, pygame.Surface]:
    """Capsules for one trail segment between neighbouring cell centres, keyed
    by horizontal (True) or vertical (False). Solid stamps are opaque on black,
    for BLEND_MAX onto the board. Ghost stamps carry their brightness in alpha,
    for BLEND_RGBA_MAX onto a transparent ghost layer."""
    size = (CELL + 2 * GLOW_R + 1, 2 * GLOW_R + 1)
    a, b = (GLOW_R, GLOW_R), (GLOW_R + CELL, GLOW_R)
    surf = pygame.Surface(size, pygame.SRCALPHA) if ghost else pygame.Surface(size)
    surf.fill((0, 0, 0, 0) if ghost else (0, 0, 0))
    for radius, k in _stroke_layers():
        hue = lighten(color, 0.55) if k >= 1.0 else color
        paint = (*hue, min(255, round(255 * k * 1.15))) if ghost else scale(hue, k)
        pygame.draw.line(surf, paint, a, b, 2 * radius + 1)
        pygame.draw.circle(surf, paint, a, radius)
        pygame.draw.circle(surf, paint, b, radius)
    return {True: surf, False: pygame.transform.rotate(surf, 90)}


def make_glow(color, radius: int, k: float = 1.0) -> pygame.Surface:
    """A soft round halo with a hot white-ish core, on black, for BLEND_ADD."""
    surf = pygame.Surface((2 * radius + 1, 2 * radius + 1))
    surf.fill((0, 0, 0))
    centre = (radius, radius)
    if config.GLOW:
        for r in range(radius, 0, -1):
            f = (1 - r / (radius + 1)) ** 1.1
            pygame.draw.circle(surf, scale(lighten(color, 0.6 * f), f * k), centre, r)
    pygame.draw.circle(surf, scale(lighten(color, 0.85), k), centre, 2)
    return surf


def make_token(font: pygame.font.Font, k: float) -> pygame.Surface:
    """An H gate pickup at brightness k, on black, for BLEND_ADD."""
    surf = pygame.Surface((25, 25))
    surf.fill((0, 0, 0))
    centre = 12
    if config.GLOW:
        for r in range(12, 6, -1):
            pygame.draw.circle(surf, scale(config.COLOR_PICKUP, 0.5 * k * (1 - r / 13) ** 1.2), (centre, centre), r)
    pygame.draw.rect(surf, (10, 12, 26), (centre - 6, centre - 6, 13, 13), border_radius=3)
    pygame.draw.rect(surf, scale(config.COLOR_PICKUP, k), (centre - 6, centre - 6, 13, 13), 1, border_radius=3)
    letter = font.render("H", False, scale(WHITE, k), (0, 0, 0))
    surf.blit(letter, letter.get_rect(center=(centre + 1, centre + 1)), special_flags=pygame.BLEND_MAX)
    return surf


def glow_text(font: pygame.font.Font, text: str, color) -> pygame.Surface:
    """Text with a halo, on black, for BLEND_ADD."""
    core = font.render(text, False, lighten(color, 0.45), (0, 0, 0))
    pad = 4
    surf = pygame.Surface((core.get_width() + 2 * pad, core.get_height() + 2 * pad))
    surf.fill((0, 0, 0))
    if config.GLOW:
        halo = font.render(text, False, scale(color, 0.45), (0, 0, 0))
        for dx in (-2, 0, 2):
            for dy in (-2, 0, 2):
                surf.blit(halo, (pad + dx, pad + dy), special_flags=pygame.BLEND_MAX)
    surf.blit(core, (pad, pad), special_flags=pygame.BLEND_MAX)
    return surf


def make_logo(font: pygame.font.Font) -> pygame.Surface:
    """QURVES, shading letter by letter from P1's cyan to P2's orange."""
    word = "QURVES"
    a, b = config.PLAYER_COLORS["p1"], config.PLAYER_COLORS["p2"]
    pieces = []
    for i, ch in enumerate(word):
        k = i / (len(word) - 1)
        pieces.append(glow_text(font, ch, tuple(round(a[j] + (b[j] - a[j]) * k) for j in range(3))))
    overlap = 8  # each piece's halo padding, both sides
    surf = pygame.Surface((sum(p.get_width() for p in pieces) - overlap * (len(pieces) - 1),
                           max(p.get_height() for p in pieces)))
    surf.fill((0, 0, 0))
    x = 0
    for p in pieces:
        surf.blit(p, (x, 0), special_flags=pygame.BLEND_MAX)
        x += p.get_width() - overlap
    return surf


def make_background() -> pygame.Surface:
    s = pygame.Surface((W, H))
    s.fill(config.COLOR_HUD)
    arena = pygame.Rect(0, HUD, W, config.GRID_H * CELL)
    inner = arena.inflate(-2 * CELL, -2 * CELL)
    s.fill(config.COLOR_WALL_FILL, arena)
    s.fill(config.COLOR_BACKGROUND, inner)
    for x in range(4, config.GRID_W - 1, 4):
        pygame.draw.line(s, config.COLOR_GRID, (x * CELL, inner.top), (x * CELL, inner.bottom - 1))
    for y in range(4, config.GRID_H - 1, 4):
        pygame.draw.line(s, config.COLOR_GRID, (inner.left, HUD + y * CELL), (inner.right - 1, HUD + y * CELL))
    if config.GLOW:
        pygame.draw.rect(s, scale(config.COLOR_WALL, 0.35), inner.inflate(4, 4), 3)
    pygame.draw.rect(s, config.COLOR_WALL, inner.inflate(2, 2), 1)
    # Vignette: a tiny brightness map, smoothly scaled up and multiplied in.
    vignette = pygame.Surface((32, 18))
    for vy in range(18):
        for vx in range(32):
            dx, dy = (vx + 0.5) / 16 - 1, (vy + 0.5) / 9 - 1
            f = max(0.55, 1 - 0.45 * (dx * dx + dy * dy))
            vignette.set_at((vx, vy), (round(255 * f),) * 3)
    s.blit(pygame.transform.smoothscale(vignette, (W, H)), (0, 0), special_flags=pygame.BLEND_MULT)
    return s


def make_scanlines() -> pygame.Surface:
    s = pygame.Surface((W, H))
    s.fill(WHITE)
    for y in range(1, H, 2):
        pygame.draw.line(s, (196, 196, 210), (0, y), (W - 1, y))
    return s


class TitleTrails:
    """Two light trails chasing round the logo in opposite directions."""

    RECT = pygame.Rect(220, 70, 520, 140)
    LENGTH = 70

    def __init__(self) -> None:
        self.s = 0.0
        self.tails: dict[str, list] = {"p1": [], "p2": []}

    def _point(self, u: float) -> tuple[float, float]:
        r = self.RECT
        d = (u % 1.0) * 2 * (r.width + r.height)
        if d < r.width:
            return (r.left + d, r.top)
        d -= r.width
        if d < r.height:
            return (r.right, r.top + d)
        d -= r.height
        if d < r.width:
            return (r.right - d, r.bottom)
        return (r.left, r.bottom - (d - r.width))

    def update(self, dt: float) -> None:
        self.s = (self.s + dt * 0.12) % 1.0
        for player, u in (("p1", self.s), ("p2", 0.5 - self.s)):
            tail = self.tails[player]
            tail.append(self._point(u))
            del tail[:-self.LENGTH]

    def draw(self, surface: pygame.Surface) -> None:
        for player, tail in self.tails.items():
            color = config.PLAYER_COLORS[player]
            for width, k, hue in ((7, 0.35, color), (3, 1.0, lighten(color, 0.5))):
                if width > 3 and not config.GLOW:
                    continue
                for i in range(1, len(tail)):
                    pygame.draw.line(surface, scale(hue, k * i / len(tail)), tail[i - 1], tail[i], width)


# --- the renderer -----------------------------------------------------------------------


class Renderer:
    RULES = (
        "SPLIT INTO TWO MIRRORED COPIES WITH A",
        "YOU ONLY LOSE WHEN EVERY COPY CRASHES",
        "DRIVE THROUGH A GHOST TRAIL TO MEASURE IT",
        "GRAB H GATES TO CHARGE YOUR |ψ> METER",
    )

    def __init__(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self.font8, self.font16, self.font32, self.font48 = (load_font(n) for n in (8, 16, 32, 48))
        self.background = make_background()
        self.scanlines = make_scanlines() if config.SHOW_SCANLINES else None
        colors = config.PLAYER_COLORS
        self.solid_stamps = {p: make_stamps(c) for p, c in colors.items()}
        self.ghost_stamps = {p: make_stamps(c, ghost=True) for p, c in colors.items()}
        self.heads = {(p, False): make_glow(c, 15) for p, c in colors.items()}
        self.heads.update({(p, True): make_glow(c, 12, 0.75) for p, c in colors.items()})
        self.tokens = [make_token(self.font8, 0.45 + 0.55 * i / 7) for i in range(8)]
        self.logo = make_logo(load_font(72))
        self.board = self.background.copy()
        self.ghost = {p: pygame.Surface((W, H), pygame.SRCALPHA) for p in colors}
        self.fx = Fx()
        self.title_trails = TitleTrails()
        self.round: rules.RoundState | None = None
        self.t = 0.0
        self._cache: dict = {}

    # --- per frame ------------------------------------------------------------------------

    def draw(self, match: Match, events: list, dt: float) -> None:
        self.t += dt
        if match.round is not self.round:
            self._reset(match.round)
        self._apply(events)
        self.fx.update(dt)
        if match.state == TITLE:
            self._draw_title(dt)
        else:
            self._draw_arena(match)
            self._draw_hud(match)
            self._draw_banner(match)
        if self.scanlines is not None:
            self.surface.blit(self.scanlines, (0, 0), special_flags=pygame.BLEND_MULT)

    def _reset(self, round_state) -> None:
        self.board.blit(self.background, (0, 0))
        for layer in self.ghost.values():
            layer.fill((0, 0, 0, 0))
        self.fx.clear()
        self.round = round_state

    def _apply(self, events: list) -> None:
        for e in events:
            if isinstance(e, rules.Moved):
                if e.branch is None:
                    self._stamp(self.board, self.solid_stamps[e.player], e.frm, e.to, pygame.BLEND_MAX)
                elif (e.to[0] + e.to[1]) % 2 == 0:  # every other cell: a dashed ghost trail
                    self._stamp(self.ghost[e.player], self.ghost_stamps[e.player], e.frm, e.to,
                                pygame.BLEND_RGBA_MAX)
                continue
            color = config.PLAYER_COLORS.get(getattr(e, "player", None), WHITE)
            if isinstance(e, rules.Split):
                self.fx.ring(cell_px(e.pos), color)
            elif isinstance(e, rules.Collapse):
                self.ghost[e.player].fill((0, 0, 0, 0))
                path = e.solidified
                for a, b in zip(path, path[1:]):
                    self._stamp(self.board, self.solid_stamps[e.player], a, b, pygame.BLEND_MAX)
                self.fx.dissolve([cell_px(c) for c in e.dissolved], color)
                self.fx.ring(cell_px(e.at), lighten(color, 0.5))
            elif isinstance(e, rules.Measured):
                self.fx.ring(cell_px(e.pos), WHITE, life=0.6)
                self.fx.burst(cell_px(e.pos), WHITE, count=16, speed=90)
            elif isinstance(e, rules.Crash):
                self.fx.burst(cell_px(e.pos), lighten(color, 0.3))
                self.fx.kick(5)
            elif isinstance(e, rules.PickedUp):
                self.fx.burst(cell_px(e.pos), config.COLOR_PICKUP, count=14, speed=80, life=0.35)

    @staticmethod
    def _stamp(target: pygame.Surface, stamps: dict, a, b, flags: int) -> None:
        (ax, ay), (bx, by) = cell_px(a), cell_px(b)
        if abs(ax - bx) + abs(ay - by) != CELL:  # only ever neighbouring cells
            return
        target.blit(stamps[ay == by], (min(ax, bx) - GLOW_R, min(ay, by) - GLOW_R), special_flags=flags)

    # --- the arena --------------------------------------------------------------------------

    def _draw_arena(self, match: Match) -> None:
        s = self.surface
        ox, oy = self.fx.offset()
        if ox or oy:
            s.fill(config.COLOR_BACKGROUND)
        s.blit(self.board, (ox, oy))
        rs = self.round
        if rs is None:
            return
        for i, (p, pl) in enumerate(rs.players.items()):
            if pl.is_split:
                layer = self.ghost[p]
                layer.set_alpha(round(205 + 50 * math.sin(self.t * 23 + i * 2.1)))
                s.blit(layer, (ox, oy))
        token = self.tokens[int((0.5 + 0.5 * math.sin(self.t * 6)) * 7.999)]
        half = token.get_width() // 2
        for c in rs.pickups:
            x, y = cell_px(c)
            s.blit(token, (x - half + ox, y - half + oy), special_flags=pygame.BLEND_ADD)
        frac = match.tick_fraction if match.state == ROUND else 1.0
        for p, pl in rs.players.items():
            if not pl.alive:
                continue
            for bike in pl.bikes:
                (px, py), (qx, qy) = cell_px(bike.prev or bike.pos), cell_px(bike.pos)
                sprite = self.heads[(p, bike.branch is not None)]
                r = sprite.get_width() // 2
                x, y = round(px + (qx - px) * frac), round(py + (qy - py) * frac)
                s.blit(sprite, (x - r + ox, y - r + oy), special_flags=pygame.BLEND_ADD)
        self.fx.draw(s)

    def _draw_hud(self, match: Match) -> None:
        s = self.surface
        s.fill(config.COLOR_HUD, (0, 0, W, HUD))
        pygame.draw.line(s, scale(config.COLOR_WALL, 0.6), (0, HUD - 1), (W - 1, HUD - 1))
        rs = self.round
        bar_w, bar_h, y = 220, 10, 13
        for p, color in config.PLAYER_COLORS.items():
            pl = rs.players[p] if rs else None
            meter = pl.meter if pl else 0.0
            left = p == "p1"
            label = self._plain(p.upper(), self.font16, color)
            s.blit(label, (12, 10) if left else (W - 12 - label.get_width(), 10))
            bar_x = 52 if left else W - 52 - bar_w
            rect = pygame.Rect(bar_x, y, bar_w, bar_h)
            s.fill((14, 18, 34), rect)
            fill_w = round(bar_w * meter / config.METER_MAX)
            fill = scale(color, 0.65 + 0.35 * math.sin(self.t * 20)) if pl and pl.is_split else color
            if fill_w:
                s.fill(fill, (bar_x if left else bar_x + bar_w - fill_w, y, fill_w, bar_h))
            mid = bar_x + bar_w // 2
            pygame.draw.line(s, (90, 96, 130), (mid, y - 2), (mid, y + bar_h + 1))
            ready = pl is not None and not pl.is_split and meter >= config.SPLIT_MIN_METER
            border = lighten(color, 0.5) if ready and int(self.t * 4) % 2 == 0 else scale(color, 0.5)
            pygame.draw.rect(s, border, rect.inflate(4, 4), 1)
            ket = self._plain("|ψ>", self.font8, scale(color, 0.85))
            s.blit(ket, (bar_x + bar_w + 10, y + 1) if left else (bar_x - 10 - ket.get_width(), y + 1))
            for i in range(config.ROUNDS_TO_WIN):
                x = W // 2 - 20 - i * 16 if left else W // 2 + 8 + i * 16
                pip = pygame.Rect(x, 12, 12, 12)
                if i < match.scores[p]:
                    s.fill(color, pip)
                else:
                    pygame.draw.rect(s, scale(color, 0.45), pip, 1)

    def _draw_banner(self, match: Match) -> None:
        state = match.state
        if state == COUNTDOWN:
            self._center(self._glow(str(max(1, 3 - int(match.t))), self.font48, WHITE), H // 2)
        elif state == ROUND and match.round_time < 0.7:
            self._center(self._glow("GO!", self.font48, WHITE), H // 2)
        elif state == ROUND_RESULT:
            winner = match.last_winner
            if winner:
                self._center(self._glow(f"{winner.upper()} TAKES THE ROUND", self.font32,
                                        config.PLAYER_COLORS[winner]), H // 2)
            else:
                self._center(self._glow("DRAW - REPLAY", self.font32, WHITE), H // 2)
        elif state == MATCH_RESULT:
            winner = match.match_winner or "p1"
            self._center(self._glow(f"{winner.upper()} WINS", self.font48, config.PLAYER_COLORS[winner]),
                         H // 2 - 40)
            score = f"{match.scores['p1']} - {match.scores['p2']}"
            self._center(self._glow(score, self.font32, WHITE), H // 2 + 24)
            if match.t >= config.MATCH_RESULT_LOCK:
                self._center(self._plain("A / START: REMATCH      B: TITLE", self.font16, config.COLOR_TEXT),
                             H // 2 + 88, add=False)

    # --- the title ------------------------------------------------------------------------

    def _draw_title(self, dt: float) -> None:
        s = self.surface
        s.blit(self.background, (0, 0))
        s.fill(config.COLOR_BACKGROUND, (0, 0, W, HUD))
        self.title_trails.update(dt)
        self.title_trails.draw(s)
        self._center(self.logo, 140)
        y = 262
        for line in self.RULES:
            self._center(self._plain(line, self.font16, config.COLOR_TEXT), y, add=False)
            y += 28
        if int(self.t * 2) % 2 == 0:
            self._center(self._glow("PRESS A OR START", self.font32, config.COLOR_FPS), 420)
        self._center(self._plain("STICK: STEER    A: SPLIT    START + SELECT: QUIT", self.font8, config.COLOR_DIM),
                     500, add=False)

    # --- text -------------------------------------------------------------------------------

    def _plain(self, text: str, font: pygame.font.Font, color) -> pygame.Surface:
        key = ("plain", text, id(font), color)
        if key not in self._cache:
            self._cache[key] = font.render(text, False, color)
        return self._cache[key]

    def _glow(self, text: str, font: pygame.font.Font, color) -> pygame.Surface:
        key = ("glow", text, id(font), color)
        if key not in self._cache:
            self._cache[key] = glow_text(font, text, color)
        return self._cache[key]

    def _center(self, img: pygame.Surface, cy: int, add: bool = True) -> None:
        pos = (W // 2 - img.get_width() // 2, cy - img.get_height() // 2)
        self.surface.blit(img, pos, special_flags=pygame.BLEND_ADD if add else 0)
