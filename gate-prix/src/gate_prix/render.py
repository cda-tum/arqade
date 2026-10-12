"""Everything on screen: the race views, the HUD, the banners and the menus (basic; the
look file's polish comes in Task 6).

- 2 players: two 960x270 views, P1 on top. 1 player: one 960x540 view. The attract race
  behind the title is drawn as a 2-player race (bots driving both players' cars).
- Each view is a `RoadView` of the track from behind its own car, with the arches, the
  item boxes, every car and the SPLIT clones (translucent) as sprites.
- The HUD, per view: the circuit overlay top left (the TARGET wire, a window of the next
  gates with the next one outlined, and the YOU wire under it with ✓ and ✗), the place and
  the lap top right, the streak and LIGHT-SPEED BOOST, and the held item.
- Banners: the CIRCUIT CHECK (the two circuits' first 16 slots, wrong ones marked), LAP 2,
  FINISH; the 3-2-1-GO countdown; the title, pause and result screens.

Nothing is rendered per frame that hasn't changed: text goes through a cache, the gate
boxes, overlays, speed lines and the title's backdrop are drawn once. The sprite cache
and the backgrounds are built when the Renderer is (at start-up, behind a loading screen).
"""

from __future__ import annotations

import math
import random

import pygame

from gate_prix import config, track
from gate_prix.circuit import GATES
from gate_prix.match import COUNTDOWN, PAUSED, RACE, RESULT, TITLE, Match
from gate_prix.race import Race
from gate_prix.road import RoadView
from gate_prix.sprites import Background, SpriteCache, font, mix

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
WHITE = (255, 255, 255)
INK = (8, 8, 20)
PANEL = (8, 10, 24)
LABEL = (190, 200, 230)
SOFT = (200, 210, 235)
CYAN = (150, 230, 255)
OK = (60, 200, 110)
BAD = (230, 60, 70)
EMPTY = (70, 74, 96)
GHOST_TEXT = (170, 230, 255)  # the SPLIT clone's pale cyan
BOX = 20  # a gate box on the HUD's wires, px
STEP = 26  # from one gate box to the next
WINDOW = 8  # gates shown on the wires
SMALL = 14  # the CIRCUIT CHECK's and the results' gate boxes
ORDINALS = ("1st", "2nd", "3rd", "4th", "5th", "6th")
NAMES = {"p1": "P1", "p2": "P2"}


def ordinal(n: int) -> str:
    return ORDINALS[n - 1] if 1 <= n <= len(ORDINALS) else f"{n}th"


def race_time(t: float | None) -> str:
    if t is None:
        return "-"
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:05.2f}"


def window_start(filled: int) -> int:
    """The first slot the HUD's wires show: the last two decided ones stay in view."""
    return max(0, min(config.SLOTS - WINDOW, filled - 2))


def _alpha(size, rgba, radius=0):
    s = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(s, rgba, s.get_rect(), border_radius=radius)
    return s


class Renderer:
    def __init__(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self.cache = SpriteCache.shared()
        self.views = {1: [RoadView((0, 0, W, H))],
                      2: [RoadView((0, 0, W, H // 2)), RoadView((0, H // 2, W, H // 2))]}
        Background.for_size((W, H))
        Background.for_size((W, H // 2))
        self._text: dict[tuple, pygame.Surface] = {}
        self._sprites: list = []
        self._arches: tuple[int, list] = (0, [])
        self._boxes = self._gate_boxes(BOX)
        self._small = self._gate_boxes(SMALL)
        self._speed = {h: self._speed_lines(h) for h in (H, H // 2)}
        self._shade = {a: _alpha((W, H), (*INK, a)) for a in (110, 170, 215)}
        self._panels: dict[tuple, pygame.Surface] = {}
        self._backdrop = self._title_backdrop()
        self.frame = 0

    # --- Cached pieces -----------------------------------------------------------------------

    def text(self, s: str, px: int, col=WHITE, shadow: bool = True) -> pygame.Surface:
        key = (s, px, col, shadow)
        img = self._text.get(key)
        if img is None:
            if len(self._text) > 600:
                self._text.clear()
            face = font(px)
            fg = face.render(s, True, col)
            if shadow:
                d = max(1, px // 12)
                img = pygame.Surface((fg.get_width() + d, fg.get_height() + d), pygame.SRCALPHA)
                img.blit(face.render(s, True, INK), (d, d))
                img.blit(fg, (0, 0))
            else:
                img = fg
            self._text[key] = img
        return img

    def put(self, s: str, px: int, col=WHITE, shadow=True, **anchor) -> pygame.Rect:
        """Blit cached text with its rect anchored, e.g. center=(x, y) or midleft=(x, y)."""
        img = self.text(s, px, col, shadow)
        r = img.get_rect(**anchor)
        self.surface.blit(img, r)
        return r

    def panel(self, w: int, h: int, edge=None, alpha: int = 200) -> pygame.Surface:
        key = (w, h, edge, alpha)
        if key not in self._panels:
            s = _alpha((w, h), (*PANEL, alpha), 8)
            if edge is not None:
                pygame.draw.rect(s, edge, s.get_rect(), 2, border_radius=8)
            self._panels[key] = s
        return self._panels[key]

    def _gate_boxes(self, size: int) -> dict[tuple, pygame.Surface]:
        """Every gate box the HUD draws, at 2x and smoothed down: (gate or None, state),
        state one of plain, dim, next, ok, bad. Each is (size + 8) square, centred."""
        out = {}
        ss = 2
        full = (size + 8) * ss
        for gate in (*GATES, None):
            for state in ("plain", "dim", "next", "ok", "bad"):
                s = pygame.Surface((full, full), pygame.SRCALPHA)
                o = 4 * ss
                b = size * ss
                col = config.GATE_COLORS[gate] if gate else EMPTY
                if state == "next":
                    for k in range(4 * ss, 0, -1):
                        a = round(110 * (1 - k / (4 * ss)))
                        pygame.draw.rect(s, (*col, a), (o - k, o - k, b + 2 * k, b + 2 * k),
                                         border_radius=6 * ss)
                pygame.draw.rect(s, (14, 16, 30), (o, o, b, b), border_radius=4 * ss)
                fill = mix(col, (14, 16, 30), 0.65) if state == "dim" else col
                pygame.draw.rect(s, fill, (o + 2 * ss, o + 2 * ss, b - 4 * ss, b - 4 * ss),
                                 border_radius=3 * ss)
                if gate:
                    ink = (170, 170, 190) if state == "dim" else WHITE
                    letter = font(round(size * 0.62 * ss)).render(gate, True, ink)
                    s.blit(letter, letter.get_rect(center=(full // 2, full // 2 + ss)))
                if state == "next":
                    pygame.draw.rect(s, WHITE, (o - 2 * ss, o - 2 * ss, b + 4 * ss, b + 4 * ss),
                                     2 * ss, border_radius=5 * ss)
                if state in ("ok", "bad"):
                    c = (o + b - 2 * ss, o + 2 * ss)
                    r = max(3, size // 3) * ss
                    pygame.draw.circle(s, OK if state == "ok" else BAD, c, r)
                    mark = font(round(r * 1.5)).render("✓" if state == "ok" else "✗", True, WHITE)
                    s.blit(mark, mark.get_rect(center=c))
                out[(gate, state)] = pygame.transform.smoothscale(s, (size + 8, size + 8))
        return out

    def _speed_lines(self, h: int) -> pygame.Surface:
        """The light-speed streaks around the horizon, for a view h high."""
        s = pygame.Surface((W, h), pygame.SRCALPHA)
        rnd = random.Random(7)
        cx, cy = W / 2, h * config.HORIZON
        k = h / 270
        for _ in range(48):
            a = rnd.uniform(0, 2 * math.pi)
            r0 = rnd.uniform(260, 380)
            r1 = r0 + rnd.uniform(60, 160)
            p0 = (cx + r0 * math.cos(a), cy + r0 * 0.45 * k * math.sin(a))
            p1 = (cx + r1 * math.cos(a), cy + r1 * 0.45 * k * math.sin(a))
            pygame.draw.line(s, (150, 220, 255, 110), p0, p1, 2)
        s.set_alpha(255, pygame.RLEACCEL)
        return s

    def _title_backdrop(self) -> pygame.Surface:
        """The title's picture when no attract race runs: the grid of a race, a gate row
        ahead."""
        race = Race(0, 1)
        view = RoadView((0, 0, W, H))
        surf = pygame.Surface((W, H))
        cam_z = race.rows[0].z - config.TOP_SPEED * 1.4
        objects = track.arch_objects(race.rows) + race.box_objects()
        objects.append((cam_z + config.CAR_AHEAD, 0.0, "car:p1"))
        objects.append((cam_z + config.CAR_AHEAD + 2500, 0.45, "car:p2"))
        view.draw(surf, race.track, cam_z, 0.0, self._sprites, objects)
        view.draw_sprites(surf, self._sprites, self.cache)
        return surf

    def _arch_objects(self, race: Race) -> list:
        if self._arches[0] != id(race):
            self._arches = (id(race), track.arch_objects(race.rows))
        return self._arches[1]

    # --- The frame ---------------------------------------------------------------------------

    def draw(self, match: Match) -> None:
        self.frame += 1
        state = match.state
        if state == TITLE:
            if match.race is not None:
                self._race(match, hud=False)
                self.surface.blit(self._shade[110], (0, 0))
            else:
                self.surface.blit(self._backdrop, (0, 0))
                self.surface.blit(self._shade[110], (0, 0))
            self._title(match)
            return
        self._race(match, hud=True)
        if state == COUNTDOWN or (state == PAUSED and match.countdown):
            self._countdown(match)
        elif state == RACE and match.race.time < config.GO_TIME:
            self._centre_text(match, "GO!", 72, (120, 240, 140))
        if state == PAUSED:
            self._pause(match)
        elif state == RESULT:
            self._result(match)

    def _race(self, match: Match, hud: bool) -> None:
        race = match.race
        views = self.views[race.players]
        objects = (self._arch_objects(race) + race.box_objects() + race.car_objects()
                   + race.clone_objects())
        for view, racer in zip(views, race.racers):
            car = racer.car
            view.draw(self.surface, race.track, car.z - config.CAR_AHEAD, car.x, self._sprites,
                      objects)
            view.draw_sprites(self.surface, self._sprites, self.cache)
            if car.boost > 0:
                self.surface.blit(self._speed[view.height], view.rect.topleft)
            if hud and match.state != RESULT:
                self._hud(match, view.rect, racer)
        if race.players == 2:
            pygame.draw.line(self.surface, INK, (0, H // 2), (W, H // 2), 4)
            pygame.draw.line(self.surface, (200, 205, 225), (0, H // 2 - 1), (W, H // 2 - 1), 1)

    # --- The HUD -----------------------------------------------------------------------------

    def _hud(self, match: Match, rect: pygame.Rect, racer) -> None:
        surf = self.surface
        car_id = racer.car.id
        col = config.PLAYER_COLORS[car_id]
        x, y = rect.topleft
        circuit = racer.circuit
        filled = circuit.filled
        start = window_start(filled)
        x0 = x + 66
        surf.blit(self.panel(274, 70, mix(col, WHITE, 0.2)), (x + 12, y + 8))
        self.put("TARGET", 9, LABEL, midleft=(x + 20, y + 22))
        self.put("YOU", 9, LABEL, midleft=(x + 20, y + 54))
        for i in range(start, start + WINDOW):
            bx = x0 + STEP * (i - start)
            state = "dim" if i < filled else "next" if i == filled else "plain"
            surf.blit(self._boxes[(circuit.target[i], state)], (bx - 4, y + 12 - 4))
            if i < filled:
                ok = circuit.results[i]
                surf.blit(self._boxes[(circuit.slots[i], "ok" if ok else "bad")], (bx - 4, y + 44 - 4))
        # the place, the lap, the streak, the item
        self.put(ordinal(racer.place), 30, WHITE, center=(x + W - 70, y + 32))
        lap = "FINISHED" if racer.finished else f"LAP {racer.lap}/{config.LAPS}"
        self.put(lap, 12, SOFT, center=(x + W - 70, y + 60))
        if circuit.streak:
            self.put(f"STREAK x{circuit.streak}", 15, CYAN, center=(x + W - 200, y + 26))
        if racer.car.boost > 0:
            self.put("LIGHT-SPEED BOOST", 9, CYAN, center=(x + W - 200, y + 46))
        bx, by = x + W - 322, y + 10
        surf.blit(self.panel(56, 56, mix(col, WHITE, 0.3), 230), (bx, by))
        if racer.item == "SPLIT":
            for dx in (-9, 9):
                pygame.draw.circle(surf, mix(col, WHITE, 0.4), (bx + 28 + dx, by + 24), 10, 2)
            self.put("SPLIT", 9, WHITE, False, center=(bx + 28, by + 46))
        elif racer.item == "QEC":
            self.put("QEC", 15, (120, 230, 160), False, center=(bx + 28, by + 22))
            self.put("FIX GATE", 8, WHITE, False, center=(bx + 28, by + 43))
        else:
            self.put("ITEM", 8, (110, 116, 140), False, center=(bx + 28, by + 28))
        if racer.split:
            self.put(f"CLONE {racer.split_rows}", 10, GHOST_TEXT, center=(bx + 28, by + 72))
        self.put(NAMES[car_id], 18, col, bottomleft=(x + 14, y + rect.height - 8))
        self._banners(match, rect, racer)

    def _banners(self, match: Match, rect: pygame.Rect, racer) -> None:
        p = racer.car.id
        cx = rect.centerx
        check = match.banner(p, "check")
        if check is not None:
            self._check(rect, racer, check.value)
        lap = match.banner(p, "lap")
        if lap is not None:
            self.put(f"LAP {lap.value}", 30, WHITE, center=(cx, rect.y + 44))
        done = match.banner(p, "finish")
        if done is not None:
            cy = rect.y + rect.height * 0.32
            self.put("FINISH!", 44, (255, 230, 120), center=(cx, cy))
            self.put(ordinal(done.value) + " PLACE", 20, WHITE, center=(cx, cy + 40))
            waiting = [q for q in match.players if not match.race.racer(q).finished]
            if waiting and match.over_time is None:
                self.put(f"WAITING FOR {NAMES[waiting[0]]}", 12, SOFT, center=(cx, cy + 66))

    def _check(self, rect: pygame.Rect, racer, distance: int) -> None:
        """CIRCUIT CHECK: the target's first 16 slots over the car's, the wrong ones marked."""
        n = config.CHECK_SLOTS
        w, h = 17 * n + 24, 116
        x, y = rect.centerx - w // 2, rect.y + 6
        self.surface.blit(self.panel(w, h, (255, 230, 120)), (x, y))
        cx = rect.centerx
        self.put("CIRCUIT CHECK - FINAL LAP", 12, (255, 230, 120), center=(cx, y + 14))
        if distance == 0:
            self.put("PERFECT CIRCUIT!", 20, (120, 240, 140), center=(cx, y + 36))
        else:
            word = "GATE" if distance == 1 else "GATES"
            self.put(f"{distance} WRONG {word}", 20, WHITE, center=(cx, y + 36))
        c = racer.circuit
        x0 = cx - 17 * n // 2
        for i in range(n):
            bx = x0 + 17 * i
            self.surface.blit(self._small[(c.target[i], "plain")], (bx - 4, y + 52 - 4))
            ok = c.slots[i] is not None and c.slots[i] == c.target[i]
            self.surface.blit(self._small[(c.slots[i], "ok" if ok else "bad")], (bx - 4, y + 70 - 4))
        boost, seconds = config.check_boost(distance)
        self.put(f"+{boost:.0%} BOOST FOR {seconds:.1f} S", 10, CYAN, center=(cx, y + 101))

    def _countdown(self, match: Match) -> None:
        n = match.countdown
        self._centre_text(match, str(n), 80, (255, 230, 120))

    def _centre_text(self, match: Match, s: str, px: int, col) -> None:
        for view in self.views[match.race.players]:
            self.put(s, px, col, center=(view.rect.centerx, view.rect.y + view.rect.height * 0.42))

    # --- Screens -----------------------------------------------------------------------------

    def _title(self, match: Match) -> None:
        cx = W // 2
        self.put("GATE PRIX", 78, WHITE, center=(cx, 128))
        self.put("STEER THROUGH THE GLOWING GATE TO BUILD THE TARGET CIRCUIT", 14, SOFT,
                 center=(cx, 188))
        for i, (label, col) in enumerate((("1 PLAYER", config.PLAYER_COLORS["p1"]),
                                          ("2 PLAYERS", config.PLAYER_COLORS["p2"]))):
            y = 270 + 48 * i
            chosen = match.mode == i + 1
            if chosen:
                self.surface.blit(self.panel(300, 42, col, 220), (cx - 150, y - 21))
                self.put("▶", 18, col, center=(cx - 120, y))
            self.put(label, 26, WHITE if chosen else (150, 156, 180), center=(cx, y))
        if (self.frame // 30) % 2 == 0:
            self.put("PRESS START", 24, (255, 230, 120), center=(cx, 410))
        self.surface.blit(self.panel(640, 58, None, 190), (cx - 320, 443))  # over the car
        self.put("STICK: CHOOSE   A OR START: RACE", 14, SOFT, center=(cx, 458))
        self.put("IN THE RACE   STICK: STEER   PULL BACK: BRAKE   A: USE ITEM   START: PAUSE",
                 12, LABEL, center=(cx, 486))
        if match.attract:
            self.put("DEMO", 14, LABEL, topright=(W - 16, 12))

    def _pause(self, match: Match) -> None:
        self.surface.blit(self._shade[170], (0, 0))
        w, h = 340, 196
        x, y = (W - w) // 2, (H - h) // 2
        self.surface.blit(self.panel(w, h, (200, 205, 225), 230), (x, y))
        self.put("PAUSED", 30, WHITE, center=(W // 2, y + 34))
        for i, item in enumerate(config.PAUSE_ITEMS):
            iy = y + 88 + 40 * i
            chosen = i == match.pause_index
            if chosen:
                self.put("▶", 18, (255, 230, 120), center=(x + 50, iy))
            self.put(item, 22, WHITE if chosen else (150, 156, 180), center=(W // 2, iy))
        self.put("A: PICK   B OR START: RESUME", 11, LABEL, center=(W // 2, y + h - 18))

    def _result(self, match: Match) -> None:
        surf = self.surface
        surf.blit(self._shade[215], (0, 0))
        cx = W // 2
        self.put("RESULTS", 34, WHITE, center=(cx, 34))
        rows = match.results or []
        for i, row in enumerate(rows):
            y = 76 + 27 * i
            col = config.CAR_COLORS[row.car]
            bright = row.player
            self.put(ordinal(row.place), 18, WHITE if bright else SOFT, midright=(250, y))
            pygame.draw.rect(surf, col, (268, y - 9, 30, 18), border_radius=4)
            pygame.draw.rect(surf, (150, 156, 180), (268, y - 9, 30, 18), 1, border_radius=4)
            name = NAMES[row.car] if row.player else "CPU " + row.car.upper()
            self.put(name, 18, col if bright else SOFT, midleft=(312, y))
            self.put(race_time(row.time), 16, WHITE if bright else SOFT, midleft=(470, y))
            gates = f"{row.right}/{config.SLOTS} GATES"
            self.put(gates, 16, (255, 230, 120) if bright else (150, 156, 180), midleft=(590, y))
        players = [r for r in rows if r.player]
        y = 260
        for row in players:
            self._circuit_rows(match, row, y)
            y += 104
        if match.t >= config.RESULT_LOCK:
            self.put("A: REMATCH        B: TITLE", 18, (255, 230, 120), center=(cx, H - 24))

    def _circuit_rows(self, match: Match, row, y: int) -> None:
        """A player's whole circuit under the target's, with its accuracy."""
        target = match.race.target  # the row's own circuit is frozen at the finish
        col = config.PLAYER_COLORS[row.car]
        w = 18 * config.SLOTS + 150
        x = (W - w) // 2
        self.surface.blit(self.panel(w, 94, col), (x, y))
        self.put(NAMES[row.car], 22, col, midleft=(x + 14, y + 26))
        acc = row.right / config.SLOTS
        self.put(f"{acc:.0%}", 16, WHITE, midleft=(x + 14, y + 54))
        check = "-" if row.check is None else f"CHECK {row.check}"
        self.put(check, 10, LABEL, midleft=(x + 14, y + 76))
        self.put("TARGET", 9, LABEL, midleft=(x + 70, y + 26))
        self.put("YOU", 9, LABEL, midleft=(x + 70, y + 56))
        x0 = x + 120
        for i in range(config.SLOTS):
            bx = x0 + 18 * i
            self.surface.blit(self._small[(target[i], "plain")], (bx - 4, y + 18 - 4))
            if row.results[i] is not None:
                state = "ok" if row.results[i] else "bad"
                self.surface.blit(self._small[(row.slots[i], state)], (bx - 4, y + 48 - 4))


def loading_screen(surface: pygame.Surface) -> None:
    """Shown while the sprites are drawn at start-up."""
    surface.fill((10, 14, 34))
    for s, px, y in (("GATE PRIX", 64, H // 2 - 30), ("LOADING...", 18, H // 2 + 40)):
        img = font(px).render(s, True, WHITE)
        surface.blit(img, img.get_rect(center=(W // 2, y)))
