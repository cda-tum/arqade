"""The 2D layer over the 3D picture, drawn with pygame on a transparent
960x540 surface: the HUD along the top (everyone's seconds in the lead),
popups, the marker over the leader, the warning when a person's racer is
about to fall off the screen, the countdown, the result, the title, the
racer select's frames and text (its racers are drawn in 3D underneath, in
the boxes select_layout gives), the HOW TO PLAY card (its demo race is
drawn in 3D underneath, in tutorial_box) and the pause menu.
"""

from __future__ import annotations

import math

import pygame

from qircuit import config, racers, tutorial
from qircuit.fonts import load_font
from qircuit.match import (COUNTDOWN, MATCH_END, MENU_ROWS, PAUSE_ITEMS, RACE, SELECT, SELECT_COLS, TITLE, TUTORIAL,
                           Match)

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
INK = config.COLOR_INK
WHITE = (255, 255, 255)
GOLD_TEXT = (255, 220, 80)
SUFFIX = {1: "ST", 2: "ND", 3: "RD"}
OFF = (34, 38, 64)  # an unused button, an empty bar
# The cabinet's 2x3 buttons as printed, and what each does in a race (None: unused)
CLUSTER = (("L", None), ("X", "FASTER"), ("R", None), ("Y", "LEFT"), ("B", "SLOWER"), ("A", "RIGHT"))


def ordinal(i: int) -> str:
    """Place i (from 0) as 1ST, 2ND, 3RD, 4TH, ..."""
    return f"{i + 1}{SUFFIX.get(i + 1, 'TH')}"


def shade(color, k: float):
    return tuple(max(0, min(255, int(c * k))) for c in color)


def select_layout(n: int) -> tuple[list[pygame.Rect], list[pygame.Rect]]:
    """The racer select's boxes: one per roster racer (5 x 2), and one per
    person along the bottom. The renderer draws racers into them."""
    tw, th, gap = 168, 142, 8
    gx = W // 2 - (SELECT_COLS * tw + (SELECT_COLS - 1) * gap) // 2
    tiles = [pygame.Rect(gx + (i % SELECT_COLS) * (tw + gap), 36 + (i // SELECT_COLS) * (th + gap), tw, th)
             for i in range(len(racers.ROSTER))]
    pw = min(460, (W - 16 - 8 * (n - 1)) // n)
    px0 = W // 2 - (n * pw + (n - 1) * 8) // 2
    panels = [pygame.Rect(px0 + j * (pw + 8), 340, pw, 182) for j in range(n)]
    return tiles, panels


def tutorial_box() -> pygame.Rect:
    """Where the HOW TO PLAY card's demo race is drawn (16:9, as tutorial.ASPECT)."""
    return pygame.Rect(24, 62, 608, 342)


def panel_model_box(rect: pygame.Rect) -> pygame.Rect:
    """Where a person's racer turns, inside their panel."""
    if rect.w > 300:
        return pygame.Rect(rect.x + 8, rect.y + 8, 164, rect.h - 16)
    return pygame.Rect(rect.x + 8, rect.y + 8, rect.w - 16, 90)


class Hud:
    def __init__(self) -> None:
        self.font8 = load_font(8)
        self.font16 = load_font(16)
        self.font32 = load_font(32)
        self.font48 = load_font(48)
        self._cache: dict = {}
        self.time = 0.0

    def text(self, text: str, font: pygame.font.Font, color, outline: bool = True) -> pygame.Surface:
        key = (text, id(font), color, outline)
        if key not in self._cache:
            img = font.render(text, False, color)
            if outline:
                s = pygame.Surface((img.get_width() + 2, img.get_height() + 2), pygame.SRCALPHA)
                ink = font.render(text, False, INK)
                for dx, dy in ((0, 1), (1, 0), (2, 1), (1, 2), (2, 2)):
                    s.blit(ink, (dx, dy))
                s.blit(img, (1, 1))
                img = s
            if len(self._cache) > 600:
                self._cache.clear()
            self._cache[key] = img
        return self._cache[key]

    def center(self, s: pygame.Surface, img: pygame.Surface, y: int, cx: int = W // 2) -> None:
        s.blit(img, img.get_rect(midtop=(cx, y)))

    def panel(self, s: pygame.Surface, w: int, h: int, cy: int = H // 2, border=config.COLOR_EDGE) -> pygame.Rect:
        r = pygame.Rect(0, 0, w, h)
        r.center = (W // 2, cy)
        s.fill(config.COLOR_PANEL + (235,), r)
        pygame.draw.rect(s, border, r, 2)
        return r

    # --- the whole layer ----------------------------------------------------------------------

    def draw(self, s: pygame.Surface, match: Match, popups: list, warnings: list, dt: float,
             lead_mark: tuple | None = None) -> None:
        self.time += dt
        s.fill((0, 0, 0, 0))
        if match.state == TITLE:
            self.title(s, match)
            return
        if match.state == SELECT:
            self.select(s, match)
            return
        if match.state == TUTORIAL:
            self.tutorial(s, match, popups, lead_mark)
            return
        for x, y, text, color, age in popups:
            img = self.text(text, self.font8, color)
            r = img.get_rect(center=(round(x), round(y - age * 18)))
            r.clamp_ip(s.get_rect())
            s.blit(img, r)
        if lead_mark is not None:
            self.lead_mark(s, *lead_mark)
        for x, y, color, label in warnings:
            self.warning(s, x, y, color, label)
        self.band(s, match)
        if match.state == COUNTDOWN:
            n = max(1, math.ceil(config.COUNTDOWN - match.t))
            self.center(s, self.text(str(n), self.font48, WHITE), H // 2 - 70)
        elif match.state == RACE and match.t < 0.8:
            self.center(s, self.text("GO!", self.font48, GOLD_TEXT), H // 2 - 70)
        elif match.state == MATCH_END:
            self.match_end(s, match)
        if match.paused:
            self.pause(s, match)

    def warning(self, s: pygame.Surface, x: float, y: float, color, label: str) -> None:
        """A person about to fall off the screen: a flashing arrow at the edge."""
        if int(self.time * 8) % 2:
            return
        x = max(20, min(W - 20, x))
        y = max(config.HUD_BAND + 20, min(H - 20, y))
        pygame.draw.polygon(s, color, [(x, y + 14), (x - 12, y - 6), (x + 12, y - 6)])
        pygame.draw.polygon(s, WHITE, [(x, y + 14), (x - 12, y - 6), (x + 12, y - 6)], 2)
        img = self.text(label, self.font8, color)
        s.blit(img, img.get_rect(midbottom=(x, y - 8)))

    def lead_mark(self, s: pygame.Surface, x: float, y: float, color, label: str) -> None:
        """Over the leader's racer: who it is, under a gold arrow."""
        x = max(20, min(W - 20, x))
        y = max(config.HUD_BAND + 24, min(H - 6, y))
        pygame.draw.polygon(s, GOLD_TEXT, [(x, y), (x - 6, y - 8), (x + 6, y - 8)])
        img = self.text(label, self.font8, color)
        s.blit(img, img.get_rect(midbottom=(x, y - 10)))

    def band(self, s: pygame.Surface, match: Match) -> None:
        """A panel per person along the top, P1 and P3 on the left and P2 and
        P4 on the right: seconds in the lead, a bar to the target, and where
        they are. Between them the target and everyone's seconds."""
        race = match.race
        if race is None:
            return
        holder = match.pack.holder
        blink = int(self.time * 4) % 2 == 0
        s.fill((6, 7, 16, 225), (0, 0, W, config.HUD_BAND))
        pygame.draw.line(s, (40, 46, 84), (0, config.HUD_BAND), (W, config.HUD_BAND))
        few = len(match.people) <= 2
        pw, ph = (200 if few else 150), config.HUD_BAND - 10
        slots = {"p1": 6, "p3": 6 + pw + 6, "p4": W - 12 - 2 * pw, "p2": W - 6 - pw}
        standings = race.standings()
        for player in match.people:
            x, y = slots[player], 5
            color = config.color_of(player)
            rect = pygame.Rect(x, y, pw, ph)
            s.fill(config.COLOR_PANEL, rect)
            pygame.draw.rect(s, GOLD_TEXT if player == holder else shade(color, 0.7), rect, 1)
            s.fill(color, (x + 1, y + 1, 4, ph - 2))
            name = racers.BY_KEY[match.racer_of[player]].name if few else ""
            s.blit(self.text(f"{config.label_of(player)} {name}", self.font8, color, False), (x + 10, y + 5))
            secs = self.text(f"{int(match.lead_time.get(player, 0.0))}", self.font16, WHITE, False)
            s.blit(secs, (x + pw - secs.get_width() - 8, y + 7))
            if player == holder:
                status, tone = ("LEAD" if blink else ""), GOLD_TEXT
            else:
                status, tone = ordinal(standings.index(player)), config.COLOR_DIM
            s.blit(self.text(status, self.font8, tone, False), (x + 10, y + 17))
            self.speedo(s, race, player, pygame.Rect(x + 48, y + 18, pw - 96, 6), color)
            share = min(1.0, match.lead_time.get(player, 0.0) / match.target)
            s.fill((34, 38, 64), (x + 10, y + ph - 6, pw - 20, 3))
            s.fill(color, (x + 10, y + ph - 6, round((pw - 20) * share), 3))
        self.center(s, self.text(f"FIRST TO {match.target} S IN FRONT", self.font8, config.COLOR_TEXT, False), 5)
        table = match.table()
        cw = 30
        x0 = W // 2 - len(table) * cw // 2
        for i, player in enumerate(table):
            x = x0 + i * cw
            r = pygame.Rect(x + 2, 18, cw - 4, 20)
            s.fill(config.color_of(player), r)
            if player == holder:
                pygame.draw.rect(s, GOLD_TEXT if blink else WHITE, r.inflate(4, 4), 2)
            elif player in match.people:
                pygame.draw.rect(s, WHITE, r.inflate(2, 2), 1)
            img = self.text(str(int(match.lead_time.get(player, 0.0))), self.font8, INK, False)
            s.blit(img, img.get_rect(center=r.center))

    def speedo(self, s: pygame.Surface, race, player: str, rect: pygame.Rect, color) -> None:
        """A person's speed as a bar (full: top speed), and a white tick where
        their cruise control is set: up and down move the tick, and the bar
        follows it."""
        b = race.front(player)
        stats = race.racers[player].stats
        s.fill(OFF, rect)
        s.fill(shade(color, 0.8), (rect.x, rect.y, round(rect.w * min(1.0, b.v / stats.max_speed)), rect.h))
        tick = rect.x + round((rect.w - 1) * min(1.0, race.cruise_speed(b, stats) / stats.max_speed))
        s.fill(WHITE, (tick - 1, rect.y - 2, 2, rect.h + 4))

    def match_end(self, s: pygame.Surface, match: Match) -> None:
        winner = match.winner
        r = self.panel(s, 460, 80 + 18 * len(match.players), border=config.color_of(winner))
        self.center(s, self.text(f"{config.label_of(winner)} WINS!", self.font16, config.color_of(winner)), r.y + 14)
        y = r.y + 48
        for i, player in enumerate(match.table()):
            key = match.racer_of[player]
            secs = f"{int(match.lead_time.get(player, 0.0))} S"
            line = f"{ordinal(i):<4} {config.label_of(player):<5} {racers.BY_KEY[key].name:<12} {secs:>5}"
            self.center(s, self.text(line, self.font8, config.color_of(player), False), y)
            y += 18
        if match.t >= config.RESULT_LOCK:
            self.center(s, self.text("A: REMATCH   B: TITLE", self.font8, config.COLOR_TEXT), r.bottom + 8)

    def pause(self, s: pygame.Surface, match: Match) -> None:
        s.fill((4, 5, 12, 150), (0, 0, W, H))
        r = self.panel(s, 300, 110)
        self.center(s, self.text("PAUSED", self.font16, WHITE), r.y + 14)
        for i, item in enumerate(PAUSE_ITEMS):
            chosen = i == match.pause_index
            text = f"> {item}" if chosen else f"  {item}"
            self.center(s, self.text(text, self.font8, GOLD_TEXT if chosen else config.COLOR_TEXT, False),
                        r.y + 50 + i * 20)

    # --- the menus ------------------------------------------------------------------------------

    def title(self, s: pygame.Surface, match: Match) -> None:
        r = self.panel(s, 480, 372)
        self.center(s, self.text("QIRCUIT", self.font48, WHITE), r.y + 24)
        self.center(s, self.text("SLOT RACING ON QUANTUM WIRES", self.font8, config.COLOR_DIM, False), r.y + 84)
        values = {
            "PLAYERS": "1 PLAYER" if match.humans == 1 else f"{match.humans} PLAYERS",
            "BOTS": "NO BOTS" if match.bots == 0 else ("1 BOT" if match.bots == 1 else f"{match.bots} BOTS"),
            "LEVEL": f"BOTS: {match.level}",
            "TRACK": match.track.name,
            "LEAD": f"FIRST TO {match.target} S IN FRONT",
            "QUIT": "QUIT",
        }
        y = r.y + 112
        for i, row in enumerate(MENU_ROWS):
            chosen = i == match.row
            idle = row == "LEVEL" and match.bots == 0
            color = GOLD_TEXT if chosen else (config.COLOR_DIM if idle else config.COLOR_TEXT)
            text = f"<  {values[row]}  >" if chosen and row != "QUIT" else values[row]
            if row == "QUIT":
                y += 6  # set apart from the race's settings
            font = self.font16 if chosen else self.font8
            self.center(s, self.text(text, font, color, False), y - (4 if chosen else 0))
            y += 24
        y += 6
        for line in ("LEAD THE PACK: EVERY SECOND IN FRONT COUNTS",
                     "OFF THE SCREEN: BACK IN AT THE BACK OF THE PACK",
                     "STICK UP / DOWN: FASTER / SLOWER, AND IT STAYS",
                     "LEFT / RIGHT: CHANGE WIRE",
                     "3-4 PLAYERS: P3 + P4 USE X Y B A"):
            self.center(s, self.text(line, self.font8, config.COLOR_DIM, False), y)
            y += 13
        if int(self.time * 2) % 2:
            self.center(s, self.text("PRESS START", self.font16, WHITE, False), r.bottom - 30)

    def select(self, s: pygame.Surface, match: Match) -> None:
        """Frames and words; the racers turn in 3D underneath, in the boxes."""
        self.center(s, self.text("CHOOSE YOUR RACER", self.font16, WHITE), 10)
        tiles, panels = select_layout(len(match.people))
        for i, (racer, rect) in enumerate(zip(racers.ROSTER, tiles)):
            pygame.draw.rect(s, (40, 46, 84), rect, 1)
            name = self.text(racer.name, self.font8, config.COLOR_TEXT, False)
            s.blit(name, name.get_rect(midbottom=(rect.centerx, rect.bottom - 4)))
            for j, p in enumerate(match.people):
                if match.picks.get(p) == i:
                    c = config.color_of(p)
                    pygame.draw.rect(s, c, rect.inflate(-2 - 6 * j, -2 - 6 * j), 3)
                    s.blit(self.text(config.label_of(p), self.font8, c), (rect.x + 5 + 26 * j, rect.y + 5))
        for j, (p, rect) in enumerate(zip(match.people, panels)):
            racer = racers.ROSTER[match.picks.get(p, 0)]
            color = config.color_of(p)
            wide = rect.w > 300
            pygame.draw.rect(s, color, rect, 2)
            tx = rect.x + 180 if wide else rect.x + 10
            ty = rect.y + 12 if wide else rect.y + 104
            head = self.text(f"{config.label_of(p)}  {racer.name}", self.font16 if wide else self.font8, color, False)
            s.blit(head, (tx, ty))
            s.blit(self.text(racer.game, self.font8, config.COLOR_DIM, False), (tx, ty + head.get_height() + 5))
            by = ty + (46 if wide else 26)
            for label, value in zip(racers.RATINGS, racer.ratings):
                s.blit(self.text(label if wide else label[:3], self.font8, config.COLOR_TEXT, False), (tx, by))
                cw = 18 if wide else 11
                for k in range(5):
                    cell = pygame.Rect(tx + (86 if wide else 32) + k * (cw + 3), by - 1, cw, 9)
                    s.fill(color if k < value else (34, 38, 64), cell)
                by += 15 if wide else 11
            locked = p in match.locked
            hint = ("READY!" if locked else "A: LOCK IN") if match.humans <= 2 else "START: GO"
            img = self.text(hint, self.font8, GOLD_TEXT if locked else config.COLOR_DIM, False)
            s.blit(img, img.get_rect(bottomright=(rect.right - 8, rect.bottom - 8)))
        self.center(s, self.text("STICK: CHOOSE   START: RACE   B: BACK", self.font8, config.COLOR_DIM, False), H - 13)

    # --- the HOW TO PLAY card -------------------------------------------------------------------

    def tutorial(self, s: pygame.Surface, match: Match, popups: list, lead_mark: tuple | None) -> None:
        """The goal, the demo race (in 3D underneath, in tutorial_box) with
        its seconds in front and a caption for what it shows, the controls
        with the cabinet's printed buttons, and who drives with which pad."""
        demo = match.tutorial
        pygame.draw.rect(s, config.COLOR_EDGE, (6, 6, W - 12, H - 12), 2)
        self.center(s, self.text("HOW TO PLAY", self.font32, WHITE), 16)
        box = tutorial_box()
        pygame.draw.rect(s, config.COLOR_EDGE, box.inflate(4, 4), 2)
        if demo is not None:
            self.tutorial_demo(s, box, demo, popups, lead_mark)

        x0, y = box.right + 24, box.y
        s.blit(self.text("GOAL", self.font16, GOLD_TEXT, False), (x0, y))
        y += 26
        for line in tutorial.goal_lines(match.target):
            s.blit(self.text(line, self.font8, config.COLOR_TEXT, False), (x0, y))
            y += 13
        y += 18
        s.blit(self.text("CONTROLS", self.font16, GOLD_TEXT, False), (x0, y))
        y += 28
        self.stick(s, x0 + 24, y + 22)
        for i, line in enumerate(tutorial.STICK_LINES):
            s.blit(self.text(line, self.font8, config.COLOR_TEXT, False), (x0 + 64, y + 4 + 15 * i))
        y += 62
        for i, (label, action) in enumerate(CLUSTER):
            c = (x0 + 12 + (i % 3) * 26, y + 12 + (i // 3) * 26)
            pygame.draw.circle(s, INK, c, 12)
            pygame.draw.circle(s, GOLD_TEXT if action else OFF, c, 11)
            img = self.text(label, self.font8, INK if action else config.COLOR_DIM, False)
            s.blit(img, img.get_rect(center=(c[0] + 1, c[1] + 1)))
        for i, line in enumerate(tutorial.BUTTON_LINES):
            s.blit(self.text(line, self.font8, config.COLOR_TEXT, False), (x0 + 88, y + 8 + 15 * i))
        y += 66
        img = self.text("START", self.font8, GOLD_TEXT, False)
        s.blit(img, (x0, y))
        s.blit(self.text(": PAUSE", self.font8, config.COLOR_TEXT, False), (x0 + img.get_width(), y))
        y += 22
        for line in tutorial.pad_lines(match.humans):
            x = x0
            for text, player in line:
                img = self.text(text, self.font8, config.color_of(player) if player else config.COLOR_DIM, False)
                s.blit(img, (x, y))
                x += img.get_width()
            y += 14
        if int(self.time * 2) % 2 == 0:
            self.center(s, self.text("PRESS ANY BUTTON TO START", self.font16, WHITE), H - 48)

    def tutorial_demo(self, s: pygame.Surface, box: pygame.Rect, demo, popups: list,
                      lead_mark: tuple | None) -> None:
        """Over the demo race: its popups, the marker over the leader, each
        racer's seconds in front as the HUD's chips, and the caption."""
        for x, y, text, color, age in popups:
            img = self.text(text, self.font8, color)
            r = img.get_rect(center=(round(x), round(y - age * 18)))
            if box.contains(r):  # not one left behind when the demo starts over
                s.blit(img, r)
        if lead_mark is not None:
            self.lead_mark(s, *lead_mark)
        x = box.x + 8
        blink = int(self.time * 4) % 2 == 0
        for player in tutorial.PLAYERS:
            color = config.color_of(player)
            label = self.text(config.label_of(player), self.font8, color)
            s.blit(label, (x, box.y + 14))
            r = pygame.Rect(x + label.get_width() + 4, box.y + 8, 26, 20)
            s.fill(color, r)
            if player == demo.pack.holder:
                pygame.draw.rect(s, GOLD_TEXT if blink else WHITE, r.inflate(4, 4), 2)
            img = self.text(str(int(demo.pack.lead_time[player])), self.font8, INK, False)
            s.blit(img, img.get_rect(center=r.center))
            x = r.right + 14
        self.center(s, self.text(demo.caption, self.font16, GOLD_TEXT), box.bottom + 12, box.centerx)

    def stick(self, s: pygame.Surface, cx: int, cy: int) -> None:
        """The cabinet's stick from above: a ball top over its base, and the
        four ways it goes."""
        pygame.draw.circle(s, INK, (cx, cy), 17)
        pygame.draw.circle(s, OFF, (cx, cy), 16)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            tip = (cx + dx * 23, cy + dy * 23)
            side = (dy * 5, dx * 5)
            back = (cx + dx * 17, cy + dy * 17)
            pygame.draw.polygon(s, config.COLOR_TEXT, [tip, (back[0] + side[0], back[1] + side[1]),
                                                       (back[0] - side[0], back[1] - side[1])])
        pygame.draw.circle(s, INK, (cx, cy), 10)
        pygame.draw.circle(s, GOLD_TEXT, (cx, cy), 9)
        pygame.draw.circle(s, WHITE, (cx - 3, cy - 3), 3)
