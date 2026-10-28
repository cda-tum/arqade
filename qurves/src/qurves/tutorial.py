"""The HOW TO PLAY card shown before every match started from the title.

Three parts: the goal in three lines, a looping demo of the core mechanic,
and the controls drawn as the cabinet's own pads (who steers with what
depends on the player count). The match decides when the card goes
(match.TUTORIAL); this module only draws it.

The demo is no animation of its own: Demo runs the real rules (rules.tick)
on a small arena with a scripted stick, so what it shows is exactly what the
game does. P1 drives over an H gate and splits into two mirrored copies; one
copy hits P2's trail and is gone while the other drives on; P2 hits the wall
and P1 takes the round. Then it starts over. Demo is pure and unit tested;
TutorialScreen draws it with the renderer's own trail stamps, glows and
gate tokens.
"""

from __future__ import annotations

import math
import random

import pygame
from arqade_common.input import KEYBOARD

from arqade_common import keycaps

from qurves import config, rules
from qurves.fx import Fx

UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)

GOAL = (
    "LAST BIKE DRIVING TAKES THE ROUND. FIRST TO 3 WINS.",
    "DRIVE OVER H TO SPLIT INTO MIRRORED COPIES:",
    "YOU'RE ONLY OUT WHEN EVERY COPY HAS CRASHED.",
)
CAPTIONS = (
    "STEER INTO THE H GATE",
    "SPLIT! NOW YOU ARE TWO MIRRORED COPIES",
    "ONE COPY CRASHED. THE OTHER DRIVES ON",
    "P2 HIT THE WALL: P1 TAKES THE ROUND",
)
PROMPT = "PRESS ANY BUTTON TO START"
KEYBOARD_PROMPT = "PRESS ANY KEY TO START"  # when everyone is on the keyboard

# --- the demo (pure) ---------------------------------------------------------------

DEMO_W, DEMO_H = 72, 24  # cells: 432 x 144 px, the game's own cell size
DEMO_SPEED = config.SPEED_START  # cells per second, as at the start of a round
DEMO_LEAD = 0.4  # seconds both bikes wait at the start
DEMO_HOLD = 1.6  # seconds the end stays up before it starts over
DEMO_START = {"p1": ((3, 12), RIGHT), "p2": ((30, 2), DOWN)}
DEMO_GATE = rules.Gate("H", (14, 12))
# The scripted stick: tick number -> {player: direction}. P1 takes the H on
# tick 9, its copies fork up and down, and on tick 14 both turn right (the
# lower one mirrored, so "right" stays right). P2 turns right on tick 11,
# leaving a wall of trail across the upper copy's row.
DEMO_STEER = {11: {"p2": RIGHT}, 14: {"p1": RIGHT}}


class Demo:
    def __init__(self) -> None:
        self.restart()

    def restart(self) -> None:
        arena = rules.Arena(DEMO_W, DEMO_H)
        players = {}
        for name, (pos, heading) in DEMO_START.items():
            arena.set(pos, rules.Trail(name, None))
            players[name] = rules.Player(name, [rules.Bike(pos, heading, prev=pos)])
        self.state = rules.RoundState(arena, players, gates=[rules.Gate(DEMO_GATE.kind, DEMO_GATE.pos)])
        self.ticks = 0
        self.accum = -DEMO_LEAD
        self.hold = 0.0
        self.copy_lost = False
        self.rng = random.Random(0)  # the script never needs it, but rules.tick takes one

    @property
    def phase(self) -> int:
        """Which caption fits: 0 before the split, 1 split, 2 a copy lost, 3 over."""
        if self.state.over:
            return 3
        if self.copy_lost:
            return 2
        return 1 if self.state.players["p1"].is_split else 0

    @property
    def tick_fraction(self) -> float:
        return 1.0 if self.state.over else max(0.0, min(1.0, self.accum * DEMO_SPEED))

    def update(self, dt: float) -> list:
        """Advance by dt; returns the rules' events (a restart returns none)."""
        if self.state.over:
            self.hold += dt
            if self.hold >= DEMO_HOLD:
                self.restart()
            return []
        events: list = []
        self.accum += dt
        while not self.state.over and self.accum >= 1.0 / DEMO_SPEED:
            self.accum -= 1.0 / DEMO_SPEED
            self.ticks += 1
            step = rules.tick(self.state, DEMO_STEER.get(self.ticks, {}), self.rng)
            self.copy_lost |= any(isinstance(e, rules.Crash) and e.player == "p1" for e in step)
            events += step
        return events


# --- the screen ----------------------------------------------------------------------

DEMO_POS = ((config.INTERNAL_WIDTH - DEMO_W * config.CELL) // 2, 164)
CONTROLS_Y = 418  # the centre line of the drawn pads
BUTTON_R = 10
# The cabinet's 2x3 cluster as printed, row-major: L X R / Y B A. Of these,
# X Y B A steer, laid out like W A S D.
CLUSTER = (("L", "X", "R"), ("Y", "B", "A"))
BUTTON_DIR = {"X": UP, "Y": LEFT, "B": DOWN, "A": RIGHT}
UNLIT = (60, 66, 100)
WHITE = (255, 255, 255)


def _cell(c) -> tuple[int, int]:
    """The pixel centre of a demo cell, on screen."""
    return (DEMO_POS[0] + c[0] * config.CELL + config.CELL // 2, DEMO_POS[1] + c[1] * config.CELL + config.CELL // 2)


def _arrow(surface: pygame.Surface, color, centre, d, size: int = 4) -> None:
    """A small solid triangle pointing in grid direction d."""
    cx, cy = centre
    dx, dy = d
    px, py = -dy, dx  # perpendicular
    tip = (cx + dx * size, cy + dy * size)
    base = [(cx - dx * size + px * size, cy - dy * size + py * size),
            (cx - dx * size - px * size, cy - dy * size - py * size)]
    pygame.draw.polygon(surface, color, [tip, *base])


class TutorialScreen:
    """Draws the card. Built by the Renderer, whose fonts, trail stamps, head
    glows, gate tokens and text helpers it borrows."""

    def __init__(self, renderer) -> None:
        from qurves import render  # render builds this screen; import it late

        self.r = renderer
        self.render = render
        self.panel = render.make_arena(DEMO_W, DEMO_H)
        self.board = self.panel.copy()
        self.ghost = {p: pygame.Surface(self.panel.get_size(), pygame.SRCALPHA) for p in DEMO_START}
        self.heading = render.make_logo(renderer.font32, "HOW TO PLAY")
        self.fx = Fx()
        self.demo = Demo()
        self.shown = None  # the demo round the board was drawn for
        self.t = 0.0

    def reset(self) -> None:
        self.demo.restart()
        self.fx.clear()
        self.t = 0.0

    def draw(self, surface: pygame.Surface, mode: int, blink_t: float, dt: float) -> None:
        self.t += dt
        events = self.demo.update(dt)
        if self.demo.state is not self.shown:
            self._clear_board()
        self._apply(events)
        self.fx.update(dt)

        r = self.r
        surface.blit(r.background, (0, 0))
        surface.fill(config.COLOR_BACKGROUND, (0, 0, config.INTERNAL_WIDTH, config.HUD_HEIGHT))
        r._center(self.heading, 66)
        y = 104
        for line in GOAL:
            r._center(r._plain(line, r.font16, config.COLOR_TEXT), y, add=False)
            y += 20
        self._draw_demo(surface)
        r._center(r._glow(CAPTIONS[self.demo.phase], r.font16, config.COLOR_FPS), 326)
        self._draw_controls(surface, mode)
        if int(blink_t * 2) % 2 == 0:
            prompt = KEYBOARD_PROMPT if r.devices.everyone_on(KEYBOARD) else PROMPT
            r._center(r._glow(prompt, r.font16, WHITE), 512)

    # --- the demo -------------------------------------------------------------------

    def _clear_board(self) -> None:
        self.board.blit(self.panel, (0, 0))
        for layer in self.ghost.values():
            layer.fill((0, 0, 0, 0))
        self.fx.clear()
        self.shown = self.demo.state

    def _stamp(self, target, stamps, a, b, flags) -> None:
        cell, glow = config.CELL, self.render.GLOW_R
        (ax, ay), (bx, by) = (a[0] * cell + cell // 2, a[1] * cell + cell // 2), (b[0] * cell + cell // 2,
                                                                                  b[1] * cell + cell // 2)
        if abs(ax - bx) + abs(ay - by) == cell:
            target.blit(stamps[ay == by], (min(ax, bx) - glow, min(ay, by) - glow), special_flags=flags)

    def _apply(self, events: list) -> None:
        r = self.r
        for e in events:
            if isinstance(e, rules.Moved):
                if e.node is None:
                    self._stamp(self.board, r.solid_stamps[e.player], e.frm, e.to, pygame.BLEND_MAX)
                elif (e.to[0] + e.to[1]) % 2 == 0:  # dashed, as in the game
                    self._stamp(self.ghost[e.player], r.ghost_stamps[e.player], e.frm, e.to, pygame.BLEND_RGBA_MAX)
                continue
            color = config.PLAYER_COLORS.get(getattr(e, "player", None), WHITE)
            if isinstance(e, rules.Split):
                self.fx.ring(_cell(e.pos), color)
            elif isinstance(e, rules.Collapse):
                for path in e.solidified:
                    for a, b in zip(path, path[1:]):
                        self._stamp(self.board, r.solid_stamps[e.player], a, b, pygame.BLEND_MAX)
                self._rebuild_ghost(e.player)
                self.fx.dissolve([_cell(c) for c in e.dissolved], color)
            elif isinstance(e, rules.Crash):
                self.fx.burst(_cell(e.pos), self.render.lighten(color, 0.3))
            elif isinstance(e, rules.PickedUp):
                self.fx.burst(_cell(e.pos), config.GATE_COLORS[e.kind], count=20, speed=100, life=0.4)

    def _rebuild_ghost(self, player: str) -> None:
        layer = self.ghost[player]
        layer.fill((0, 0, 0, 0))
        pl = self.demo.state.players[player]
        for node in pl.nodes.values():
            for a, b in zip(node.cells, node.cells[1:]):
                if (b[0] + b[1]) % 2 == 0:
                    self._stamp(layer, self.r.ghost_stamps[player], a, b, pygame.BLEND_RGBA_MAX)

    def _draw_demo(self, s: pygame.Surface) -> None:
        r, rs = self.r, self.demo.state
        s.blit(self.board, DEMO_POS)
        for i, (p, pl) in enumerate(rs.players.items()):
            if pl.is_split:
                layer = self.ghost[p]
                layer.set_alpha(round(205 + 50 * math.sin(self.t * 23 + i * 2.1)))
                s.blit(layer, DEMO_POS)
        level = int((0.5 + 0.5 * math.sin(self.t * 6)) * 7.999)
        for gate in rs.gates:
            token = r.tokens[gate.kind][level]
            half = token.get_width() // 2
            x, y = _cell(gate.pos)
            s.blit(token, (x - half, y - half), special_flags=pygame.BLEND_ADD)
        frac = self.demo.tick_fraction
        for p, pl in rs.players.items():
            if not pl.alive:
                continue
            for bike in pl.bikes:
                (px, py), (qx, qy) = _cell(bike.prev or bike.pos), _cell(bike.pos)
                sprite = r.heads[(p, bike.node is not None)]
                half = sprite.get_width() // 2
                x, y = round(px + (qx - px) * frac), round(py + (qy - py) * frac)
                s.blit(sprite, (x - half, y - half), special_flags=pygame.BLEND_ADD)
        self.fx.draw(s)

    # --- the controls ---------------------------------------------------------------

    def _draw_controls(self, s: pygame.Surface, mode: int) -> None:
        """Each pad on its own side of the screen, as on the cabinet. With 2
        players a pad's stick and buttons both steer its player; with 4 the
        stick is one player and the X Y B A buttons another."""
        r = self.r
        for pad, cx in ((0, config.INTERNAL_WIDTH // 4), (1, 3 * config.INTERNAL_WIDTH // 4)):
            stick_player, button_player = (("p1", "p3"), ("p2", "p4"))[pad]
            if mode == 2:
                button_player = stick_player
            stick_x, cluster_x, start_x = cx - 135, cx + 5, cx + 120
            y, top = CONTROLS_Y, CONTROLS_Y - 54
            if mode == 2:
                color = config.PLAYER_COLORS[stick_player]
                self._label(stick_player.upper(), r.font16, color, ((stick_x + cluster_x) // 2, top))
                self._label("OR", r.font16, config.COLOR_DIM, ((stick_x + cluster_x) // 2 - 6, y))
            else:
                for name, x in ((stick_player, stick_x), (button_player, cluster_x)):
                    self._label(name.upper(), r.font16, config.PLAYER_COLORS[name], (x, top))
            side = ("p1", "p2")[pad]  # names the controls for this side's keys or pad
            if r.devices[side] == KEYBOARD:  # this side's keys, not its pad
                label = r.devices.label
                stick_keys = ((None, label("up", side), None),
                              (label("left", side), label("down", side), label("right", side)))
                self._keys(s, (stick_x, y), config.PLAYER_COLORS[stick_player], stick_keys)
                face_keys = tuple(tuple(label(b.lower(), side) for b in row) for row in CLUSTER)
                self._keys(s, (cluster_x, y), config.PLAYER_COLORS[button_player], face_keys)
                self._key(s, label("start", side), r.font8, (start_x, y), config.PLAYER_COLORS[stick_player])
            else:
                self._stick(s, (stick_x, y), config.PLAYER_COLORS[stick_player])
                self._cluster(s, (cluster_x, y), config.PLAYER_COLORS[button_player])
                self._start(s, (start_x, y), config.PLAYER_COLORS[stick_player])
            for x, device, action in ((stick_x, r.name("stick", side), "STEER"),
                                      (cluster_x, r.name("face", side), "STEER"),
                                      (start_x, r.name("start", side), "PAUSE")):
                self._label(device, r.font8, config.COLOR_TEXT, (x, y + 44))
                self._label(action, r.font8, config.COLOR_DIM, (x, y + 58))

    def _label(self, text: str, font, color, centre) -> None:
        img = self.r._plain(text, font, color)
        self.r.surface.blit(img, img.get_rect(center=centre))

    def _stick(self, s: pygame.Surface, centre, color) -> None:
        """A ball-top stick seen from above, with the four ways it steers."""
        lighten, scale = self.render.lighten, self.render.scale
        cx, cy = centre
        pygame.draw.circle(s, (14, 18, 34), centre, 22)
        pygame.draw.circle(s, scale(color, 0.5), centre, 22, 1)
        for d in (UP, DOWN, LEFT, RIGHT):
            _arrow(s, lighten(color, 0.3), (cx + d[0] * 30, cy + d[1] * 30), d)
        s.blit(self._ball(color), (cx - 13, cy - 13), special_flags=pygame.BLEND_ADD)

    def _ball(self, color) -> pygame.Surface:
        key = ("ball", color)
        cache = self.r._cache
        if key not in cache:
            ball = pygame.Surface((27, 27))
            ball.fill((0, 0, 0))
            pygame.draw.circle(ball, self.render.scale(color, 0.55), (13, 13), 12)
            pygame.draw.circle(ball, color, (13, 13), 10)
            pygame.draw.circle(ball, self.render.lighten(color, 0.6), (10, 10), 4)
            cache[key] = ball
        return cache[key]

    def _cluster(self, s: pygame.Surface, centre, color) -> None:
        """The 2x3 buttons as printed (L X R / Y B A). The four that steer are
        lit in the player's colour with an arrow for their direction."""
        lighten, scale = self.render.lighten, self.render.scale
        cx, cy = centre
        for row, labels in enumerate(CLUSTER):
            for col, label in enumerate(labels):
                x, y = cx + (col - 1) * 30, cy + (row * 2 - 1) * 14
                d = BUTTON_DIR.get(label)
                if d is None:
                    pygame.draw.circle(s, (14, 18, 34), (x, y), BUTTON_R)
                    pygame.draw.circle(s, UNLIT, (x, y), BUTTON_R, 1)
                    text = self.r._plain(label, self.r.font8, UNLIT)
                else:
                    pygame.draw.circle(s, scale(color, 0.4), (x, y), BUTTON_R)
                    pygame.draw.circle(s, lighten(color, 0.3), (x, y), BUTTON_R, 2)
                    text = self.r._plain(label, self.r.font8, lighten(color, 0.8))
                    _arrow(s, lighten(color, 0.3), (x + d[0] * 17, y + d[1] * 17), d, 3)
                s.blit(text, text.get_rect(center=(x + 1, y + 1)))

    def _keys(self, s: pygame.Surface, centre, color, names) -> None:
        """Keys laid out like the pad's 2x3 cluster (the keyboard's are too):
        the four that steer lit in the player's colour, with an arrow for
        their direction (the arrow keys show theirs on the cap)."""
        cx, cy = centre
        for row, keys in enumerate(names):
            for col, name in enumerate(keys):
                if name is None:
                    continue
                x, y = cx + (col - 1) * 30, cy + (row * 2 - 1) * 14
                d = BUTTON_DIR.get(CLUSTER[row][col])
                self._key(s, name, self.r.font16, (x, y), color if d else None)
                if d and name not in keycaps.ARROWS:
                    _arrow(s, self.render.lighten(color, 0.3), (x + d[0] * 19, y + d[1] * 19), d, 3)

    def _key(self, s: pygame.Surface, name: str, font, centre, color) -> None:
        """One keycap centred on `centre`, lit in `color` (None: unused)."""
        lighten, scale = self.render.lighten, self.render.scale
        w, h = keycaps.keycap_size(font, name)
        topleft = (centre[0] - w // 2, centre[1] - h // 2)
        if color is None:
            keycaps.draw_keycap(s, font, name, topleft, (14, 18, 34), UNLIT, UNLIT)
        else:
            keycaps.draw_keycap(s, font, name, topleft, scale(color, 0.4), lighten(color, 0.3), lighten(color, 0.8))

    def _start(self, s: pygame.Surface, centre, color) -> None:
        pill = pygame.Rect(0, 0, 50, 18)
        pill.center = centre
        pygame.draw.rect(s, self.render.scale(color, 0.4), pill, border_radius=9)
        pygame.draw.rect(s, self.render.lighten(color, 0.3), pill, 2, border_radius=9)
        text = self.r._plain("START", self.r.font8, self.render.lighten(color, 0.8))
        s.blit(text, text.get_rect(center=(centre[0] + 1, centre[1] + 1)))

