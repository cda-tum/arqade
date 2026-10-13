"""Everything on screen at 480x270, SNES-puzzle style, all procedural: the
title, the setup screen, two boards side by side (P1 blue on the left, P2
red on the right) or one centred board in single player, the HUD, the
animations and banners, the initials entry and the high-score table.

The board logic pauses for its own flash and settle steps, so the renderer
only adds juice on top of the real state: a squish when a pill lands, a
white flash on matched gates, star bursts when they clear, chain pop-ups,
and a shake when noise drops in.
"""

from __future__ import annotations

import math
import random

import pygame

from gate_drop import config, tutorial
from gate_drop.board import Cnot, Gate
from gate_drop.fonts import load_font
from gate_drop.match import (
    COUNTDOWN, GAME_OVER, HISCORES, LETTERS, LEVEL_CLEAR, MATCH_RESULT, NAME_ENTRY, PAUSE_ITEMS, PLAYERS, QUIT_ROW,
    ROUND, ROUND_RESULT, SETUP, TITLE, TITLE_ITEMS, TUTORIAL, BoardEvent, Match,
)
from gate_drop.sprites import INK, WHITE, Sprites, lighten, shade

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
CELL = config.CELL
WELL_W, WELL_H = config.COLS * CELL, config.ROWS * CELL
PANEL_X = {"p1": 150, "p2": 246}  # the HUD column beside each board
PANEL_W = 84
_NEIGHBOURS = (("r", (1, 0)), ("l", (-1, 0)), ("d", (0, 1)), ("u", (0, -1)))
SOLO_PANELS = (100, 300)  # the HUD columns either side of the single-player board
RULES = (
    "STACK GATE PILLS ON THE QUBIT WIRES",
    "INVERSES CANCEL:  XX  YY  ZZ  HH",
    "T CANCELS T-DAGGER.  HXH = Z,  HZH = X",
    "X ON A CONTROL OR Z ON A TARGET CLEARS A PAIR",
    "CLEAR EVERY PAULI ERROR BUG TO WIN!",
    "VERSUS: CHAINS DROP T GATES ON YOUR RIVAL",
)


def joint_toward(a, b) -> str:
    return {(1, 0): "r", (-1, 0): "l", (0, 1): "d", (0, -1): "u"}[(b[0] - a[0], b[1] - a[1])]


def make_background(colors) -> pygame.Surface:
    """A two-tone diamond tile pattern, one tile larger than the screen so it
    can scroll seamlessly."""
    a, b = colors
    s = pygame.Surface((W + 32, H + 32))
    s.fill(a)
    for ty in range(0, H + 32, 32):
        for tx in range(0, W + 32, 32):
            pygame.draw.polygon(s, b, [(tx + 16, ty + 3), (tx + 29, ty + 16), (tx + 16, ty + 29), (tx + 3, ty + 16)])
            s.fill(lighten(b, 0.25), (tx + 15, ty + 15, 2, 2))
    return s


def outlined(font: pygame.font.Font, text: str, color, outline=INK, shadow: bool = True) -> pygame.Surface:
    """Text with a one-pixel ink outline (and a drop shadow), readable on any pattern."""
    core = font.render(text, False, color)
    ink = font.render(text, False, outline)
    s = pygame.Surface((core.get_width() + 3, core.get_height() + 3), pygame.SRCALPHA)
    if shadow:
        s.blit(ink, (2, 3))
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2), (0, 0), (2, 0), (0, 2), (2, 2)):
        s.blit(ink, (dx, dy))
    s.blit(core, (1, 1))
    return s


def make_logo(font: pygame.font.Font, text: str = "GATE DROP") -> pygame.Surface:
    """GATE DROP (or a heading), each letter in a gate colour, with a chunky outline and shadow."""
    colors = [config.GATE_COLORS[k] for k in ("H", "X", "Y", "Z")]
    pieces, i = [], 0
    for ch in text:
        if ch == " ":
            pieces.append(None)
            continue
        pieces.append(outlined(font, ch, colors[i % len(colors)]))
        i += 1
    step = font.size("G")[0]
    s = pygame.Surface((step * len(text) + 6, pieces[0].get_height() + 3), pygame.SRCALPHA)
    for k, piece in enumerate(pieces):
        if piece is not None:
            s.blit(piece, (k * step, (k % 2) * 2))  # a little bounce, letter by letter
    return s


class Renderer:
    def __init__(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self.sprites = Sprites()
        self.font8, self.font16, self.font32 = load_font(8), load_font(16), load_font(32)
        self.backgrounds = [make_background(c) for c in config.BACKGROUNDS]
        self.logo = make_logo(self.font32)
        self.how_to_play = make_logo(self.font16, tutorial.HEADING)
        self.rng = random.Random(1)
        self.t = 0.0
        self.mode = 2
        self._boards = None
        self._text: dict = {}
        self.flash = {p: {} for p in PLAYERS}  # cell -> seconds left
        self.squish = {p: {} for p in PLAYERS}
        self.shake = {p: 0.0 for p in PLAYERS}
        self.popups: list[list] = []  # [player, image, age]
        self.stars: list[list] = []  # [x, y, vx, vy, life, colour]
        self.rain = [self._raindrop(random_y=True) for _ in range(14)]
        self.demo = tutorial.Demo()  # the HOW TO PLAY card's looping mini-round
        self.demo_flash: dict = {}
        self.demo_squish: dict = {}
        self.demo_popup: float | None = None  # age of its FIXED! pop-up
        self._state: str | None = None

    # --- per frame -----------------------------------------------------------------------

    def draw(self, match: Match, events: list, dt: float) -> None:
        self.t += dt
        if match.boards is not self._boards:
            self._boards = match.boards
            for p in PLAYERS:
                self.flash[p].clear()
                self.squish[p].clear()
                self.shake[p] = 0.0
            self.popups.clear()
            self.stars.clear()
        self.mode = match.mode
        if match.state != self._state:
            self._state = match.state
            if match.state == TUTORIAL:  # the card always opens on the demo's first frame
                self.demo.reset()
                self.demo_flash.clear()
                self.demo_squish.clear()
                self.demo_popup = None
        self._apply(events)
        self._tick(dt)
        if match.state == TITLE:
            self._title(match, dt)
        elif match.state == SETUP:
            self._setup(match)
        elif match.state == TUTORIAL:
            self._tutorial(match, dt)
        elif match.state == NAME_ENTRY:
            self._name_entry(match)
        elif match.state == HISCORES:
            self._hiscores(match)
        else:
            self._game(match)

    def _apply(self, events: list) -> None:
        for e in events:
            if not isinstance(e, BoardEvent):
                continue
            p, ev = e.player, e.event
            if ev.kind == "flash":
                for c in ev.cells:
                    self.flash[p][c] = config.CLEAR_TIME
            elif ev.kind == "clear":
                for c in ev.cells:
                    self._burst(p, c)
                if ev.value >= 2:
                    self._popup(p, f"{ev.value} CHAIN!", config.GATE_COLORS["H"])
            elif ev.kind == "land":
                for c in ev.cells:
                    self.squish[p][c] = 0.1
            elif ev.kind == "noise":
                self.shake[p] = 0.35
            elif ev.kind == "propagate":
                self._popup(p, "CNOT!", config.CNOT_COLOR)
            elif ev.kind == "attack":
                self._popup(p, f"SEND {ev.value}!", WHITE)
            elif ev.kind == "errors":
                self._popup(p, "FIXED!", lighten(config.PLAYER_COLORS[p], 0.5))
            elif ev.kind == "topout":
                self._popup(p, "OVERFLOW!", config.GATE_COLORS["X"])

    def _tick(self, dt: float) -> None:
        for timers in (*self.flash.values(), *self.squish.values(), self.demo_flash, self.demo_squish):
            for c in list(timers):
                timers[c] -= dt
                if timers[c] <= 0:
                    del timers[c]
        for p in PLAYERS:
            self.shake[p] = max(0.0, self.shake[p] - dt)
        for pop in self.popups:
            pop[2] += dt
        self.popups = [pop for pop in self.popups if pop[2] < 1.1]
        alive = []
        for s in self.stars:
            s[4] -= dt
            if s[4] > 0:
                s[0] += s[2] * dt
                s[1] += s[3] * dt
                s[3] += 260 * dt  # gravity
                alive.append(s)
        self.stars = alive

    def _origin(self, player: str) -> tuple[int, int]:
        return config.SOLO_ORIGIN if self.mode == 1 else config.BOARD_ORIGIN[player]

    def _cell_px(self, player: str, pos) -> tuple[int, int]:
        ox, oy = self._origin(player)
        return ox + pos[0] * CELL, oy + pos[1] * CELL

    def _burst(self, player: str, pos) -> None:
        self._burst_at(*self._cell_px(player, pos), lighten(config.PLAYER_COLORS[player], 0.5))

    def _burst_at(self, x: int, y: int, accent) -> None:
        """Stars flying out of the cell whose top-left is (x, y)."""
        for _ in range(6):
            angle = self.rng.uniform(0, 2 * math.pi)
            speed = self.rng.uniform(40, 110)
            color = self.rng.choice((WHITE, config.GATE_COLORS["H"], accent))
            self.stars.append([x + 8, y + 8, math.cos(angle) * speed, math.sin(angle) * speed - 60,
                               self.rng.uniform(0.35, 0.6), color])

    def _popup(self, player: str, text: str, color) -> None:
        font = self.font16 if len(text) <= 6 else self.font8  # the board is only 96 px wide
        self.popups.append([player, outlined(font, text, color), 0.0])

    # --- the game screen ------------------------------------------------------------------

    def _scroll_background(self, index: int) -> None:
        off = int(self.t * 8) % 32
        self.surface.blit(self.backgrounds[index % len(self.backgrounds)], (-off, -off))

    def _game(self, match: Match) -> None:
        self._scroll_background(match.round_no - 1)
        for p in match.players:
            self._board(match, p)
        if match.mode == 1:
            self._solo_panels(match)
        else:
            for p in PLAYERS:
                self._panel(match, p)
            label = outlined(self.font8, f"ROUND {match.round_no}", WHITE)
            self.surface.blit(label, (W // 2 - label.get_width() // 2, 8))
        for x, y, _vx, _vy, life, color in self.stars:
            size = 2 if life > 0.25 else 1
            self.surface.fill(color, (round(x), round(y), size, size))
        stacked = {p: 0 for p in PLAYERS}
        for player, img, age in reversed(self.popups):  # newest at the bottom, older ones above
            ox, oy = self._origin(player)
            rise = min(1.0, age / 0.25)
            bounce = round(math.sin(rise * math.pi) * 4)
            y = oy + WELL_H // 2 - round(rise * 30) - bounce - stacked[player]
            stacked[player] += img.get_height() + 2
            self.surface.blit(img, (ox + WELL_W // 2 - img.get_width() // 2, y))
        self._banner(match)
        if match.paused:
            self._pause_menu(match)

    def _pause_menu(self, match: Match) -> None:
        s = self.surface
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((*INK, 170))
        s.blit(veil, (0, 0))
        box = pygame.Rect(0, 0, 252, 118)
        box.center = (W // 2, H // 2)
        pygame.draw.rect(s, INK, box.inflate(4, 4), border_radius=7)
        pygame.draw.rect(s, (46, 40, 84), box, border_radius=6)
        pygame.draw.rect(s, WHITE, box, 2, border_radius=6)
        head = outlined(self.font16, "PAUSED", config.GATE_COLORS["H"])
        s.blit(head, (W // 2 - head.get_width() // 2, box.y + 12))
        for i, item in enumerate(PAUSE_ITEMS):
            active = i == match.pause_index
            img = outlined(self.font8, item, config.GATE_COLORS["H"] if active else WHITE, shadow=False)
            y = box.y + 44 + i * 18
            s.blit(img, (W // 2 - img.get_width() // 2, y))
            if active and int(self.t * 3) % 2 == 0:
                arrow = outlined(self.font8, ">", config.GATE_COLORS["H"], shadow=False)
                s.blit(arrow, (W // 2 - img.get_width() // 2 - 16, y))
        hint = outlined(self.font8, "A: PICK   START / B: RESUME", shade(WHITE, 0.8), shadow=False)
        s.blit(hint, (W // 2 - hint.get_width() // 2, box.bottom - 18))

    def _board(self, match: Match, player: str) -> None:
        board = match.boards.get(player)
        ox, oy = self._origin(player)
        if self.shake[player]:
            ox += round(math.sin(self.t * 90) * 2 * self.shake[player] / 0.35)
        color = config.PLAYER_COLORS[player]
        danger = board is not None and match.state == ROUND and board.stack_top() < config.DANGER_ROWS
        if danger and int(self.t * 6) % 2 == 0:
            color = lighten(color, 0.75)  # blinks towards white, never the other player's colour
        self._well(ox, oy, config.COLS, config.ROWS, color)
        if board is not None:
            self._cells(board, ox, oy, self.flash[player], self.squish[player])

    def _well(self, ox: int, oy: int, cols: int, rows: int, color) -> None:
        """An empty well in a player's colour: the riveted frame, the wires,
        and the |q_n> label plate underneath."""
        s = self.surface
        well = pygame.Rect(ox, oy, cols * CELL, rows * CELL)
        plate = config.LABEL_PLATE

        def framed(grow: int) -> pygame.Rect:  # the frame runs on below the well, round the label plate
            r = well.inflate(grow, grow)
            r.height += plate
            return r

        pygame.draw.rect(s, INK, framed(16), border_radius=5)
        pygame.draw.rect(s, shade(color, 0.6), framed(12), border_radius=4)
        pygame.draw.rect(s, color, framed(10), border_radius=4)
        pygame.draw.rect(s, lighten(color, 0.5), framed(10), 1, border_radius=4)
        for k in range(4):  # rivets
            rx = well.left - 3 if k % 2 == 0 else well.right + 1
            ry = well.top - 3 if k < 2 else well.bottom + plate + 1
            s.fill(lighten(color, 0.6), (rx, ry, 2, 2))
        s.fill(INK, well.inflate(2, 2))
        s.fill(config.COLOR_WELL, well)
        s.fill(INK, (well.x, well.bottom + 1, well.width, plate + 1))
        for x in range(cols):  # the qubit wires, each starting from its |q_n> label
            cx = ox + x * CELL + CELL // 2 - 1
            s.fill(config.COLOR_WIRE, (cx, oy, 2, well.height))
            s.blit(self.sprites.ket(x, lighten(color, 0.7)), (ox + x * CELL, well.bottom + 2))

    def _cells(self, board, ox: int, oy: int, flash: dict, squish: dict) -> None:
        """A board's gates, errors and falling pill, drawn into its well."""
        s = self.surface
        grid = board.grid
        frame = int(self.t * 3) % 2
        for pos, c in grid.items():
            if isinstance(c, Gate) and c.error:
                img = self.sprites.bug(c.kind, frame)
            elif isinstance(c, Gate):
                img = self.sprites.gate(c.kind, self._joint(grid, pos, c))
            else:
                right = grid.get((pos[0] + 1, pos[1]))
                joint = "r" if isinstance(right, Cnot) and right.pill == c.pill else "l"
                img = self.sprites.cnot(c.role, joint)
            px, py = ox + pos[0] * CELL, oy + pos[1] * CELL
            if pos in squish:
                py += 1
            s.blit(img, (px, py))
            if pos in flash and int(self.t * 20) % 2 == 0:
                s.fill(WHITE, (px + 2, py + 2, CELL - 4, CELL - 4))
        if board.piece is not None:
            cells = board.piece.cells()
            for i, (pos, half) in enumerate(cells):
                if pos[1] < 0:
                    continue
                joint = joint_toward(pos, cells[1 - i][0])
                img = self.sprites.cnot(half.role, joint) if isinstance(half, Cnot) else self.sprites.gate(half.kind, joint)
                s.blit(img, (ox + pos[0] * CELL, oy + pos[1] * CELL))

    @staticmethod
    def _joint(grid, pos, gate: Gate):
        if gate.pill is None:
            return None
        for name, (dx, dy) in _NEIGHBOURS:
            n = grid.get((pos[0] + dx, pos[1] + dy))
            if isinstance(n, Gate) and n.pill == gate.pill:
                return name
        return None

    def _panel(self, match: Match, player: str) -> None:
        s = self.surface
        color = config.PLAYER_COLORS[player]
        board = match.boards.get(player)
        ox, _oy = config.BOARD_ORIGIN[player]
        name = outlined(self.font16, player.upper(), color)
        s.blit(name, (ox + WELL_W // 2 - name.get_width() // 2, 4))
        x = PANEL_X[player]
        box = pygame.Rect(x, 30, PANEL_W, 200)
        pygame.draw.rect(s, INK, box, border_radius=5)
        pygame.draw.rect(s, shade(color, 0.55), box, 1, border_radius=5)
        mid = x + PANEL_W // 2

        def label(text, y):
            img = outlined(self.font8, text, WHITE, shadow=False)
            s.blit(img, (mid - img.get_width() // 2, y))

        label("NEXT", 38)
        if board is not None:
            first, second = board.next.halves
            if isinstance(first, Cnot):
                s.blit(self.sprites.cnot(first.role, "r"), (mid - CELL, 50))
                s.blit(self.sprites.cnot(second.role, "l"), (mid, 50))
            else:
                s.blit(self.sprites.gate(first.kind, "r"), (mid - CELL, 50))
                s.blit(self.sprites.gate(second.kind, "l"), (mid, 50))
        label("ERRORS", 80)
        left = board.errors_left() if board is not None else 0
        s.blit(self.sprites.bug("X", int(self.t * 3) % 2), (mid - 24, 94))
        count = outlined(self.font16, f"x{left}", WHITE if left else config.GATE_COLORS["H"])
        s.blit(count, (mid - 4, 94))
        label("NOISE", 124)
        if board is not None:
            for i, kind in enumerate(board.noise_queue[:8]):
                s.blit(self.sprites.dot(kind), (x + 10 + (i % 4) * 17, 140 + (i // 4) * 14))
        label("WINS", 182)
        for k in range(config.ROUNDS_TO_WIN):
            pip = pygame.Rect(mid - 14 + k * 18, 196, 12, 12)
            if k < match.scores[player]:
                pygame.draw.rect(s, color, pip, border_radius=3)
                s.fill(lighten(color, 0.6), (pip.x + 2, pip.y + 2, 3, 2))
            else:
                pygame.draw.rect(s, shade(color, 0.5), pip, 1, border_radius=3)

    def _solo_panels(self, match: Match) -> None:
        """Single player: score, best, level and speed on the left; the next
        pill and the errors left on the right."""
        s = self.surface
        color = config.PLAYER_COLORS["p1"]
        board = match.boards.get("p1")
        best = match.hiscores.entries[0].score if match.hiscores.entries else 0
        setup = match.setups["p1"]
        left, right = SOLO_PANELS
        for x in (left, right):
            box = pygame.Rect(x, 30, 80, 200)
            pygame.draw.rect(s, INK, box, border_radius=5)
            pygame.draw.rect(s, shade(color, 0.55), box, 1, border_radius=5)

        def text(x, y, msg, font=self.font8, col=WHITE):
            img = outlined(font, msg, col, shadow=False)
            s.blit(img, (x + 40 - img.get_width() // 2, y))

        text(left, 38, "SCORE")
        text(left, 52, f"{match.score:06d}", col=config.GATE_COLORS["H"])
        text(left, 74, "TOP")
        text(left, 88, f"{max(best, match.score):06d}")
        text(left, 112, "LEVEL")
        text(left, 124, str(match.level), self.font16, color)
        text(left, 152, "SPEED")
        text(left, 164, setup.speed, self.font16, color)
        text(right, 38, "NEXT")
        if board is not None:
            first, second = board.next.halves
            mid = right + 40
            if isinstance(first, Cnot):
                s.blit(self.sprites.cnot(first.role, "r"), (mid - CELL, 50))
                s.blit(self.sprites.cnot(second.role, "l"), (mid, 50))
            else:
                s.blit(self.sprites.gate(first.kind, "r"), (mid - CELL, 50))
                s.blit(self.sprites.gate(second.kind, "l"), (mid, 50))
        text(right, 80, "ERRORS")
        left_count = board.errors_left() if board is not None else 0
        s.blit(self.sprites.bug("X", int(self.t * 3) % 2), (right + 16, 94))
        count = outlined(self.font16, f"x{left_count}", WHITE if left_count else config.GATE_COLORS["H"])
        s.blit(count, (right + 36, 94))
        title = outlined(self.font8, f"LEVEL {match.level}", WHITE)
        s.blit(title, (W // 2 - title.get_width() // 2, 8))

    def _setup(self, match: Match) -> None:
        """Each player's level and speed, side by side with two players."""
        s = self.surface
        self._scroll_background(0)
        head = outlined(self.font16, "SET UP", WHITE)
        s.blit(head, (W // 2 - head.get_width() // 2, 14))
        centres = {"p1": W // 2} if match.mode == 1 else {"p1": 128, "p2": W - 128}
        for p, cx in centres.items():
            setup = match.setups[p]
            color = config.PLAYER_COLORS[p]
            box = pygame.Rect(0, 0, 200, 170)
            box.midtop = (cx, 44)
            pygame.draw.rect(s, INK, box.inflate(4, 4), border_radius=7)
            pygame.draw.rect(s, shade(color, 0.45), box, border_radius=6)
            pygame.draw.rect(s, color, box, 2, border_radius=6)
            name = outlined(self.font16, "1 PLAYER" if match.mode == 1 else p.upper(), color)
            s.blit(name, (cx - name.get_width() // 2, box.y + 10))
            rows = ((f"LEVEL {setup.level}", f"{2 * setup.level + 2} ERRORS"), (f"SPEED {setup.speed}", ""))
            for i, (main, sub) in enumerate(rows):
                y = box.y + 46 + i * 44
                active = setup.row == i and not setup.ready
                col = config.GATE_COLORS["H"] if active else WHITE
                label = outlined(self.font16, main, col)
                s.blit(label, (cx - label.get_width() // 2, y))
                if active and int(self.t * 3) % 2 == 0:
                    for side, glyph in ((-1, "<"), (1, ">")):
                        arrow = outlined(self.font16, glyph, col)
                        s.blit(arrow, (cx + side * (label.get_width() // 2 + 14) - arrow.get_width() // 2, y))
                if sub:
                    sub_img = outlined(self.font8, sub, WHITE, shadow=False)
                    s.blit(sub_img, (cx - sub_img.get_width() // 2, y + 20))
            if setup.ready:
                stamp = outlined(self.font16, "READY!", config.GATE_COLORS["T"])
            else:
                stamp = outlined(self.font8, "A: READY", WHITE, shadow=False)
            s.blit(stamp, (cx - stamp.get_width() // 2, box.bottom - 26))
        foot = outlined(self.font8, "STICK: CHOOSE    A: READY    B: BACK", WHITE, shadow=False)
        s.fill(INK, (0, 242, W, 20))
        s.blit(foot, (W // 2 - foot.get_width() // 2, 248))

    def _name_entry(self, match: Match) -> None:
        s = self.surface
        self._scroll_background(1)
        entry = match.name_entry
        for y, img in ((40, outlined(self.font16, "NEW HIGH SCORE!", config.GATE_COLORS["H"])),
                       (66, outlined(self.font16, f"{match.score}", WHITE)),
                       (96, outlined(self.font8, "ENTER YOUR INITIALS", WHITE, shadow=False))):
            s.blit(img, (W // 2 - img.get_width() // 2, y))
        if entry is not None:
            for i, letter in enumerate(entry.name):
                x = W // 2 - 60 + i * 44
                box = pygame.Rect(x, 118, 32, 40)
                active = i == entry.pos
                pygame.draw.rect(s, INK, box, border_radius=5)
                pygame.draw.rect(s, config.GATE_COLORS["H"] if active else shade(WHITE, 0.5), box, 2, border_radius=5)
                img = outlined(self.font32, letter, config.GATE_COLORS["H"] if active else WHITE)
                s.blit(img, (box.centerx - img.get_width() // 2, box.y + 4))
                if active and int(self.t * 4) % 2 == 0:
                    for dy, glyph in ((-16, "^"), (44, "v")):
                        arrow = outlined(self.font8, glyph, WHITE, shadow=False)
                        s.blit(arrow, (box.centerx - arrow.get_width() // 2, box.y + dy + 2))
        foot = outlined(self.font8, "STICK: LETTER    A: NEXT    B: BACK", WHITE, shadow=False)
        s.fill(INK, (0, 242, W, 20))
        s.blit(foot, (W // 2 - foot.get_width() // 2, 248))

    def _hiscores(self, match: Match) -> None:
        s = self.surface
        self._scroll_background(2)
        head = outlined(self.font16, "HIGH SCORES", config.GATE_COLORS["H"])
        s.blit(head, (W // 2 - head.get_width() // 2, 16))
        box = pygame.Rect(W // 2 - 130, 42, 260, 192)
        pygame.draw.rect(s, INK, box, border_radius=6)
        pygame.draw.rect(s, shade(WHITE, 0.5), box, 1, border_radius=6)
        entries = match.hiscores.entries
        if not entries:
            img = outlined(self.font8, "NO SCORES YET - BE THE FIRST!", WHITE, shadow=False)
            s.blit(img, (W // 2 - img.get_width() // 2, box.centery - 4))
        for i, e in enumerate(entries):
            y = box.y + 12 + i * 18
            fresh = i == match.new_rank
            if fresh and int(self.t * 4) % 2:
                continue
            col = config.GATE_COLORS["H"] if fresh else WHITE
            for x, text in ((box.x + 14, f"{i + 1:>2}."), (box.x + 52, e.name),
                            (box.x + 108, f"{e.score:>7}"), (box.x + 186, f"LV{e.level}")):
                s.blit(self.font8.render(text, False, col), (x, y))

    def _banner(self, match: Match) -> None:
        state = match.state
        lines = []
        if state == COUNTDOWN:
            lines = [outlined(self.font32, str(max(1, 3 - int(match.t))), WHITE)]
        elif state == ROUND and match.round_time < 0.6:
            lines = [outlined(self.font32, "GO!", config.GATE_COLORS["H"])]
        elif state == ROUND_RESULT:
            winner = match.last_winner
            if winner:
                lines = [outlined(self.font16, f"{winner.upper()} WINS THE ROUND", config.PLAYER_COLORS[winner])]
            else:
                lines = [outlined(self.font16, "DRAW!  REPLAY", WHITE)]
        elif state == LEVEL_CLEAR:
            lines = [outlined(self.font16, "LEVEL CLEAR!", config.GATE_COLORS["H"]),
                     outlined(self.font8, f"BONUS +{match.last_bonus}", WHITE, shadow=False)]
        elif state == GAME_OVER:
            lines = [outlined(self.font16, "GAME OVER", config.GATE_COLORS["X"]),
                     outlined(self.font8, f"SCORE {match.score}", WHITE, shadow=False)]
        elif state == MATCH_RESULT:
            winner = match.match_winner or "p1"
            lines = [outlined(self.font32, f"{winner.upper()} WINS!", config.PLAYER_COLORS[winner])]
            if match.t >= config.MATCH_RESULT_LOCK:
                lines.append(outlined(self.font8, "A / START: REMATCH     B: TITLE", WHITE, shadow=False))
        if not lines:
            return
        width = max(img.get_width() for img in lines) + 24
        height = sum(img.get_height() for img in lines) + 8 * len(lines) + 12
        box = pygame.Rect(0, 0, width, height)
        box.center = (W // 2, H // 2)
        pygame.draw.rect(self.surface, INK, box.inflate(4, 4), border_radius=7)
        pygame.draw.rect(self.surface, (46, 40, 84), box, border_radius=6)
        pygame.draw.rect(self.surface, WHITE, box, 2, border_radius=6)
        y = box.y + 10
        for img in lines:
            self.surface.blit(img, (W // 2 - img.get_width() // 2, y))
            y += img.get_height() + 8

    # --- how to play -----------------------------------------------------------------------

    def _tutorial(self, match: Match, dt: float) -> None:
        """The HOW TO PLAY card: the goal, the demo on a small well, and the
        controls on the cabinet's buttons, each lit while the demo uses it."""
        s = self.surface
        self._scroll_background(0)
        s.blit(self.how_to_play, (W // 2 - self.how_to_play.get_width() // 2, 8))
        self._demo(dt)
        goal = pygame.Rect(144, 34, W - 156, 62)
        self._card(goal, "GOAL")
        for i, line in enumerate(tutorial.GOAL[match.mode]):
            s.blit(self.font8.render(line, False, config.COLOR_TEXT), (goal.x + 10, goal.y + 20 + i * 12))
        controls = pygame.Rect(144, goal.bottom + 6, W - 156, 126)
        self._card(controls, "CONTROLS")
        self._controls(controls, self.demo.control())
        s.fill(INK, (0, 242, W, 20))
        if (self.t % 1.0) < 0.65:
            prompt = outlined(self.font8, tutorial.PROMPT, config.GATE_COLORS["H"], shadow=False)
            s.blit(prompt, (W // 2 - prompt.get_width() // 2, 248))

    def _card(self, box: pygame.Rect, title: str) -> None:
        s = self.surface
        pygame.draw.rect(s, INK, box, border_radius=6)
        pygame.draw.rect(s, shade(WHITE, 0.6), box, 1, border_radius=6)
        s.blit(outlined(self.font8, title, config.GATE_COLORS["H"], shadow=False), (box.x + 8, box.y + 5))

    def _demo(self, dt: float) -> None:
        """Steps the demo and draws it, with the game's own flash, stars and pop-up."""
        s = self.surface
        cols, rows = tutorial.DEMO_COLS, tutorial.DEMO_ROWS
        ox, oy = 72 - cols * CELL // 2, 42
        color = config.PLAYER_COLORS["p1"]
        for e in self.demo.update(dt):
            if e.kind == "flash":
                self.demo_flash.update(dict.fromkeys(e.cells, config.CLEAR_TIME))
            elif e.kind == "land":
                self.demo_squish.update(dict.fromkeys(e.cells, 0.1))
            elif e.kind == "clear":
                for x, y in e.cells:
                    self._burst_at(ox + x * CELL, oy + y * CELL, lighten(color, 0.5))
            elif e.kind == "errors":
                self.demo_popup = 0.0
        self._well(ox, oy, cols, rows, color)
        self._cells(self.demo.board, ox, oy, self.demo_flash, self.demo_squish)
        for x, y, _vx, _vy, life, star in self.stars:
            size = 2 if life > 0.25 else 1
            s.fill(star, (round(x), round(y), size, size))
        if self.demo_popup is not None and self.demo_popup < 1.1:
            self.demo_popup += dt
            rise = min(1.0, self.demo_popup / 0.25)
            img = outlined(self.font8, "FIXED!", lighten(color, 0.5))
            s.blit(img, (ox + cols * CELL // 2 - img.get_width() // 2, oy + 40 - round(rise * 24)))
        lines = tutorial.caption(self.demo)
        for i, line in enumerate(lines):
            img = outlined(self.font8, line, WHITE, shadow=False)
            s.blit(img, (72 - img.get_width() // 2, oy + rows * CELL + 22 + i * 12))

    def _controls(self, box: pygame.Rect, active: str | None) -> None:
        """The stick and the 2x3 cluster as printed on the cabinet (L X R over
        Y B A), plus Start: used buttons lit, the one the demo presses flashing
        white, and what each does listed beside them."""
        s = self.surface
        lit, dim = config.GATE_COLORS["H"], (70, 64, 110)
        # the stick: a ball on a shaft, leaning the way the demo pushes it
        base = (box.x + 30, box.y + 70)
        lean = {"left": (-5, 0), "down": (0, 4)}.get(active, (0, 0))
        top = (base[0] + lean[0], base[1] - 14 + lean[1])
        pygame.draw.ellipse(s, (46, 40, 84), (base[0] - 14, base[1] - 4, 28, 10))
        pygame.draw.ellipse(s, shade(WHITE, 0.6), (base[0] - 14, base[1] - 4, 28, 10), 1)
        pygame.draw.line(s, shade(WHITE, 0.7), base, top, 3)
        pygame.draw.circle(s, INK, top, 8)
        pygame.draw.circle(s, WHITE if active in ("left", "down") else lit, top, 7)
        s.fill(lighten(lit, 0.7), (top[0] - 3, top[1] - 4, 3, 2))
        if active == "left":  # an arrow the way it is pushed
            pygame.draw.polygon(s, WHITE, [(top[0] - 17, top[1]), (top[0] - 12, top[1] - 5), (top[0] - 12, top[1] + 5)])
        elif active == "down":
            pygame.draw.polygon(s, WHITE, [(top[0] + 15, top[1] + 4), (top[0] + 10, top[1] - 1), (top[0] + 20, top[1] - 1)])
        stick = outlined(self.font8, "STICK", lit, shadow=False)
        s.blit(stick, (base[0] - stick.get_width() // 2, base[1] + 12))
        # the buttons
        used = {name for name, _ in tutorial.CONTROLS}
        for row, names in enumerate(tutorial.CLUSTER):
            for col, name in enumerate(names):
                centre = (box.x + 76 + col * 22, box.y + 46 + row * 22)
                pressed = name.lower() == active
                fill = WHITE if pressed else (lit if name in used else dim)
                pygame.draw.circle(s, INK, (centre[0], centre[1] + 1), 9)
                pygame.draw.circle(s, fill, (centre[0], centre[1] + pressed), 8)
                letter = self.font8.render(name, False, INK if name in used else shade(WHITE, 0.55))
                s.blit(letter, letter.get_rect(center=(centre[0] + 1, centre[1] + 1 + pressed)))
        start = pygame.Rect(0, 0, 48, 14)
        start.center = (box.x + 98, box.y + 104)
        pygame.draw.rect(s, INK, start.inflate(2, 2), border_radius=7)
        pygame.draw.rect(s, lit, start, border_radius=6)
        label = self.font8.render("START", False, INK)
        s.blit(label, label.get_rect(center=(start.centerx + 1, start.centery + 1)))
        # what each one does
        for i, (name, action) in enumerate(tutorial.CONTROLS):
            y = box.y + 30 + i * 22
            flash = active == name.lower() or (name == "STICK" and active in ("left", "down"))
            key = outlined(self.font8, f"{name}:", WHITE if flash else lit, shadow=False)
            s.blit(key, (box.x + 140, y))
            s.blit(outlined(self.font8, action, WHITE, shadow=False), (box.x + 140 + key.get_width() + 6, y))

    # --- the title ------------------------------------------------------------------------

    def _raindrop(self, random_y: bool = False) -> list:
        kinds = config.GATE_KINDS
        y = self.rng.uniform(-H, H) if random_y else self.rng.uniform(-60, -32)
        return [self.rng.uniform(8, W - 24), y, self.rng.choice(kinds), self.rng.choice(kinds),
                self.rng.uniform(30, 70)]

    def _title(self, match: Match, dt: float) -> None:
        s = self.surface
        self._scroll_background(0)
        for i, drop in enumerate(self.rain):
            drop[1] += drop[4] * dt
            if drop[1] > H:
                self.rain[i] = drop = self._raindrop()
            s.blit(self.sprites.gate(drop[2], "d"), (round(drop[0]), round(drop[1])))
            s.blit(self.sprites.gate(drop[3], "u"), (round(drop[0]), round(drop[1]) + CELL))
        s.blit(self.logo, (W // 2 - self.logo.get_width() // 2, 12))
        strip = pygame.Rect(36, 56, W - 72, 12 * len(RULES) + 8)
        pygame.draw.rect(s, INK, strip, border_radius=6)
        pygame.draw.rect(s, shade(WHITE, 0.6), strip, 1, border_radius=6)
        for i, line in enumerate(RULES):
            img = self.font8.render(line, False, config.COLOR_TEXT)
            s.blit(img, (W // 2 - img.get_width() // 2, strip.y + 5 + i * 12))
        menu = pygame.Rect(0, 0, 220, 70)
        menu.midtop = (W // 2, strip.bottom + 6)
        pygame.draw.rect(s, INK, menu, border_radius=6)
        pygame.draw.rect(s, shade(WHITE, 0.6), menu, 1, border_radius=6)
        for i, item in enumerate(TITLE_ITEMS):
            active = i == match.title_index
            img = outlined(self.font16, item, config.GATE_COLORS["H"] if active else WHITE)
            x = menu.x + 52
            y = menu.y + 8 + i * 18 + (4 if i == QUIT_ROW else 0)  # QUIT sits a little apart from the modes
            s.blit(img, (x, y))
            if active and int(self.t * 3) % 2 == 0:
                s.blit(outlined(self.font16, ">", config.GATE_COLORS["H"]), (x - 24, y))
        if int(self.t * 2) % 2 == 0:
            press = outlined(self.font8, "PRESS START", config.GATE_COLORS["H"], shadow=False)
            s.blit(press, (W // 2 - press.get_width() // 2, menu.bottom + 6))
        foot = outlined(self.font8, "STICK: CHOOSE    A: PICK    START: PLAY", WHITE, shadow=False)
        bar = pygame.Rect(0, 242, W, 20)
        s.fill(INK, bar)
        s.blit(foot, (W // 2 - foot.get_width() // 2, 248))
