"""The HOW TO PLAY card, shown before every match begun from the title (match.HOWTO).

Its parts: the goal in three lines, a looping demo of the core mechanic, the controls drawn
as the cabinet's pad (the stick, the L X R / Y B A cluster with A lit, and START) and a
blinking PRESS ANY BUTTON TO START. The match decides when it goes; this module only draws.

The demo is no animation of its own: `Demo` runs a real `Race` on THE FRIDGE with the
game's own CPU driver at full skill on P1's car. It starts a little before the race's first
gate row, off to the left of the glowing arch, steers into it, gets its RIGHT GATE boost,
drives on with its flames lit, then starts over. `Demo` is pure and unit tested;
`TutorialCard` draws it with the game's own road renderer, sprites and HUD pieces.
"""

from __future__ import annotations

import pygame

from gate_prix import bot, config, track
from gate_prix.race import Race

DEMO_SEED = 24  # its first row: three arches, the right one (Z) far over on the right
DEMO_LEAD = 1.9  # seconds at top speed before the row, where the demo starts
DEMO_X = -0.3  # where the car starts, left of the arch
DEMO_HOLD = 1.8  # seconds it drives on after the row, boosting, before it starts over
GOAL = (
    "DRIVE THROUGH THE GLOWING GATE IN EVERY ROW.",
    "EACH RIGHT GATE BUILDS YOUR CIRCUIT AND GIVES YOU A BOOST.",
    "FEWER MISTAKES = A FASTER FINAL LAP.",
)
CAPTIONS = ("STEER INTO THE GLOWING GATE", "RIGHT GATE: BOOST!", "WRONG GATE: NO BOOST")
PROMPT = "PRESS ANY BUTTON TO START"
CLUSTER = (("L", "X", "R"), ("Y", "B", "A"))  # the cabinet's buttons as printed


class Demo:
    """The scripted scene: P1's car, a CPU driver, the race's first gate row."""

    def __init__(self) -> None:
        self.restart()

    def restart(self) -> None:
        race = Race(DEMO_SEED, 1)
        self.race = race
        self.row = race.rows[0]
        car = race.racer("p1").car
        car.z = car.prev_z = self.row.z - DEMO_LEAD * config.TOP_SPEED
        car.x = car.prev_x = DEMO_X
        car.speed = config.TOP_SPEED
        for r in race.racers[1:]:  # the CPU cars wait far behind, out of the picture
            r.car.z = r.car.prev_z = -100 * config.TOP_SPEED
        self.driver = bot.Bot("p1", 1.0, DEMO_SEED, offset=0.0)
        self.outcome: str | None = None  # "right", "wrong" or "miss", once it crossed the row
        self.after = 0.0  # seconds since

    @property
    def car(self):
        return self.race.racer("p1").car

    @property
    def phase(self) -> int:
        """Which caption fits: 0 before the row, 1 a right gate, 2 anything else."""
        if self.outcome is None:
            return 0
        return 1 if self.outcome == "right" else 2

    def update(self, dt: float) -> list:
        """Advance by dt; returns the race's events for P1's car."""
        if self.outcome is not None:
            self.after += dt
            if self.after >= DEMO_HOLD:
                self.restart()
                return []
        events = [e for e in self.race.update(dt, {"p1": self.driver.controls(self.race)})
                  if e.car == "p1"]
        for e in events:
            if e.kind in ("right", "wrong", "miss") and self.outcome is None:
                self.outcome = e.kind
        return events

    def objects(self) -> list:
        """What the demo's road shows: the first lap's rows and P1's car (with its flame)."""
        car = self.car
        objects = track.arch_objects(self.race.rows[:2]) + [(0.0, 0.0, "gantry"),
                                                            (car.z, car.x, car.kind)]
        if car.boost > 0:
            objects.append((car.z - 1.0, car.x, f"flame:{int(self.race.time * 20) % 4}"))
        return objects


# --- The card -------------------------------------------------------------------------------

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
DEMO_RECT = (40, 142, 448, 252)
GOLD = (255, 230, 120)
SOFT = (200, 210, 235)
LABEL = (190, 200, 230)
UNLIT = (70, 76, 104)
INK = (8, 8, 20)
WHITE = (255, 255, 255)


class TutorialCard:
    """Draws the card. Built by the Renderer (at start-up), whose text cache, panels, sprite
    cache and markers it borrows."""

    def __init__(self, renderer) -> None:
        from gate_prix.road import RoadView

        self.r = renderer
        self.view = RoadView(DEMO_RECT)
        self.sprites: list = []
        self.demo = Demo()
        self.t = 0.0
        self.controls = self._controls_picture()

    def reset(self) -> None:
        self.demo.restart()
        self.t = 0.0

    def draw(self, surface: pygame.Surface, mode: int, dt: float) -> None:
        self.t += dt
        self.demo.update(dt)
        r = self.r
        surface.blit(r._backdrop, (0, 0))
        surface.blit(r._shade[215], (0, 0))
        r.put("HOW TO PLAY", 40, GOLD, center=(W // 2, 38))
        for i, line in enumerate(GOAL):
            r.put(line, 16, SOFT if i else WHITE, center=(W // 2, 80 + 22 * i))
        self._draw_demo(surface)
        surface.blit(self.controls, (520, DEMO_RECT[1]))
        who = "P1: LEFT PAD     P2: RIGHT PAD" if mode == 2 else "EITHER PAD DRIVES"
        r.put(who, 13, LABEL, center=(520 + 200, DEMO_RECT[1] + DEMO_RECT[3] - 16))
        if int(self.t * 2) % 2 == 0:
            r.put(PROMPT, 24, GOLD, center=(W // 2, 470))
        r.put("START + SELECT: QUIT", 11, LABEL, center=(W // 2, 516))

    def _draw_demo(self, surface: pygame.Surface) -> None:
        r, demo, view = self.r, self.demo, self.view
        car = demo.car
        view.draw(surface, demo.race.track, car.z - config.CAR_AHEAD, car.x, self.sprites,
                  demo.objects())
        view.draw_sprites(surface, self.sprites, r.cache)
        if demo.outcome is None:
            r._markers_over_right_arches(view, self.sprites)
        x, y, w, h = DEMO_RECT
        pygame.draw.rect(surface, (200, 205, 225), (x - 2, y - 2, w + 4, h + 4), 2, border_radius=4)
        caption = CAPTIONS[demo.phase]
        col = (110, 190, 255) if demo.phase == 1 else (GOLD if demo.phase == 0 else (255, 90, 96))
        r.put(caption, 20, col, center=(x + w // 2, y + h + 22))
        if demo.phase == 1 and demo.after < 1.0:
            r.put("+BOOST", 22, (110, 190, 255), center=(x + w // 2, y + h - 78))

    # --- The controls, drawn once --------------------------------------------------------

    def _controls_picture(self) -> pygame.Surface:
        r = self.r
        s = pygame.Surface((400, DEMO_RECT[3]), pygame.SRCALPHA)
        s.blit(r.panel(400, DEMO_RECT[3], (200, 205, 225), 220), (0, 0))
        col = config.PLAYER_COLORS["p1"]
        # the stick, from above: left, right and back
        cx, cy = 52, 62
        pygame.draw.circle(s, (14, 18, 34), (cx, cy), 26)
        pygame.draw.circle(s, (90, 96, 130), (cx, cy), 26, 1)
        for d in ((-1, 0), (1, 0), (0, 1)):
            tip = (cx + d[0] * 40, cy + d[1] * 40)
            px, py = -d[1], d[0]
            base = [(cx + d[0] * 32 + px * 6, cy + d[1] * 32 + py * 6),
                    (cx + d[0] * 32 - px * 6, cy + d[1] * 32 - py * 6)]
            pygame.draw.polygon(s, (150, 200, 255), [tip, *base])
        pygame.draw.circle(s, (30, 60, 110), (cx, cy), 14)
        pygame.draw.circle(s, col, (cx, cy), 12)
        pygame.draw.circle(s, (210, 235, 255), (cx - 4, cy - 4), 4)
        lines = (("STICK LEFT / RIGHT: STEER", WHITE), ("STICK BACK: BRAKE", WHITE),
                 ("STICK BACK + STEER: DRIFT", GOLD))
        for i, (text, c) in enumerate(lines):
            img = r.text(text, 15, c)
            s.blit(img, img.get_rect(midleft=(112, 34 + 24 * i)))
        img = r.text("let go of a drift for a mini-turbo", 11, LABEL, shadow=False)
        s.blit(img, img.get_rect(midleft=(112, 106)))
        # the buttons as printed, A lit
        bx, by = 52, 148
        for row, labels in enumerate(CLUSTER):
            for k, label in enumerate(labels):
                x, y = bx + (k - 1) * 28, by + (row * 2 - 1) * 13
                lit = label == "A"
                pygame.draw.circle(s, (210, 60, 70) if lit else (14, 18, 34), (x, y), 11)
                pygame.draw.circle(s, GOLD if lit else UNLIT, (x, y), 11, 2)
                img = r.text(label, 11, WHITE if lit else UNLIT, shadow=False)
                s.blit(img, img.get_rect(center=(x, y + 1)))
        img = r.text("A: USE YOUR ITEM", 15, WHITE)
        s.blit(img, img.get_rect(midleft=(112, by - 6)))
        img = r.text("boxes on the road give one", 11, LABEL, shadow=False)
        s.blit(img, img.get_rect(midleft=(112, by + 14)))
        pill = pygame.Rect(0, 0, 58, 20)
        pill.center = (52, 200)
        pygame.draw.rect(s, (40, 46, 80), pill, border_radius=10)
        pygame.draw.rect(s, (150, 160, 200), pill, 2, border_radius=10)
        img = r.text("START", 10, WHITE, shadow=False)
        s.blit(img, img.get_rect(center=(pill.centerx, pill.centery + 1)))
        img = r.text("START: PAUSE", 15, WHITE)
        s.blit(img, img.get_rect(midleft=(112, 200)))
        return s

