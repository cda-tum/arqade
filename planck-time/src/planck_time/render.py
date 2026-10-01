"""The 640x360 frame: one GBA-style handheld per player (two side by side
in versus, one in the middle solo), each with a true 240x160 screen that
the current microgame draws itself into, plus everything around it: hearts
and scores, the timer fuse, the intro card (the verb and its input icon),
the result stamp and caption, SPEED UP!, the title with its attract demo,
initials, high scores, the match result and the pause menu.

Static art (bezels, hearts, the tiled backdrop) is drawn once at start-up;
per frame it's blits, a few fills and cached text, which the Pi manages
easily alongside the microgames themselves.
"""

from __future__ import annotations

import math
import random

import pygame

from planck_time import config
from planck_time import palette as P
from planck_time import session as S
from planck_time.pixel import backdrop, blit_center, orb, outlined

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
SW, SH = config.SCREEN_W, config.SCREEN_H
BEZEL_W, BEZEL_H = 300, 200
KEY = (255, 0, 255)  # transparent in the bezels
PLAYER_NAMES = {"p1": "P1", "p2": "P2"}
INPUT_LABELS = {"stick": "STICK", "a": "PRESS A", "mash": "MASH A!", "stick+a": "STICK + A"}

HEART = (
    ".oo...oo.",
    "oXXo.oXXo",
    "oXhXoXXXo",
    "oXXXXXXXo",
    ".oXXXXXo.",
    "..oXXXo..",
    "...oXo...",
    "....o....",
)


def bitmap(rows, colors: dict, scale: int = 1) -> pygame.Surface:
    """A little pixel sprite from strings: each character a colour, '.' clear."""
    surf = pygame.Surface((len(rows[0]), len(rows)), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in colors:
                surf.set_at((x, y), colors[ch])
    return pygame.transform.scale_by(surf, scale) if scale != 1 else surf


def make_bezel(color) -> pygame.Surface:
    """A GBA-shaped handheld in a player's colour. Its edges are hard pixels, so
    the corners are a colour key rather than per-pixel alpha: much cheaper to
    blit every frame on the Pi."""
    b = pygame.Surface((BEZEL_W, BEZEL_H))
    b.fill(KEY)
    b.set_colorkey(KEY, pygame.RLEACCEL)
    body = b.get_rect()
    pygame.draw.rect(b, P.INK, body, border_radius=44)
    pygame.draw.rect(b, P.shade(color, 0.7), body.inflate(-4, -4), border_radius=42)
    top = body.inflate(-4, -10).move(0, -3)
    pygame.draw.rect(b, color, top, border_radius=40)
    pygame.draw.rect(b, P.lighten(color, 0.45), (40, 5, BEZEL_W - 80, 3))
    # the screen surround
    surround = pygame.Rect(0, 0, SW + 12, SH + 24)
    surround.topleft = (24, 12)
    pygame.draw.rect(b, P.INK, surround.inflate(2, 2), border_radius=8)
    pygame.draw.rect(b, P.NIGHT, surround, border_radius=7)
    pygame.draw.rect(b, P.SLATE, surround, 1, border_radius=7)
    # D-pad (left wing)
    cx, cy = 14, 96
    for rect in ((cx - 7, cy - 2, 15, 5), (cx - 2, cy - 7, 5, 15)):
        pygame.draw.rect(b, P.INK, pygame.Rect(rect).inflate(2, 2))
    for rect in ((cx - 6, cy - 1, 13, 3), (cx - 1, cy - 6, 3, 13)):
        b.fill(P.SLATE, rect)
    b.fill(P.MIST, (cx - 1, cy - 6, 3, 1))
    # start / select pills
    for y in (150, 160):
        pygame.draw.rect(b, P.INK, (7, y, 14, 5), border_radius=2)
        pygame.draw.rect(b, P.shade(color, 0.55), (8, y + 1, 12, 3), border_radius=2)
    # A and B (right wing)
    orb(b, (290, 90), 5, P.lighten(color, 0.3))
    orb(b, (282, 104), 5, P.lighten(color, 0.3))
    # speaker holes
    for i in range(3):
        for j in range(3):
            b.fill(P.shade(color, 0.5), (279 + i * 5, 146 + j * 5 + i, 2, 2))
    return b


def make_tiles(colors) -> pygame.Surface:
    """A 16 px bigger-than-the-frame checker, scrolled by blitting at an offset."""
    surf = pygame.Surface((W + 16, H + 16))
    backdrop(surf, colors, 0.0)
    return surf


def ease_out_back(k: float) -> float:
    k = max(0.0, min(1.0, k)) - 1.0
    return 1.0 + 2.70158 * k ** 3 + 1.70158 * k ** 2


class Renderer:
    def __init__(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self.t = 0.0
        self.screens = {p: pygame.Surface((SW, SH)) for p in S.PLAYERS}
        self.bezels = {p: make_bezel(config.PLAYER_COLORS[p]) for p in S.PLAYERS}
        self.tiles = make_tiles(((32, 24, 64), (40, 32, 80)))
        self.title_tiles = make_tiles(((64, 40, 120), (80, 48, 144)))
        heart = {"o": P.INK, "X": P.BAD, "h": P.lighten(P.BAD, 0.6)}
        self.heart = bitmap(HEART, heart, 2)
        self.heart_empty = bitmap(HEART, {"o": P.INK, "X": P.SLATE, "h": P.SLATE}, 2)
        self.dim = pygame.Surface((SW, SH), pygame.SRCALPHA)
        self.dim.fill((*P.INK, 150))
        self.intro_dim = pygame.Surface((SW, SH), pygame.SRCALPHA)
        self.intro_dim.fill((*P.INK, 200))
        self.frame_dim = pygame.Surface((W, H), pygame.SRCALPHA)
        self.frame_dim.fill((*P.INK, 170))
        self.shake = {p: 0.0 for p in S.PLAYERS}
        self.led = {p: 0.0 for p in S.PLAYERS}
        self.rng = random.Random(5)

    # --- the frame ------------------------------------------------------------------------

    def draw(self, s: S.Session, events: list, dt: float) -> None:
        self.t += dt
        for e in events:
            if e.kind == "fail" and e.player:
                self.shake[e.player] = 0.3
            elif e.kind == "win" and e.player:
                self.led[e.player] = 1.0
        for p in S.PLAYERS:
            self.shake[p] = max(0.0, self.shake[p] - dt)
            self.led[p] = max(0.0, self.led[p] - dt)

        state = s.state
        if state == S.TITLE:
            self._title(s)
        elif state == S.NAME_ENTRY:
            self._name_entry(s)
        elif state == S.HISCORES:
            self._hiscores(s)
        else:
            self._game(s)
            if state == S.GAME_OVER:
                self._game_over(s)
            elif state == S.MATCH_RESULT:
                self._match_result(s)
        if s.paused:
            self._pause_menu(s)

    def _scroll(self, tiles: pygame.Surface, speed: float = 8.0) -> None:
        off = int(self.t * speed) % 16
        self.surface.blit(tiles, (off - 16, off - 16))

    def _centers(self, s: S.Session) -> dict:
        if s.mode == 1:
            return {"p1": config.SOLO_CENTER}
        return dict(config.SCREEN_CENTERS)

    # --- playing ------------------------------------------------------------------------

    def _game(self, s: S.Session) -> None:
        self._scroll(self.tiles)
        surf = self.surface
        blit_center(surf, outlined("PLANCK TIME", 16, P.GOLD), (W // 2, 22))
        level = outlined(f"LEVEL {s.level + 1}", 8, P.WHITE, shadow=False)
        blit_center(surf, level, (W // 2, 42))
        for p, center in self._centers(s).items():
            self._handheld(s, p, center)
        if s.state == S.RESULT and s.game_cls is not None:
            self._caption(s.game_cls.CAPTION)
        elif s.state in (S.INTRO, S.PLAY):
            hint = outlined("START: PAUSE", 8, P.MIST, shadow=False)
            blit_center(surf, hint, (W // 2, H - 14))

    def _handheld(self, s: S.Session, p: str, center) -> None:
        surf = self.surface
        cx, cy = center
        dx = dy = 0
        if self.shake[p] > 0:
            dx, dy = self.rng.randint(-3, 3), self.rng.randint(-2, 2)
        bx, by = cx - BEZEL_W // 2 + dx, cy - BEZEL_H // 2 + dy
        self._hud(s, p, cx, by - 14)
        surf.blit(self.bezels[p], (bx, by))
        # the power LED blinks green after a success
        lit = self.led[p] > 0 and int(self.led[p] * 10) % 2 == 0
        pygame.draw.circle(surf, P.INK, (bx + 14, by + 34), 3)
        pygame.draw.circle(surf, P.GOOD if lit else P.shade(P.BAD, 0.8), (bx + 14, by + 34), 2)
        screen = self.screens[p]
        self._screen(s, p, screen)
        surf.blit(screen, (bx + 30, by + 18))
        self._fuse(s, bx + 30, by + 18 + SH + 6)

    def _hud(self, s: S.Session, p: str, cx: int, y: int) -> None:
        """Above a handheld: the player tag, hearts and score."""
        surf = self.surface
        color = config.PLAYER_COLORS[p]
        left = cx - BEZEL_W // 2 + 12
        tag = outlined(PLAYER_NAMES[p], 8, color) if s.mode == 2 else None
        x = left
        if tag:
            surf.blit(tag, (x, y - 5))
            x += tag.get_width() + 6
        for i in range(config.LIVES):
            surf.blit(self.heart if i < s.lives[p] else self.heart_empty, (x + i * 20, y - 8))
        score = outlined(f"{s.scores[p]:>3}", 16, P.WHITE)
        surf.blit(score, (cx + BEZEL_W // 2 - 12 - score.get_width(), y - 8))

    def _fuse(self, s: S.Session, x: int, y: int) -> None:
        """The timer: a fuse burning down from right to left, with a spark."""
        surf = self.surface
        k = s.time_left
        surf.fill(P.INK, (x - 1, y - 1, SW + 2, 7))
        w = round(SW * k)
        if w > 0:
            color = P.GOLD if k > 0.5 else P.ORANGE if k > 0.25 else P.BAD
            if s.state == S.PLAY and k <= 0.25 and int(self.t * 8) % 2:
                color = P.WHITE
            surf.fill(color, (x, y, w, 5))
            surf.fill(P.lighten(color, 0.5), (x, y, w, 1))
        if s.state == S.PLAY and 0 < k < 1:
            sx = x + w
            for _ in range(4):
                a = self.rng.uniform(0, 2 * math.pi)
                r = self.rng.uniform(1, 5)
                surf.fill(self.rng.choice((P.GOLD, P.WHITE, P.ORANGE)),
                          (round(sx + math.cos(a) * r), round(y + 2 + math.sin(a) * r), 2, 2))

    def _screen(self, s: S.Session, p: str, screen: pygame.Surface) -> None:
        state = s.state
        game = s.games.get(p)
        if state == S.SPEED_UP:
            self._speed_up(s, screen)
            return
        if state == S.BOSS_CARD:
            self._boss_card(s, screen)
            return
        if game is None:
            screen.fill(P.NIGHT)
            return
        game.draw(screen)
        if state == S.INTRO:
            screen.blit(self.intro_dim, (0, 0))
            self._intro(s, screen, game)
        elif state == S.RESULT:
            self._stamp(s, p, screen, game)
        elif state in (S.GAME_OVER, S.MATCH_RESULT):
            screen.blit(self.dim, (0, 0))

    def _intro(self, s: S.Session, screen: pygame.Surface, game) -> None:
        """The verb drops in letter by letter, squashes and bounces; below it,
        the one input the microgame uses (animated the first time it comes up)."""
        verb = game.VERB
        size = 24 if len(verb) * 24 <= SW - 16 else 16
        x0 = SW // 2 - len(verb) * size // 2
        for i, ch in enumerate(verb):
            lt = s.t - i * 0.05
            if lt < 0:
                continue
            img = outlined(ch, size, P.GOLD)
            y = 52 - 36 * max(0.0, 1 - lt / 0.18) ** 2
            if 0.18 <= lt < 0.3:  # squash on landing
                img = pygame.transform.scale(img, (round(img.get_width() * 1.2), round(img.get_height() * 0.75)))
                y += 4
            elif lt >= 0.3:
                y -= 3 * abs(math.sin(s.t * 5 + i * 0.7))
            screen.blit(img, (x0 + i * size + size // 2 - img.get_width() // 2, round(y) - img.get_height() // 2))
        if game.BOSS:
            tag = outlined("BOSS", 8, P.WHITE)
            box = tag.get_rect(center=(SW // 2, 18)).inflate(10, 4)
            pygame.draw.rect(screen, P.INK, box.inflate(2, 2), border_radius=3)
            pygame.draw.rect(screen, P.BAD, box, border_radius=3)
            blit_center(screen, tag, box.center)
        panel = pygame.Rect(0, 0, 112, 66)
        panel.midtop = (SW // 2, 88)
        pygame.draw.rect(screen, P.INK, panel.inflate(4, 4), border_radius=8)
        pygame.draw.rect(screen, P.NIGHT, panel, border_radius=7)
        pygame.draw.rect(screen, P.GOLD if s.first_time else P.SLATE, panel, 1, border_radius=7)
        self._input_icon(screen, game.INPUT, (SW // 2, panel.y + 24), s.t, s.first_time)
        label = outlined(INPUT_LABELS[game.INPUT], 8, P.WHITE)
        blit_center(screen, label, (SW // 2, panel.bottom - 10))

    def _input_icon(self, screen, kind: str, center, t: float, demo: bool) -> None:
        cx, cy = center
        if kind == "stick+a":
            self._stick_icon(screen, (cx - 22, cy), t, demo)
            self._a_icon(screen, (cx + 22, cy + 4), t, demo, rate=1.6)
        elif kind == "stick":
            self._stick_icon(screen, center, t, demo)
        else:
            self._a_icon(screen, (cx, cy + 4), t, demo, rate=8.0 if kind == "mash" else 2.0)

    def _stick_icon(self, screen, center, t: float, demo: bool) -> None:
        cx, cy = center
        base = pygame.Rect(0, 0, 30, 10)
        base.center = (cx, cy + 14)
        pygame.draw.ellipse(screen, P.INK, base.inflate(2, 2))
        pygame.draw.ellipse(screen, P.SLATE, base)
        tilt = math.sin(t * 7) * 0.55 if demo else 0.25
        top = (cx + math.sin(tilt) * 18, cy + 14 - math.cos(tilt) * 18)
        pygame.draw.line(screen, P.INK, (cx, cy + 14), top, 5)
        pygame.draw.line(screen, P.MIST, (cx, cy + 14), top, 3)
        orb(screen, top, 7, P.BAD)
        if demo:  # little motion marks either side
            for side in (-1, 1):
                if (math.sin(t * 7) > 0.3) == (side > 0) or abs(math.sin(t * 7)) < 0.3:
                    continue
                x = cx + side * 24
                for k in range(3):
                    screen.fill(P.WHITE, (x + side * k * 3, cy - 2 + k * 2, 2, 2))

    def _a_icon(self, screen, center, t: float, demo: bool, rate: float) -> None:
        cx, cy = center
        phase = (t * rate) % 1.0
        down = demo and phase < 0.35
        pygame.draw.ellipse(screen, P.INK, (cx - 13, cy - 4, 26, 16))
        pygame.draw.ellipse(screen, P.SLATE, (cx - 12, cy - 3, 24, 14))
        y = cy + (2 if down else -2)
        orb(screen, (cx, y), 10, P.BAD)
        blit_center(screen, outlined("A", 8, P.WHITE, shadow=False), (cx + 1, y))
        if demo and phase < 0.5:
            r = round(12 + 16 * phase)
            pygame.draw.circle(screen, P.WHITE, (cx, y), r, 1)

    def _stamp(self, s: S.Session, p: str, screen, game) -> None:
        """NICE! or OOPS!, popping in, and the points just scored."""
        k = ease_out_back(s.t / 0.25)
        text, color = ("NICE!", P.GOOD) if game.result else ("OOPS!", P.BAD)
        img = outlined(text, 24, color)
        scale = max(0.1, 0.3 + 0.7 * k)
        img = pygame.transform.scale(img, (round(img.get_width() * scale), round(img.get_height() * scale)))
        band = pygame.Surface((SW, 40), pygame.SRCALPHA)
        band.fill((*P.INK, 170))
        screen.blit(band, (0, SH // 2 - 26))
        blit_center(screen, img, (SW // 2, SH // 2 - 6))
        gained = s.gained[p]
        if gained:
            bonus = " FIRST!" if s.first == p else ""
            pts = outlined(f"+{gained}{bonus}", 8, P.GOLD)
            blit_center(screen, pts, (SW // 2, SH // 2 + 20 - min(6, s.t * 20)))

    def _speed_up(self, s: S.Session, screen) -> None:
        backdrop(screen, P.BACKDROPS[s.level % len(P.BACKDROPS)], self.t, speed=60)
        for row, word in enumerate(("SPEED", "UP!")):
            wob = math.sin(self.t * 12 + row) * 3
            img = outlined(word, 24, P.GOLD if row else P.WHITE)
            blit_center(screen, img, (SW // 2 + wob, 54 + row * 34))
        lv = outlined(f"LEVEL {s.level + 1}", 8, P.WHITE)
        blit_center(screen, lv, (SW // 2, 128))
        off = int(self.t * 90) % 24
        for x in range(-24 + off, SW, 24):
            screen.blit(outlined(">", 8, P.CREAM, shadow=False), (x, 146))

    def _boss_card(self, s: S.Session, screen) -> None:
        """WARNING-style: red hazard stripes scrolling, BOSS! shaking in the middle."""
        flash = int(self.t * 6) % 2
        screen.fill(P.shade(P.BAD, 0.35) if flash else P.INK)
        off = int(self.t * 40) % 16
        for y0 in (14, SH - 26):
            screen.fill(P.GOLD, (0, y0, SW, 12))
            for x in range(-16 + off, SW + 16, 16):
                pygame.draw.polygon(screen, P.INK, ((x, y0), (x + 8, y0), (x + 2, y0 + 12), (x - 6, y0 + 12)))
        shake = self.rng.randint(-2, 2) if s.t < 1.2 else 0
        blit_center(screen, outlined("WARNING", 8, P.GOLD if flash else P.WHITE), (SW // 2, 50))
        blit_center(screen, outlined("BOSS!", 32, P.BAD), (SW // 2 + shake, 82 + shake))
        blit_center(screen, outlined("WORTH 3 POINTS", 8, P.WHITE), (SW // 2, 112))

    def _caption(self, text: str) -> None:
        surf = self.surface
        img = outlined(text, 8, P.WHITE)
        ribbon = pygame.Rect(0, 0, img.get_width() + 28, 22)
        ribbon.center = (W // 2, H - 22)
        pygame.draw.rect(surf, P.INK, ribbon.inflate(2, 2), border_radius=6)
        pygame.draw.rect(surf, P.NIGHT, ribbon, border_radius=5)
        pygame.draw.rect(surf, P.GOLD, ribbon, 1, border_radius=5)
        blit_center(surf, img, ribbon.center)

    # --- end of a run ------------------------------------------------------------------------

    def _banner(self, lines: list, y: int = H // 2) -> None:
        surf = self.surface
        height = sum(img.get_height() + 6 for img in lines) + 18
        width = max(img.get_width() for img in lines) + 48
        box = pygame.Rect(0, 0, width, height)
        box.center = (W // 2, y)
        pygame.draw.rect(surf, P.INK, box.inflate(4, 4), border_radius=10)
        pygame.draw.rect(surf, P.NIGHT, box, border_radius=8)
        pygame.draw.rect(surf, P.GOLD, box, 2, border_radius=8)
        yy = box.y + 12
        for img in lines:
            surf.blit(img, (W // 2 - img.get_width() // 2, yy))
            yy += img.get_height() + 6

    def _game_over(self, s: S.Session) -> None:
        self._banner([outlined("GAME OVER", 32, P.BAD), outlined(f"SCORE {s.score}", 16, P.WHITE)])

    def _match_result(self, s: S.Session) -> None:
        if s.winner:
            head = outlined(f"{PLAYER_NAMES[s.winner]} WINS!", 32, config.PLAYER_COLORS[s.winner])
        else:
            head = outlined("DRAW!", 32, P.GOLD)
        score = outlined(f"{s.scores['p1']}  -  {s.scores['p2']}", 16, P.WHITE)
        lines = [head, score]
        if s.t >= config.MATCH_RESULT_LOCK:
            lines.append(outlined("A: REMATCH     B: TITLE", 8, P.MIST, shadow=False))
        self._banner(lines)

    def _pause_menu(self, s: S.Session) -> None:
        surf = self.surface
        surf.blit(self.frame_dim, (0, 0))
        lines = [outlined("PAUSED", 24, P.GOLD)]
        for i, item in enumerate(S.PAUSE_ITEMS):
            on = i == s.pause_index
            lines.append(outlined(f"> {item} <" if on else item, 16 if on else 8, P.GOLD if on else P.WHITE))
        lines.append(outlined("A: PICK   START / B: RESUME", 8, P.MIST, shadow=False))
        self._banner(lines)

    def _name_entry(self, s: S.Session) -> None:
        surf = self.surface
        self._scroll(self.title_tiles)
        entry = s.name_entry
        blit_center(surf, outlined("NEW HIGH SCORE!", 24, P.GOLD), (W // 2, 54))
        blit_center(surf, outlined(f"{s.score}", 32, P.WHITE), (W // 2, 100))
        blit_center(surf, outlined("ENTER YOUR INITIALS", 8, P.WHITE), (W // 2, 140))
        if entry is not None:
            for i, letter in enumerate(entry.name):
                box = pygame.Rect(W // 2 - 76 + i * 56, 164, 40, 48)
                active = i == entry.pos
                pygame.draw.rect(surf, P.INK, box.inflate(4, 4), border_radius=7)
                pygame.draw.rect(surf, P.NIGHT, box, border_radius=6)
                pygame.draw.rect(surf, P.GOLD if active else P.SLATE, box, 2, border_radius=6)
                blit_center(surf, outlined(letter, 32, P.GOLD if active else P.WHITE), box.center)
                if active and int(self.t * 4) % 2 == 0:
                    blit_center(surf, outlined("^", 8, P.WHITE, shadow=False), (box.centerx, box.y - 10))
                    blit_center(surf, outlined("v", 8, P.WHITE, shadow=False), (box.centerx, box.bottom + 10))
        foot = outlined("STICK: LETTER    A: NEXT    B: BACK", 8, P.WHITE)
        surf.fill(P.INK, (0, 300, W, 24))
        blit_center(surf, foot, (W // 2, 312))

    def _hiscores(self, s: S.Session) -> None:
        surf = self.surface
        self._scroll(self.title_tiles)
        blit_center(surf, outlined("HIGH SCORES", 24, P.GOLD), (W // 2, 32))
        box = pygame.Rect(W // 2 - 150, 56, 300, 226)
        pygame.draw.rect(surf, P.INK, box.inflate(4, 4), border_radius=8)
        pygame.draw.rect(surf, P.NIGHT, box, border_radius=7)
        pygame.draw.rect(surf, P.SLATE, box, 1, border_radius=7)
        entries = s.hiscores.entries
        if not entries:
            blit_center(surf, outlined("NO SCORES YET - BE THE FIRST!", 8, P.WHITE), box.center)
        for i, e in enumerate(entries):
            y = box.y + 14 + i * 21
            fresh = i == s.new_rank
            if fresh and int(self.t * 4) % 2:
                continue
            col = P.GOLD if fresh else P.WHITE
            for x, text in ((box.x + 20, f"{i + 1:>2}."), (box.x + 70, e.name),
                            (box.x + 140, f"{e.score:>5}"), (box.x + 226, f"LV{e.level + 1}")):
                surf.blit(outlined(text, 8, col, shadow=False), (x, y))

    # --- title ----------------------------------------------------------------------------

    def _logo(self, center, size: int) -> None:
        """PLANCK TIME, each letter in a gate colour, riding a wave."""
        surf = self.surface
        cx, cy = center
        text = "PLANCK TIME"
        colors = (P.GATE["X"], P.GATE["H"], P.GOOD, P.GATE["Z"], P.GATE["Y"], P.PINK)
        x0 = cx - len(text) * size // 2
        for i, ch in enumerate(text):
            if ch == " ":
                continue
            y = cy - 4 * math.sin(self.t * 4 + i * 0.6)
            blit_center(surf, outlined(ch, size, colors[i % len(colors)]), (x0 + i * size + size // 2, y))
        # a stopwatch, its hand racing round
        r = size // 2 + 2
        wx, wy = x0 + len(text) * size + r + 10, cy
        pygame.draw.circle(surf, P.INK, (wx, wy), r + 2)
        pygame.draw.circle(surf, P.CREAM, (wx, wy), r)
        surf.fill(P.INK, (wx - 3, wy - r - 6, 6, 5))
        a = self.t * 6
        pygame.draw.line(surf, P.BAD, (wx, wy), (wx + math.sin(a) * (r - 3), wy - math.cos(a) * (r - 3)), 2)

    def _title(self, s: S.Session) -> None:
        surf = self.surface
        self._scroll(self.title_tiles)
        blink = int(self.t * 2) % 2 == 0
        if s.attract:
            self._logo((W // 2 - 14, 34), 24)
            for p, center in config.SCREEN_CENTERS.items():
                bx, by = center[0] - BEZEL_W // 2, center[1] - BEZEL_H // 2
                surf.blit(self.bezels[p], (bx, by))
                screen = self.screens[p]
                s.attract[p].draw(screen)
                surf.blit(screen, (bx + 30, by + 18))
            if blink:
                blit_center(surf, outlined("PRESS START", 16, P.WHITE), (W // 2, H - 26))
            return
        self._logo((W // 2 - 18, 92), 32)
        blit_center(surf, outlined("A QUANTUM MICROGAME PARTY", 8, P.CREAM), (W // 2, 132))
        for i, (n, label) in enumerate(((1, "1 PLAYER"), (2, "2 PLAYERS"))):
            y = 190 + i * 30
            on = s.mode == n
            color = P.GOLD if on else P.WHITE
            img = outlined(label, 16, color)
            blit_center(surf, img, (W // 2, y))
            if on:
                bob = 3 * math.sin(self.t * 8)
                blit_center(surf, outlined(">", 16, P.GOLD), (W // 2 - img.get_width() // 2 - 20 + bob, y))
                blit_center(surf, outlined("<", 16, P.GOLD), (W // 2 + img.get_width() // 2 + 20 - bob, y))
        if blink:
            blit_center(surf, outlined("PRESS START", 8, P.WHITE), (W // 2, 282))
        best = s.hiscores.entries[0] if s.hiscores.entries else None
        if best:
            hi = outlined(f"HI-SCORE  {best.name}  {best.score}", 8, P.MIST, shadow=False)
            blit_center(surf, hi, (W // 2, 330))
