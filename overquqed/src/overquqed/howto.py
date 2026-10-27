"""HOW TO PLAY: the short card shown before every round picked from the menu.

Not the same thing as tutorial.py, which is Training Day: a whole guided
round where Chef Ket teaches one step at a time. This card is the 5-10 s
version that every round gets, Training Day included: the goal in three
lines, a tiny kitchen where the game's own bot (bot.py) cooks two orders on
the real rules (fridge, Blender or Flipper, pass), and the cabinet buttons.

Any button on either pad starts the round, once the card has been up for
DISMISS_GUARD (so the A that picked the kitchen can't skip it unseen). The
stick does not. RESTART from the pause menu goes straight to a new round.
"""

from __future__ import annotations

import math
import random

import pygame
from arqade_common.input import KEYBOARD, PAD

from overquqed import palette as P
from overquqed.bot import Bot
from overquqed.config import INTERNAL_HEIGHT, INTERNAL_WIDTH, KITCHEN_Y, TILE
from overquqed.dining import Dining
from overquqed.fonts import text
from overquqed.game import Scene
from overquqed.hud import panel_box, rich
from overquqed.input import PLAYERS, Input
from overquqed.ket import ket_surface
from overquqed.levels import Level
from overquqed.quantum import Noise
from overquqed.render import KitchenView, tile_px
from overquqed.sprites import portrait
from overquqed.world import IDLE, World

DISMISS_GUARD = 0.3  # seconds before a button press counts

# A two-chef kitchen just big enough for the core loop: each chef takes a
# fresh |0> from a fridge, runs it through one machine and serves it.
DEMO_LEVEL = Level(
    key="howto",
    name="How to play",
    short="How to play",
    blurb="",
    map=(
        "#########",
        "#F=H=X=F#",
        "#.1...2.#",
        "#.......#",
        "#=PPPPP=#",
    ),
    duration=math.inf,
    noise=Noise(),
    recipes=("+", "1"),
    guests=("surface", "dj"),
    tutorial=True,  # no orders of its own: the demo places them
)
DEMO_ORDERS = (("+", "surface"), ("1", "dj"))  # Surface Code wants |+>, Deutsch-Jozsa |1>
DEMO_LOOP = 5.0  # seconds, then the kitchen starts over
DEMO_WAIT = 0.6  # the guests walk in before the chefs move
DINING_SHOWN = 36  # px of dining room under the kitchen: the guests' feet

GOAL = (
    "Guests order quantum states, like |+> or |1>.",
    "Take a qubit from the fridge, change it with the",
    "gate machines and serve it before they walk out!",
)
CONTROLS = (
    ("STICK", "WALK", P.WHITE),
    ("A", "TAKE / PUT / SERVE", (120, 230, 120)),
    ("B", "USE MACHINE (HOLD)", (250, 120, 110)),
    ("Y", "SWAP CHEF (SOLO)", P.GOLD),
    ("START", "PAUSE", P.WHITE),
)
LIT = {label: col for label, _, col in CONTROLS if len(label) == 1}
CLUSTER = (("L", "X", "R"), ("Y", "B", "A"))  # the pads' printed 2x3 layout


class DemoKitchen:
    """The looping mini-round: a real World, cooked by the real Bot."""

    def __init__(self) -> None:
        self.scratch = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))
        self._start()

    def _start(self) -> None:
        # A seeded rng, so the demo never draws from (and shifts) the
        # unseeded randomness a capture seeds for the round itself.
        self.world = World(DEMO_LEVEL, random.Random(0))
        self.bot = Bot(self.world)
        self.view = KitchenView(self.world)
        self.dining = Dining(self.world, self.view.dining_top)
        self.floaters: list[tuple[pygame.Surface, int, int, float]] = []
        self.t = 0.0
        for i, (recipe, guest) in enumerate(DEMO_ORDERS):
            order = self.world.orders.spawn(0.0, recipe, guest)
            order.patience = order.remaining = 9999.0
            self.dining.on_event(("order", order))
            self.dining.actors[order.id].x -= 30 * i  # in single file

    @property
    def size(self) -> tuple[int, int]:
        return self.world.w * TILE, self.world.h * TILE + DINING_SHOWN

    def update(self, dt: float) -> None:
        self.t += dt
        if self.t >= DEMO_LOOP:
            self._start()
            return
        inputs = self.bot.update(dt) if self.t >= DEMO_WAIT else [IDLE, IDLE]
        self.world.update(dt, inputs)
        for ev in self.world.events:
            self.dining.on_event(ev)
            if ev[0] == "serve":
                px, py = tile_px(*ev[1])
                lbl = text(f"+{ev[2].points}", 8, P.GOOD, shadow=P.INK)
                self.floaters.append((lbl, px + TILE // 2 - lbl.get_width() // 2, py - 4, self.t))
        self.world.events.clear()
        self.dining.update(dt)

    def caption(self) -> tuple[str, str]:
        """(button, what it does) for P1's chef right now."""
        for job in self.bot.jobs:
            step = job.step
            if step is None or step.chef != 0:
                continue
            kind, st = step.kind, step.station.kind
            if kind == "take":
                return ("A", "TAKE A FRESH QUBIT") if st == "fridge" else ("A", "PICK IT UP AGAIN")
            if kind == "put":
                return ("A", "SERVE IT AT THE PASS") if st == "pass" else ("A", "PUT IT IN A MACHINE")
            if kind in ("tap", "hold"):
                return "B", "HOLD TO BLEND (H GATE)" if st == "h" else "TAP TO FLIP (X GATE)"
        if self.world.stats.delivered:
            return "", "SERVED! +POINTS"
        return "", "TWO ORDERS COME IN..."

    def draw(self, surf: pygame.Surface, x: int, y: int) -> None:
        s = self.scratch
        self.view.draw(s, self.world.t, {0, 1}, P.PLAYER_COLORS)
        self.dining.draw(s, self.t)
        for lbl, fx, fy, t0 in self.floaters:
            age = self.t - t0
            if age < 1.1:
                s.blit(lbl, (fx, fy - round(age * 18)))
        w, h = self.size
        surf.blit(s, (x, y), pygame.Rect(0, KITCHEN_Y, w, h))


def draw_cluster(surf: pygame.Surface, x: int, y: int, pitch: int = 24, r: int = 9) -> None:
    """The pad's six buttons as printed on the cabinet, used ones lit."""
    for row, labels in enumerate(CLUSTER):
        for col, label in enumerate(labels):
            cx, cy = x + col * pitch + r, y + row * pitch + r
            lit = LIT.get(label)
            pygame.draw.circle(surf, P.INK, (cx, cy + 1), r + 1)
            pygame.draw.circle(surf, lit or (70, 56, 86), (cx, cy), r)
            g = text(label, 8, P.INK if lit else (120, 106, 136))
            surf.blit(g, (cx - g.get_width() // 2 + 1, cy - 3))


def draw_stick(surf: pygame.Surface, cx: int, cy: int, t: float) -> None:
    """A joystick, wiggling round the four directions."""
    a = int(t * 2) % 4
    dx, dy = ((-4, 0), (0, -3), (4, 0), (0, 3))[a]
    pygame.draw.ellipse(surf, P.INK, (cx - 14, cy + 9, 28, 10))
    pygame.draw.ellipse(surf, (70, 56, 86), (cx - 13, cy + 10, 26, 7))
    pygame.draw.line(surf, P.INK, (cx, cy + 13), (cx + dx, cy + dy), 4)
    pygame.draw.circle(surf, P.INK, (cx + dx, cy + dy), 8)
    pygame.draw.circle(surf, (240, 70, 70), (cx + dx, cy + dy), 7)
    surf.fill(P.WHITE, (cx + dx - 3, cy + dy - 4, 2, 2))
    for ax, ay, pts in ((-21, 0, ((0, -3), (-3, 0), (0, 3))), (21, 0, ((0, -3), (3, 0), (0, 3))),
                        (0, -16, ((-3, 0), (0, -3), (3, 0)))):
        pygame.draw.polygon(surf, P.TEXT_DIM, [(cx + ax + px, cy + ay + py) for px, py in pts])


class HowToPlayScene(Scene):
    def __init__(self, app, level: Level, players: list[int]) -> None:
        super().__init__(app)
        self.level = level
        self.players = players
        self.t = 0.0
        self.demo = DemoKitchen()

    def update(self, dt: float, inp: Input) -> None:
        self.t += dt
        self.demo.update(dt)
        if inp.any_button and self.t >= DISMISS_GUARD:
            from overquqed.round_scene import RoundScene

            self.app.sfx("confirm")
            held = {p: set(inp.held[p]) for p in PLAYERS}
            self.app.switch(RoundScene(self.app, self.level, self.players, consumed=held))

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(P.BG)
        title = text("HOW TO PLAY", 16, P.GOLD, shadow=P.INK)
        surf.blit(title, ((INTERNAL_WIDTH - title.get_width()) // 2, 10))
        surf.blit(text("GOAL", 8, P.GOLD), (12, 36))
        for i, line in enumerate(GOAL):
            surf.blit(rich(line, P.TEXT, outline=P.INK), (56, 34 + i * 13))
        self._draw_demo(surf, 8, 80)
        self._draw_controls(surf, 240, 80)
        if int(self.t * 2) % 2 == 0:
            any_button = "ANY KEY" if self.app.inp.devices.everyone_on(KEYBOARD) else "ANY BUTTON"
            prompt = text(f"PRESS {any_button} TO START", 16, P.WHITE, shadow=P.INK)
            surf.blit(prompt, ((INTERNAL_WIDTH - prompt.get_width()) // 2, 318))

    def _draw_demo(self, surf: pygame.Surface, x: int, y: int) -> None:
        demo = self.demo
        w, h = demo.size
        surf.blit(panel_box(w + 8, h + 56, fill=P.HUD_BG, edge=(70, 56, 86)), (x, y))
        # the open orders as little tickets: who wants what
        surf.blit(text("ORDERS", 8, P.TEXT_DIM), (x + 6, y + 10))
        tx = x + 62
        for order in demo.world.orders.orders:
            k = ket_surface((order.recipe.key,))
            tk = panel_box(k.get_width() + 26, 22)
            tk.blit(portrait(order.guest.key), (3, 3))
            tk.blit(k, (22, (22 - k.get_height()) // 2))
            surf.blit(tk, (tx, y + 3))
            tx += tk.get_width() + 4
        pygame.draw.rect(surf, P.INK, (x + 3, y + 27, w + 2, h + 2))
        demo.draw(surf, x + 4, y + 28)
        button, what = demo.caption()
        cy = y + h + 36
        parts = [text(what, 8, P.TEXT)]
        if button:
            parts.insert(0, text(self._name(button) + ": ", 8, LIT[button]))
        width = sum(p.get_width() for p in parts)
        cx = x + 4 + (w - width) // 2
        for p in parts:
            surf.blit(p, (cx, cy))
            cx += p.get_width()

    def _name(self, label: str) -> str:
        """A printed name (STICK, A, START...) for the players' keys or pads:
        the one player's when one is cooking, both players' otherwise."""
        who = PLAYERS[self.players[0]] if len(self.players) == 1 else None
        return self.app.inp.name(label.lower(), who)

    def _draw_controls(self, surf: pygame.Surface, x: int, y: int) -> None:
        w = INTERNAL_WIDTH - 8 - x
        surf.blit(panel_box(w, self.demo.size[1] + 56, fill=P.HUD_BG, edge=(70, 56, 86)), (x, y))
        head = text("CONTROLS", 8, P.GOLD)
        surf.blit(head, (x + (w - head.get_width()) // 2, y + 8))
        draw_stick(surf, x + 52, y + 50, self.t)
        draw_cluster(surf, x + 118, y + 28)
        for i, (label, action, col) in enumerate(CONTROLS):
            ly = y + 92 + i * 18
            key = text(self._name(label) + ":", 8, col)
            if key.get_width() <= 52:  # right-aligned, as the pad's letters
                surf.blit(key, (x + 58 - key.get_width(), ly))
                surf.blit(text(action, 8, P.TEXT), (x + 66, ly))
            else:  # a long key name (e.g. "WASD / ARROWS"): the action follows it
                surf.blit(key, (x + 8, ly))
                surf.blit(text(action, 8, P.TEXT), (x + 16 + key.get_width(), ly))
        on_pads = self.app.inp.devices.everyone_on(PAD)
        note = text("BOTH PADS THE SAME" if on_pads else "SAME FOR BOTH PLAYERS", 8, P.TEXT_DIM)
        surf.blit(note, (x + (w - note.get_width()) // 2, y + 188))
