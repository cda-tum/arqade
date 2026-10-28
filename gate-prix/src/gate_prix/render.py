"""Everything on screen: the race views, the HUD, the banners, the effects and the menus.

- 2 players: two 480x540 views side by side, P1 on the left, P2 on the right, a thin
  divider between (each projects the road VIEW_2P_SPREAD wide, so nothing is squeezed).
  1 player: one 960x540 view. The attract race behind the title (bots only) is drawn in
  two views as well, following two of its bots (`match.viewed`).
- Each view is a `RoadView` of the track from behind its own car, with the arches, the
  item boxes, the start and finish gantry over the chequered lap line (drawn at its exact
  size, gantry.py; its five start lights red one by one in the countdown, all green from
  GO), every car, their exhaust flames while they boost and the SPLIT clones
  (translucent) as sprites, and a bouncing marker over every right arch. The people's cars
  (P1 blue, P2 red) have a white outline, so you find your own among the bots' neutral ones
  (sprites.py; the attract race has no people, so nobody is outlined). Every car carries
  its qubit on its engine cover: an orb in its state's colour, its Bloch arrow pointing
  where the car's circuit so far has put |0> (bloch.py; drawn just after the car, moved
  with its tilt). A drifting car is
  tilted, with sparks at its rear wheels (white, blue at charge 1, gold at 2) and the
  mini-turbo's flash as it lets go; a tunnelling car is a see-through shimmer. MEASURE
  shots fly as gold orbs on a beam from their shooter, DECOHERENCE clouds sit on the road,
  and each racer's own noise storm (its static clouds and bit-flip mines) shows in its own
  view only.
- **The HUD**, per view:
  - top left, one big NEXT GATE badge and under it a dot per slot, 16 in all (in a narrow
    2P view two rows of 8, a lap each): ✓ green, ✗ red, the next one ringed. Past the last
    row "TO THE LINE", and on the final lap "FINAL LAP: NO GATES", with a flag;
  - top right, the place and the lap, and under them (1P: beside them), while an item is
    held, its slot pulsing with the item's icon, its name and A (in 1P also one line on
    what it does), and ITEM FULL, its edge flashing red, when a box gave nothing new;
  - while a racer is `blind` (a DECOHERENCE cloud), its NEXT GATE badge is static and says
    NO SIGNAL, and the ▼ over the right arch is left out;
  - near the car, each row's flash: RIGHT GATE +BOOST, WRONG GATE or MISSED, and a box's
    item popping up over the car as it is taken;
  - PRESS A TO USE SPLIT on the first pickup of each item (in its own place, never over a
    flash), LAP 2/3, FINAL LAP with STORM AHEAD (after the check's freeze), FINISH;
  - the minimap: bottom left in 1P, and one map for both, straddling the divider at the
    bottom, in 2P; every car's dot is labelled (P1, P2, CPU1 ...).
- The HOW TO PLAY card (`tutorial.TutorialCard`) before every match begun from the title.
- **The CIRCUIT CHECK**: for CHECK_FREEZE seconds after a player crosses into the final
  lap, their view is a still of the moment they crossed, under the comparison panel
  ("14/16 GATES CORRECT", the wrong ones marked); the other view runs on. Then the LIGHT
  SPEED! warp: a star-streak tunnel, the field of view widening and a tint at the edges,
  fading out over the check's boost.
- **Speed you can feel:** speed lines from SPEED_LINES_AT of the top speed (stronger while
  boosting), a slight camera shake at speed, and the field of view widening with speed
  above the top (a projection constant and the camera pulled in: `RoadView.draw`'s depth
  and ahead), plus the exhaust flames.
- The 3-2-1-GO countdown; the title (the logo's GATE PRIX wordmark over PLAYERS / BOTS /
  LEVEL / QUIT, each value between arrows, dimmed at its end), pause and the results: the
  places (the bots named CPU1, CPU2 ...), and per player the accuracy and the check, the
  circuit under the target's with a ✓ or ✗ row of its own, and the final state on a Bloch
  sphere beside the target's.

Nothing is scaled per frame and no text is rendered twice: text goes through a cache, and
the gate badges, dots, panels, speed lines, tunnel, tint, markers, start lights, item icons,
the minimap's outline, the HOW TO PLAY card's pieces, the title's backdrop and wordmark and
the results' gate boxes and Bloch spheres are drawn once, at start-up (behind the loading
screen), as are the sprite cache (with its tilted and tunnelling cars and the qubit's orbs)
and the backgrounds; the gantry is drawn at its exact size from fills and its own
pre-rendered pieces (gantry.py). Per frame the effects are blits of those (and one copy of
a view, when a freeze starts). The text cache is an LRU of TEXT_CACHE renders.
"""

from __future__ import annotations

import math
import random
from collections import OrderedDict

import pygame
from arqade_common.input import KEYBOARD, PLAYERS, LastDevice

from gate_prix import bloch, config, icons, sprites, track, wordmark
from gate_prix.circuit import GATES
from gate_prix.gantry import Gantry
from gate_prix.match import COUNTDOWN, HOWTO, PAUSED, RACE, RESULT, TITLE, Match
from gate_prix.minimap import Minimap
from gate_prix.race import Race
from gate_prix.road import RoadView
from gate_prix.sprites import Background, SpriteCache, font, mix
from gate_prix.tutorial import TutorialCard

W, H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
TOP = config.TOP_SPEED
WHITE = (255, 255, 255)
INK = (8, 8, 20)
PANEL = (8, 10, 24)
LABEL = (190, 200, 230)
SOFT = (200, 210, 235)
CYAN = (150, 230, 255)
GOLD = (255, 230, 120)
OK = (60, 200, 110)
BAD = (230, 60, 70)
EMPTY = (70, 74, 96)
GHOST_TEXT = (170, 230, 255)  # the SPLIT clone's pale cyan
FULL = (255, 96, 104)  # ITEM FULL
FLASHES = {  # a row's outcome, near the car
    "right": ("RIGHT GATE +BOOST", (110, 190, 255)),
    "wrong": ("WRONG GATE", (255, 90, 96)),
    "miss": ("MISSED", (255, 186, 90)),
}
ITEM_LINES = {
    "SPLIT": "SPLIT: a clone takes a second gate",
    "QEC": "QEC: fixes your last wrong gate",
    "MEASURE": "MEASURE: collapses the car ahead",
    "TUNNEL": "TUNNEL: through cars and hazards",
    "DECOHERENCE": "drops a noise cloud behind you",
}
ITEM_COLORS = {"SPLIT": GHOST_TEXT, "QEC": (120, 230, 160), "MEASURE": (255, 200, 90),
               "TUNNEL": (200, 170, 255), "DECOHERENCE": (180, 160, 210)}
BADGE = 56  # the NEXT GATE badge, px
DOT = 12  # a slot's dot under it
DOT_STEP = 13
SMALL = 14  # the CIRCUIT CHECK's gate boxes
RESULT_BOX = 18  # the results' gate boxes, every RESULT_STEP px, a lap's gap between laps
RESULT_STEP = 23
RESULT_LAP_GAP = 10
RESULT_PANEL = (900, 120)  # a player's panel on the results
SPHERE = 78  # the results' Bloch spheres, px
WORDMARK = 560  # the title's GATE PRIX, px wide
PULSE = 8  # the held item's slot pulses through this many pre-drawn steps
LINE_FRAMES = 4  # speed lines and the tunnel are animated over this many pre-drawn frames
TINTS = (70, 130, 190)  # the warp's edge tint, by strength
VIEW_W, VIEW_H = config.VIEW_2P  # a 2P view
SIZES = ((W, H), (VIEW_W, VIEW_H))  # every view size
ICON = 44  # the item slot's icon, px
TIP_ICON = 30
REVEAL_ICONS = (24, 34, 44, 52, 56)  # a box's item popping up: growing over these sizes
MAP = (170, 118)  # the minimap's box
TILT = 0.45  # a drifting car's tilt, as a share of its slide's angle (20 degrees: 9)
STORM = (200, 170, 255)  # STORM AHEAD's violet
SHOT = (255, 200, 90)
TEXT_CACHE = 600  # rendered texts kept (least recently used dropped first)
ORDINALS = ("1st", "2nd", "3rd", "4th", "5th", "6th")
NAMES = {"p1": "P1", "p2": "P2"}
KEYBOARD_STICKS = {"p1": "WASD", "p2": "ARROWS"}  # the keys that stand in for each stick


LEVEL_LINES = {
    "EASY": "EASY BOTS: FOR YOUR FIRST RACE",
    "TOUGH": "TOUGH BOTS: YOU WILL HAVE TO WORK FOR IT",
    "BRUTAL": "BRUTAL BOTS: NEAR PERFECT",
}


def title_rows(match: Match) -> list[tuple[str, str | None, bool, bool]]:
    """The title's rows as (label, value, at its low end, at its high end); QUIT's value
    is None."""
    levels = config.LEVELS
    return [
        ("PLAYERS", str(match.mode), match.mode == 1, match.mode == config.MAX_PLAYERS),
        ("BOTS", str(match.bot_count), match.bot_count == 0,
         match.bot_count == match.max_bots()),
        ("LEVEL", match.level, match.level == levels[0], match.level == levels[-1]),
        ("QUIT", None, True, True),
    ]


def field_line(match: Match) -> str:
    """What the rows add up to, under them."""
    if match.bot_count == 0:
        return "A DUEL: JUST THE TWO OF YOU" if match.mode == 2 else "A TIME TRIAL: JUST YOU"
    return LEVEL_LINES[match.level]


def ordinal(n: int) -> str:
    return ORDINALS[n - 1] if 1 <= n <= len(ORDINALS) else f"{n}th"


def race_time(t: float | None) -> str:
    if t is None:
        return "-"
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:05.2f}"


def _alpha(size, rgba, radius=0):
    s = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(s, rgba, s.get_rect(), border_radius=radius)
    return s


def _veil(size, rgb, alpha: int) -> pygame.Surface:
    """A shade of one colour over the whole screen: one alpha for the surface rather than
    one per pixel. It looks the same and blits 6x faster in the browser (960x540: 2 ms
    rather than 13 ms a frame under WebAssembly)."""
    s = pygame.Surface(size)
    s.fill(rgb)
    s.set_alpha(alpha)
    return s


def warp_level(race: Race, racer) -> float:
    """How strong the LIGHT SPEED! warp is now: 1 as the check's boost starts, fading to 0
    as it ends (0 when there is none)."""
    if racer.warp_time is None or not racer.check_boost:
        return 0.0
    seconds = racer.check_boost[1]
    t = race.time - racer.warp_time
    return max(0.0, 1.0 - t / seconds) if seconds > 0 else 0.0


def fov(speed: float, warp: float) -> float:
    """The field of view's widening (1 = normal) at a speed (world units a second)."""
    extra = max(0.0, speed / TOP - 1.0)
    return min(config.FOV_MAX, 1.0 + config.FOV_BOOST * extra + config.FOV_WARP * warp)


def shake(speed: float, frame: int, seed: int) -> float:
    """The camera's height jitter (world units): nothing below 90% of the top speed, SHAKE
    at the top speed, up to SHAKE_BOOST at +100%."""
    f = speed / TOP
    if f < 0.9:
        return 0.0
    amp = config.SHAKE * min(1.0, (f - 0.9) / 0.1)
    amp += (config.SHAKE_BOOST - config.SHAKE) * min(1.0, max(0.0, f - 1.0))
    wobble = 0.6 * math.sin(frame * 1.9 + seed) + 0.4 * math.sin(frame * 3.7 + 2 * seed)
    return amp * wobble


class Renderer:
    def __init__(self, surface: pygame.Surface, devices: LastDevice | None = None) -> None:
        self.surface = surface
        # Who last used their keys or their pad, so the hints name what they're holding.
        self.devices = devices or LastDevice()
        self.cache = SpriteCache.shared()
        spread = config.VIEW_2P_SPREAD
        self.views = {1: [RoadView((0, 0, W, H))],
                      2: [RoadView((0, 0, VIEW_W, VIEW_H), spread=spread),
                          RoadView((W - VIEW_W, 0, VIEW_W, VIEW_H), spread=spread)]}
        for size in SIZES:
            Background.for_size(size)
        self._text: OrderedDict[tuple, pygame.Surface] = OrderedDict()
        self._sprites: list = []
        self._arches: tuple[Race | None, list] = (None, [])
        self._small = self._gate_boxes(SMALL)
        self._result_boxes = self._gate_boxes(RESULT_BOX)
        self._spheres = {name: bloch.sphere(name, SPHERE, font) for name in bloch.NAMES}
        self._badges = self._next_badges()
        self._dots = self._slot_dots()
        self._lines = {(size, strong): [self._speed_lines(size, k, strong) for k in range(LINE_FRAMES)]
                       for size in SIZES for strong in (False, True)}
        self._tunnel = {size: [self._tunnel_frame(size, k) for k in range(LINE_FRAMES)]
                        for size in SIZES}
        self._tint = {size: [self._edge_tint(size, a) for a in TINTS] for size in SIZES}
        self._shade = {a: _veil((W, H), INK, a) for a in (110, 150, 170, 215)}
        self._panels: dict[tuple, pygame.Surface] = {}
        self._buttons: dict[str, list[pygame.Surface]] = {}  # the A button's pulse, by its name
        self.a_button("A")
        self._markers = sprites.markers()
        self._frozen: dict[str, tuple[Race, pygame.Surface]] = {}  # player: (race, still)
        self._blind = self._blind_badge()
        self.gantry = Gantry.shared()  # drawn at its exact size: gantry.py
        icons.build((ICON, TIP_ICON, *REVEAL_ICONS))
        self._gantries = [(n * track.fridge().lap_length(), 0.0, "gantry")
                          for n in range(config.LAPS + 1)]
        self._backdrop = self._title_backdrop()
        self._wordmark = wordmark.build(WORDMARK)
        self.howto = TutorialCard(self)
        self._in_howto = False
        self.frame = 0

    # --- Cached pieces -----------------------------------------------------------------------

    def text(self, s: str, px: int, col=WHITE, shadow: bool = True) -> pygame.Surface:
        """The text, rendered once: an LRU cache of TEXT_CACHE renders, so a long session's
        changing texts (times, names) never grow it, and what is drawn every frame stays."""
        key = (s, px, col, shadow)
        cache = self._text
        img = cache.get(key)
        if img is not None:
            cache.move_to_end(key)
            return img
        while len(cache) >= TEXT_CACHE:
            cache.popitem(last=False)
        face = font(px)
        fg = face.render(s, True, col)
        if shadow:
            d = max(1, px // 12)
            img = pygame.Surface((fg.get_width() + d, fg.get_height() + d), pygame.SRCALPHA)
            img.blit(face.render(s, True, INK), (d, d))
            img.blit(fg, (0, 0))
        else:
            img = fg
        cache[key] = img
        return img

    def put(self, s: str, px: int, col=WHITE, shadow=True, **anchor) -> pygame.Rect:
        """Blit cached text with its rect anchored, e.g. center=(x, y) or midleft=(x, y)."""
        img = self.text(s, px, col, shadow)
        r = img.get_rect(**anchor)
        self.surface.blit(img, r)
        return r

    def put_fit(self, s: str, px: int, width: int, col=WHITE, **anchor) -> pygame.Rect:
        """`put`, a size or two smaller if the text is wider than `width` (the keyboard's
        key names are longer than the pad's buttons)."""
        while px > 9 and self.text(s, px, col).get_width() > width:
            px -= 1
        return self.put(s, px, col, **anchor)

    # --- Button names, for the hints ------------------------------------------------------

    def name(self, action: str, player: str | None = None) -> str:
        """A control's on-screen name for one player's device ("A" on a pad, "B" or "L" on
        the keyboard), or for both players' when `player` is None ("B / L"). "stick" is
        the stick or the direction keys, "back" the stick pulled back (or its key) and
        "quit" the Start + Select combo."""
        players = (player,) if player else PLAYERS
        if action in ("stick", "back", "quit"):
            names = [self._own_name(action, p) for p in players]
            return " / ".join(dict.fromkeys(names))
        return self.devices.label(action, player) if player else self.devices.shared_label(action)

    def _own_name(self, action: str, player: str) -> str:
        pad = self.devices[player] != KEYBOARD
        if action == "stick":
            return "STICK" if pad else KEYBOARD_STICKS[player]
        if action == "back":
            return "BACK" if pad else self.devices.label("down", player)
        return f"{self.devices.label('start', player)} + {self.devices.label('select', player)}"

    def hint_player(self, match: Match, car: str) -> str:
        """Whose device a car's hints name: its player's; with one player either pad (or
        either player's keys) drives, so whoever pressed something last."""
        return self.devices.latest if match.mode == 1 else car

    def a_button(self, name: str) -> list[pygame.Surface]:
        """The held item's big button, labelled `name` (A, or its key), in its PULSE steps."""
        if name not in self._buttons:
            self._buttons[name] = [self._a_button(k / (PULSE - 1), name) for k in range(PULSE)]
        return self._buttons[name]

    def panel(self, w: int, h: int, edge=None, alpha: int = 200) -> pygame.Surface:
        key = (w, h, edge, alpha)
        if key not in self._panels:
            s = _alpha((w, h), (*PANEL, alpha), 8)
            if edge is not None:
                pygame.draw.rect(s, edge, s.get_rect(), 2, border_radius=8)
            self._panels[key] = s
        return self._panels[key]

    def _gate_boxes(self, size: int) -> dict[tuple, pygame.Surface]:
        """The small gate boxes of the check's panel and the results, at 2x and smoothed
        down: (gate or None, state), state one of plain, ok, bad. Each is (size + 8) square."""
        out = {}
        ss = 2
        full = (size + 8) * ss
        for gate in (*GATES, None):
            for state in ("plain", "ok", "bad"):
                s = pygame.Surface((full, full), pygame.SRCALPHA)
                o = 4 * ss
                b = size * ss
                col = config.GATE_COLORS[gate] if gate else EMPTY
                pygame.draw.rect(s, (14, 16, 30), (o, o, b, b), border_radius=4 * ss)
                pygame.draw.rect(s, col, (o + 2 * ss, o + 2 * ss, b - 4 * ss, b - 4 * ss),
                                 border_radius=3 * ss)
                if gate:
                    letter = font(round(size * 0.62 * ss)).render(gate, True, WHITE)
                    s.blit(letter, letter.get_rect(center=(full // 2, full // 2 + ss)))
                if state in ("ok", "bad"):
                    c = (o + b - 2 * ss, o + 2 * ss)
                    r = max(3, size // 3) * ss
                    pygame.draw.circle(s, OK if state == "ok" else BAD, c, r)
                    mark = font(round(r * 1.5)).render("✓" if state == "ok" else "✗", True, WHITE)
                    s.blit(mark, mark.get_rect(center=c))
                out[(gate, state)] = pygame.transform.smoothscale(s, (size + 8, size + 8))
        return out

    def _next_badges(self) -> dict[str, pygame.Surface]:
        """The big NEXT GATE badge of each gate (glowing, its letter large), and "flag" for
        the gate-free final lap. Each is BADGE + 16 square."""
        out = {}
        ss = 2
        full = (BADGE + 16) * ss
        o, b = 8 * ss, BADGE * ss
        for gate in (*GATES, "flag"):
            s = pygame.Surface((full, full), pygame.SRCALPHA)
            col = config.GATE_COLORS.get(gate, GOLD)
            for k in range(8 * ss, 0, -1):
                a = round(150 * (1 - k / (8 * ss)) ** 1.5)
                pygame.draw.rect(s, (*col, a), (o - k, o - k, b + 2 * k, b + 2 * k),
                                 border_radius=12 * ss)
            pygame.draw.rect(s, (14, 16, 30), (o, o, b, b), border_radius=9 * ss)
            inner = pygame.Rect(o + 3 * ss, o + 3 * ss, b - 6 * ss, b - 6 * ss)
            if gate == "flag":  # a chequered flag: no more gates
                pygame.draw.rect(s, WHITE, inner, border_radius=6 * ss)
                n = 5
                cell = inner.w / n
                for i in range(n):
                    for j in range(n):
                        if (i + j) % 2:
                            pygame.draw.rect(s, (20, 22, 34), (round(inner.x + i * cell),
                                             round(inner.y + j * cell), math.ceil(cell),
                                             math.ceil(cell)))
            else:
                pygame.draw.rect(s, col, inner, border_radius=6 * ss)
                letter = font(round(BADGE * 0.66 * ss)).render(gate, True, WHITE)
                shadow = font(round(BADGE * 0.66 * ss)).render(gate, True, INK)
                c = (full // 2, full // 2 + ss)
                s.blit(shadow, shadow.get_rect(center=(c[0] + 2 * ss, c[1] + 2 * ss)))
                s.blit(letter, letter.get_rect(center=c))
            pygame.draw.rect(s, WHITE, (o - 2 * ss, o - 2 * ss, b + 4 * ss, b + 4 * ss),
                             2 * ss, border_radius=10 * ss)
            out[gate] = pygame.transform.smoothscale(s, (BADGE + 16, BADGE + 16))
        return out

    def _slot_dots(self) -> dict[str, pygame.Surface]:
        """A slot's dot: "ok" (green ✓), "bad" (red ✗), "next" (ringed) or "todo"."""
        out = {}
        ss = 4
        full = (DOT + 4) * ss
        c = full // 2
        r = DOT * ss // 2
        for state in ("ok", "bad", "next", "todo"):
            s = pygame.Surface((full, full), pygame.SRCALPHA)
            if state in ("ok", "bad"):
                pygame.draw.circle(s, INK, (c, c), r + ss)
                pygame.draw.circle(s, OK if state == "ok" else BAD, (c, c), r)
                mark = font(round(r * 1.5)).render("✓" if state == "ok" else "✗", True, WHITE)
                s.blit(mark, mark.get_rect(center=(c, c + ss)))
            elif state == "next":
                pygame.draw.circle(s, (40, 44, 66), (c, c), r)
                pygame.draw.circle(s, WHITE, (c, c), r + ss, 2 * ss)
            else:
                pygame.draw.circle(s, (40, 44, 66), (c, c), r - ss)
                pygame.draw.circle(s, (90, 96, 124), (c, c), r - ss, ss)
            out[state] = pygame.transform.smoothscale(s, (DOT + 4, DOT + 4))
        return out

    def _a_button(self, glow: float, name: str = "A") -> pygame.Surface:
        """The held item's big A button (labelled `name`), at one step of its pulse (0 dim
        to 1 bright)."""
        ss = 2
        d = 46
        s = pygame.Surface((d * ss, d * ss), pygame.SRCALPHA)
        c = d * ss // 2
        ring = mix((120, 120, 150), GOLD, glow)
        pygame.draw.circle(s, (*ring, round(90 + 120 * glow)), (c, c), c)
        pygame.draw.circle(s, INK, (c, c), c - 3 * ss)
        pygame.draw.circle(s, mix((210, 60, 70), (255, 110, 110), glow), (c, c), c - 5 * ss)
        letter = font((26 if len(name) == 1 else 13) * ss).render(name, True, WHITE)
        s.blit(letter, letter.get_rect(center=(c, c + ss)))
        return pygame.transform.smoothscale(s, (d, d))

    def _speed_lines(self, size, frame: int, strong: bool) -> pygame.Surface:
        """Streaks rushing out from the vanishing point towards the edges, for a view of
        this size: one of LINE_FRAMES frames, each further out than the last."""
        w, h = size
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        rnd = random.Random(7 if strong else 8)
        cx, cy = w / 2, h * config.HORIZON
        k = h / 270
        q = w / W
        for _ in range(64 if strong else 44):
            a = rnd.uniform(0, 2 * math.pi)
            phase = (rnd.random() + frame / LINE_FRAMES) % 1.0
            r0 = 300 + 260 * phase
            r1 = r0 + (90 if strong else 60) + 120 * phase
            p0 = (cx + r0 * q * math.cos(a), cy + r0 * 0.5 * k * math.sin(a))
            p1 = (cx + r1 * q * math.cos(a), cy + r1 * 0.5 * k * math.sin(a))
            alpha = round((160 if strong else 120) * (0.4 + 0.6 * phase))
            pygame.draw.line(s, (170, 225, 255, alpha), p0, p1, 3 if strong else 2)
        s.set_alpha(255, pygame.RLEACCEL)
        return s

    def _tunnel_frame(self, size, frame: int) -> pygame.Surface:
        """The warp's star-streak tunnel: long white streaks from just round the vanishing
        point out past the edges, one of LINE_FRAMES frames."""
        w, h = size
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        rnd = random.Random(11)
        cx, cy = w / 2, h * config.HORIZON
        k = h / 270
        q = w / W
        for _ in range(110):
            a = rnd.uniform(0, 2 * math.pi)
            phase = (rnd.random() + frame / LINE_FRAMES) % 1.0
            r0 = 30 + 520 * phase ** 1.6
            r1 = r0 + 40 + 260 * phase
            col = (255, 255, 255) if rnd.random() < 0.6 else (150, 200, 255)
            p0 = (cx + r0 * q * math.cos(a), cy + r0 * 0.55 * k * math.sin(a))
            p1 = (cx + r1 * q * math.cos(a), cy + r1 * 0.55 * k * math.sin(a))
            pygame.draw.line(s, (*col, round(80 + 160 * phase)), p0, p1, 1 + round(2 * phase))
        s.set_alpha(255, pygame.RLEACCEL)
        return s

    def _edge_tint(self, size, alpha: int) -> list[tuple[pygame.Surface, tuple[int, int]]]:
        """The warp's tint at the edges of a view of this size: four strips (only the edges
        are drawn per frame), violet-blue fading inwards."""
        col = (110, 80, 255)
        W, h = size
        bw, bh = round(W * 0.09), round(h * 0.13)
        strips = []
        for side in ("top", "bottom", "left", "right"):
            horizontal = side in ("top", "bottom")
            size = (W, bh) if horizontal else (bw, h)
            s = pygame.Surface(size, pygame.SRCALPHA)
            depth = bh if horizontal else bw
            for i in range(depth):
                a = round(alpha * (1 - i / depth) ** 2)
                if side == "top":
                    pygame.draw.line(s, (*col, a), (0, i), (W, i))
                elif side == "bottom":
                    pygame.draw.line(s, (*col, a), (0, bh - 1 - i), (W, bh - 1 - i))
                elif side == "left":
                    pygame.draw.line(s, (*col, a), (i, 0), (i, h))
                else:
                    pygame.draw.line(s, (*col, a), (bw - 1 - i, 0), (bw - 1 - i, h))
            s.set_alpha(255, pygame.RLEACCEL)
            pos = {"top": (0, 0), "bottom": (0, h - bh), "left": (0, 0), "right": (W - bw, 0)}
            strips.append((s, pos[side]))
        return strips

    def _blind_badge(self) -> pygame.Surface:
        """A decohered racer's NEXT GATE badge: static where the gate's letter was."""
        ss = 2
        full = (BADGE + 16) * ss
        o, b = 8 * ss, BADGE * ss
        s = pygame.Surface((full, full), pygame.SRCALPHA)
        pygame.draw.rect(s, (14, 16, 30), (o, o, b, b), border_radius=9 * ss)
        inner = pygame.Rect(o + 3 * ss, o + 3 * ss, b - 6 * ss, b - 6 * ss)
        pygame.draw.rect(s, (70, 60, 96), inner, border_radius=6 * ss)
        rnd = random.Random(13)
        for _ in range(260):
            x, y = rnd.randrange(inner.left, inner.right), rnd.randrange(inner.top, inner.bottom)
            pygame.draw.rect(s, mix((120, 110, 150), (235, 225, 255), rnd.random()), (x, y, 2 * ss, ss))
        letter = font(round(BADGE * 0.6 * ss)).render("?", True, WHITE)
        s.blit(letter, letter.get_rect(center=(full // 2, full // 2 + ss)))
        pygame.draw.rect(s, (180, 160, 210), (o - 2 * ss, o - 2 * ss, b + 4 * ss, b + 4 * ss),
                         2 * ss, border_radius=10 * ss)
        return pygame.transform.smoothscale(s, (BADGE + 16, BADGE + 16))

    def _title_backdrop(self) -> pygame.Surface:
        """The title's picture when no attract race runs: the grid of a race, under the
        gantry, a gate row ahead."""
        race = Race(0, 1)
        view = RoadView((0, 0, W, H))
        surf = pygame.Surface((W, H))
        cam_z = -2.6 * config.CAR_AHEAD
        objects = track.arch_objects(race.rows) + race.box_objects() + self._gantries
        for z, x, kind in ((cam_z + config.CAR_AHEAD, 0.0, "car:p1"),
                           (cam_z + config.CAR_AHEAD + 2600, 0.5, "car:p2")):
            objects += [(z, x, kind), (z, x, "orb:+z")]  # on the grid: |0>, no gates yet
        view.draw(surf, race.track, cam_z, 0.0, self._sprites, objects)
        self.gantry.lights = ("green", config.GANTRY_LIGHTS)
        view.draw_sprites(surf, self._sprites, self.cache)
        return surf

    def _arch_objects(self, race: Race) -> list:
        # keyed by the race itself, not its id(): a new race can reuse a freed one's id
        if self._arches[0] is not race:
            self._arches = (race, track.arch_objects(race.rows) + self._gantries)
        return self._arches[1]

    # --- The frame ---------------------------------------------------------------------------

    def draw(self, match: Match) -> None:
        self.frame += 1
        self.gantry.drawn.clear()
        state = match.state
        if state == HOWTO:
            if not self._in_howto:
                self.howto.reset()
                self._in_howto = True
            self.howto.draw(self.surface, match.mode, 1.0 / config.FPS)
            return
        self._in_howto = False
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

    def _car_kind(self, car) -> tuple[str, float]:
        """A car's sprite now: see-through while it tunnels, tilted while it drifts (and
        wobbling while it spins out). And the tilt it is drawn at, in degrees."""
        if car.tunnelling:
            return f"{car.kind}:ghost{(self.frame // 5) % sprites.GHOST_FRAMES}", 0.0
        if car.spinning:
            degrees = 8 * math.sin(self.frame * 0.7)
        else:
            degrees = math.degrees(car.drift_angle) * TILT
        kind = sprites.tilt_kind(car.kind, degrees)
        steps = max(-sprites.TILTS, min(sprites.TILTS, round(degrees / sprites.TILT_STEP)))
        return kind, steps * sprites.TILT_STEP if kind != car.kind else 0.0

    def _objects(self, race: Race) -> list:
        """Every sprite object of the race that every view shows: arches, the gantries,
        boxes, DECOHERENCE clouds, cars, clones, MEASURE shots, and just in front of each
        car its flames while it boosts, its sparks while it drifts and its mini-turbo's
        flash."""
        flick = self.frame // 3
        out = self._arch_objects(race) + race.box_objects() + race.clone_objects()
        f = (self.frame // 4) % sprites.STATIC_FRAMES
        out += [(z, x, f"deco:{(f + i) % sprites.STATIC_FRAMES}")
                for i, (z, x, _) in enumerate(race.deco_objects())]
        for i, r in enumerate(race.racers):
            car = r.car
            kind, degrees = self._car_kind(car)
            out.append((car.z, car.x, kind))
            # its qubit, at the car's own distance (so the same cached size, drawn just after
            # it), on its engine cover: moved sideways as far as the cover is by the tilt
            lean = math.sin(math.radians(degrees)) * sprites.ORB_Y
            out.append((car.z, car.x + lean, f"orb:{bloch.state_of(tuple(r.circuit.slots))}"))
            if car.boost > 0:
                out.append((car.z - 1.0, car.x, f"flame:{(flick + i) % sprites.FLAME_FRAMES}"))
            if car.drifting:
                level = car.drift_level
                out.append((car.z - 0.5, car.x, f"spark:{level}:{(flick + i) % sprites.SPARK_FRAMES}"))
            if car.turbo_flash > 0 and car.turbo_level in (1, 2):
                out.append((car.z - 1.5, car.x, f"turbo:{car.turbo_level}"))
        for shot in race.shots:
            a, b = race.racer(shot.owner).car, race.racer(shot.target).car
            k = shot.progress
            if k >= 1.0:  # waiting on its target's CIRCUIT CHECK freeze: an orb on it
                out.append((b.z - 2.0, b.x, "shot"))
            else:
                out.append((a.z + (b.z - a.z) * k, a.x + (b.x - a.x) * k, "shot"))
        return out

    def _hazards(self, race: Race, car_id: str) -> list:
        """A racer's own noise storm, for its own view only: the live hazards."""
        out = []
        f = self.frame // 4
        for i, (z, x, kind, alive) in enumerate(race.hazards_for(car_id)):
            if alive:
                if kind == "mine":
                    out.append((z, x, f"mine:{(f // 2 + i) % sprites.MINE_FRAMES}"))
                else:
                    out.append((z, x, f"static:{(f + i) % sprites.STATIC_FRAMES}"))
        return out

    def _race(self, match: Match, hud: bool) -> None:
        race = match.race
        followed = [race.racer(c) for c in match.viewed]  # the players', or two bots'
        views = self.views[len(followed)]
        objects = self._objects(race)
        for i, (view, racer) in enumerate(zip(views, followed)):
            p = racer.car.id
            mine = objects + self._hazards(race, p) if racer.hazards else objects
            if hud and match.frozen(p):
                self._freeze(match, view, racer, mine, i)
            else:
                self._frozen.pop(p, None)
                self._view(match, view, racer, mine, i, hud)
        if len(followed) == 2:
            x = VIEW_W
            pygame.draw.line(self.surface, INK, (x, 0), (x, H), 4)
            pygame.draw.line(self.surface, (200, 205, 225), (x, 0), (x, H), 1)
        if hud:
            self._minimap(match)

    def _lights_state(self, match: Match) -> tuple[str, int]:
        """The start lights: ("red", n) lit one by one in the countdown, all green after."""
        if match.state == COUNTDOWN or (match.state == PAUSED and match.paused_from == COUNTDOWN):
            n = 1 + int(match.t / config.COUNTDOWN * config.GANTRY_LIGHTS)
            return "red", min(config.GANTRY_LIGHTS, n)
        return "green", config.GANTRY_LIGHTS

    def _view(self, match: Match, view: RoadView, racer, objects, i: int, hud: bool) -> None:
        """One player's view, live: the road, its sprites, the effects and the HUD."""
        race = match.race
        car = racer.car
        warp = warp_level(race, racer)
        widen = fov(car.speed, warp)
        ahead = config.CAR_AHEAD / widen
        view.draw(self.surface, race.track, car.z - ahead, car.x, self._sprites, objects,
                  depth=config.CAMERA_DEPTH / widen, ahead=ahead,
                  lift=shake(car.speed, self.frame, i))
        self.gantry.lights = self._lights_state(match)
        view.draw_sprites(self.surface, self._sprites, self.cache)
        self._beams(view, race, car.z - ahead)
        if not (hud and racer.blind):  # decohered: the marker goes blank
            self._markers_over_right_arches(view)
        size = view.rect.size
        frame = (self.frame // 2) % LINE_FRAMES
        if warp > 0:
            self.surface.blit(self._tunnel[size][frame], view.rect.topleft)
            level = min(len(TINTS) - 1, int(warp * len(TINTS)))
            for strip, (x, y) in self._tint[size][level]:
                self.surface.blit(strip, (view.rect.x + x, view.rect.y + y))
        elif car.speed >= config.SPEED_LINES_AT * TOP:
            self.surface.blit(self._lines[(size, car.boost > 0)][frame], view.rect.topleft)
        if hud and match.state != RESULT:
            self._hud(match, view.rect, racer)
            since = race.time - racer.warp_time if racer.warp_time is not None else None
            if since is not None and since < config.LIGHT_SPEED_TEXT:
                px = 54 if view.width > VIEW_W else 42
                self.put("LIGHT SPEED!", px, (200, 240, 255),
                         center=(view.rect.centerx, view.rect.y + 250))

    def _markers_over_right_arches(self, view: RoadView, found=None) -> None:
        """The bouncing ▼ over every right arch in sight (the sprites as just drawn)."""
        bounce = abs(math.sin(self.frame * 0.16))
        ox, oy = view.rect.topleft
        for kind, x, y, scale, clip_y in (self._sprites if found is None else found):
            if not kind.endswith(":lit"):
                continue
            img = sprites.marker_for(scale)
            w = img.get_width()
            bottom = y - sprites.badge_top(scale) - 3 - bounce * (3 + 0.4 * w)
            if bottom > clip_y or bottom - w < 0:
                continue  # behind a crest, or above the view
            self.surface.blit(img, (ox + round(x - w / 2), oy + round(bottom - w)))

    def _beams(self, view: RoadView, race: Race, cam_z: float) -> None:
        """Each MEASURE shot's beam, from its shooter's car to the orb, in this view."""
        ox, oy = view.rect.topleft
        for shot in race.shots:
            k = shot.progress
            if k >= 1.0:
                continue  # waiting on a frozen target: just the orb
            a, b = race.racer(shot.owner).car, race.racer(shot.target).car
            p = view.place(a.z - cam_z, a.x)
            q = view.place(a.z + (b.z - a.z) * k - cam_z, a.x + (b.x - a.x) * k)
            if p is None or q is None:
                continue
            p0 = (ox + p[0], oy + p[1] - 0.08 * p[2])
            q0 = (ox + q[0], oy + q[1] - 0.12 * q[2])
            pygame.draw.line(self.surface, SHOT, p0, q0, 5)
            pygame.draw.line(self.surface, (255, 250, 220), p0, q0, 2)

    def _freeze(self, match: Match, view: RoadView, racer, objects, i: int) -> None:
        """The CIRCUIT CHECK: a still of the moment the player crossed, under the panel."""
        race = match.race
        p = racer.car.id
        still = self._frozen.get(p)
        if still is None or still[0] is not race:
            self._view(match, view, racer, objects, i, hud=True)
            still = (race, self.surface.subsurface(view.rect).copy())
            self._frozen[p] = still
        self.surface.blit(still[1], view.rect.topleft)
        self.surface.blit(self._shade[150], view.rect.topleft, ((0, 0), view.rect.size))
        self._check(view.rect, racer)

    def _minimap(self, match: Match) -> None:
        race = match.race
        mm = Minimap.for_track(race.track, MAP)
        if race.players == 2:
            x, y = W // 2 - MAP[0] // 2, H - MAP[1] - 6
        else:
            x, y = 10, H - MAP[1] - 10
        self.surface.blit(self.panel(MAP[0], MAP[1], (110, 116, 150), 170), (x, y))
        mm.draw(self.surface, (x, y), [(r.car.id, r.car.colour, r.car.z) for r in race.racers],
                match.players)

    # --- The HUD -----------------------------------------------------------------------------

    def _hud(self, match: Match, rect: pygame.Rect, racer) -> None:
        surf = self.surface
        car_id = racer.car.id
        narrow = rect.width < W
        col = config.PLAYER_COLORS[car_id]
        x, y = rect.topleft
        circuit = racer.circuit
        filled = circuit.filled
        # top left: the NEXT GATE badge, and a dot for every slot under it
        pw, ph = (208, 86) if narrow else (312, 78)
        lx = x + 90 if narrow else x + 96
        surf.blit(self.panel(pw, ph, mix(col, WHITE, 0.2)), (x + 8, y + 8))
        label_y = y + 24 if narrow else y + 27
        badge = None
        if racer.finished:
            self.put("FINISHED", 14, GOLD, midleft=(lx, label_y))
            badge = self._badges["flag"]
        elif filled < len(circuit.target):
            if racer.blind:  # decohered: the badge goes blank
                self.put("NO SIGNAL", 14, (200, 180, 240), midleft=(lx, label_y))
                badge = self._blind
            else:
                self.put("NEXT GATE", 14 if narrow else 15, WHITE, midleft=(lx, label_y))
                badge = self._badges[circuit.target[filled]]
        else:
            final = racer.lap >= config.LAPS
            words = ("NO GATES" if narrow else "FINAL LAP: NO GATES") if final else "TO THE LINE"
            self.put(words, 14, GOLD, midleft=(lx, label_y))
            badge = self._badges["flag"]
        surf.blit(badge, (x + 12, y + 11))
        rows = config.ROWS_PER_LAP
        for slot, result in enumerate(circuit.results):
            if narrow:
                dx, dy = lx + 14 * (slot % rows), y + 40 + 20 * (slot // rows)
            else:
                dx, dy = lx + DOT_STEP * slot + (8 if slot >= rows else 0), y + 54
            state = ("todo" if slot != filled else "next") if result is None else \
                ("ok" if result else "bad")
            surf.blit(self._dots[state], (dx - 2, dy))
        # top right: the place and the lap, the item under (or beside) them
        px = x + rect.width - (52 if narrow else 62)
        self.put(ordinal(racer.place), 30, WHITE, center=(px, y + 30))
        lap = "FINISHED" if racer.finished else f"LAP {racer.lap}/{config.LAPS}"
        self.put(lap, 12, SOFT, center=(px, y + 58))
        self._item(match, rect, racer, narrow)
        if car_id == "p1" and narrow:  # P1's name bottom left, else bottom right: clear
            self.put(NAMES[car_id], 18, col, bottomleft=(x + 14, y + rect.height - 8))  # of the map
        else:
            self.put(NAMES[car_id], 18, col, bottomright=(x + rect.width - 14, y + rect.height - 8))
        self._banners(match, rect, racer)

    def _item(self, match: Match, rect: pygame.Rect, racer, narrow: bool) -> None:
        """The held item, pulsing: its icon, its name and A (in 1P one line on what it does);
        ITEM FULL, its edge flashing red, after a box driven through with it held."""
        x, y = rect.topleft
        if narrow:
            px, py, w, h = x + rect.width - 174, y + 78, 166, 56
        else:
            px, py, w, h = x + W - 452, y + 8, 330, 64
        if racer.item is not None:
            k = round((PULSE - 1) * (0.5 + 0.5 * math.sin(self.frame * 0.18)))
            # ITEM FULL: a box was driven through with this held; the slot's edge flashes red
            full = match.banner(racer.car.id, "full") is not None
            if full and (self.frame // 5) % 2 == 0:
                edge = FULL
            else:
                edge = mix((110, 116, 150), GOLD, k / (PULSE - 1))
            self.surface.blit(self.panel(w, h, edge, 225), (px, py))
            name = racer.item
            use = self.name("a", self.hint_player(match, racer.car.id))  # A, or its key
            self.surface.blit(icons.icon(name, ICON), (px + 6, py + (h - ICON) // 2))
            if narrow:
                self.put(name, 15 if len(name) <= 7 else 14, ITEM_COLORS[name],
                         midleft=(px + 54, py + 18))
                if full:
                    self.put("ITEM FULL", 13, FULL, midleft=(px + 54, py + 39))
                else:
                    self.put(f"PRESS {use}", 13, GOLD, midleft=(px + 54, py + 39))
            else:
                self.put(name, 20 if len(name) <= 7 else 14, ITEM_COLORS[name],
                         midleft=(px + 58, py + 20))
                self.put("PRESS", 10, LABEL, midright=(px + w - 60, py + 20))
                if full:
                    self.put("ITEM FULL: USE IT TO TAKE ANOTHER", 12, FULL,
                             midleft=(px + 58, py + 46))
                else:
                    self.put(ITEM_LINES[name], 12, WHITE, midleft=(px + 58, py + 46))
                self.surface.blit(self.a_button(use)[k], (px + w - 54, py + 9))
        elif racer.split:
            self.surface.blit(self.panel(w, 34, GHOST_TEXT, 200), (px, py))
            word = "GATE" if racer.split_rows == 1 else "GATES"
            text = (f"CLONE: {racer.split_rows} MORE {word}" if narrow
                    else f"CLONE OUT: {racer.split_rows} MORE {word}")
            self.put(text, 11 if narrow else 13, GHOST_TEXT, center=(px + w // 2, py + 17))

    def _banners(self, match: Match, rect: pygame.Rect, racer) -> None:
        """The banners, each in its own place, top to bottom: LAP / FINAL LAP and STORM
        AHEAD, FINISH, (LIGHT SPEED!, the view's), the first-pickup tip, a box's item over
        the car, and each row's flash just above the car."""
        p = racer.car.id
        cx = rect.centerx
        narrow = rect.width < W
        flash = match.banner(p, "gate")
        if flash is not None:
            kind, value = flash.value
            text, col = FLASHES[kind]
            fy = rect.bottom - 152  # just above the car's wing
            self.put(text, 24 if narrow else 28, col, center=(cx, fy))
            if kind == "right" and value >= 2:
                self.put(f"STREAK x{value}", 13, CYAN, center=(cx, fy + 21))
        tip = match.banner(p, "tip")
        if tip is not None:
            ty = rect.y + 312
            use = self.name("a", self.hint_player(match, p))  # A, or its key
            img = self.text(f"PRESS {use} TO USE {tip.value}", 20 if narrow else 24, GOLD)
            w = img.get_width() + TIP_ICON + 34
            left = cx - w // 2
            self.surface.blit(self.panel(w, 44, GOLD, 220), (left, ty - 22))
            self.surface.blit(icons.icon(tip.value, TIP_ICON), (left + 10, ty - TIP_ICON // 2))
            self.surface.blit(img, img.get_rect(midleft=(left + TIP_ICON + 22, ty)))
        else:
            reveal = match.banner(p, "reveal")
            if reveal is not None:
                age = config.REVEAL_TIME - reveal.time
                i = min(len(REVEAL_ICONS) - 1, int(age / 0.05))
                img = icons.icon(reveal.value, REVEAL_ICONS[i])
                self.surface.blit(img, img.get_rect(center=(cx, rect.bottom - 212 - 30 * min(1.0, age * 3))))
        lap = match.banner(p, "lap")
        if lap is not None:
            self.put(f"LAP {lap.value}/{config.LAPS}", 30, WHITE, center=(cx, rect.y + 152))
        final = match.banner(p, "final")
        if final is not None and not match.frozen(p):
            self.put("FINAL LAP", 30, GOLD, center=(cx, rect.y + 152))
            if (self.frame // 12) % 4:
                self.put("STORM AHEAD", 22, STORM, center=(cx, rect.y + 188))
        done = match.banner(p, "finish")
        if done is not None:
            cy = rect.y + 173
            self.put("FINISH!", 44, GOLD, center=(cx, cy))
            self.put(ordinal(done.value) + " PLACE", 20, WHITE, center=(cx, cy + 40))
            waiting = [q for q in match.players if not match.race.racer(q).finished]
            if waiting and match.over_time is None:
                self.put(f"WAITING FOR {NAMES[waiting[0]]}", 12, SOFT, center=(cx, cy + 66))

    def _check(self, rect: pygame.Rect, racer) -> None:
        """CIRCUIT CHECK: all 16 of the target's slots over the car's, the wrong ones marked."""
        n = config.CHECK_SLOTS
        distance = racer.check or 0
        w, h = 17 * n + 48, 138
        x, y = rect.centerx - w // 2, rect.centery - h // 2
        self.surface.blit(self.panel(w, h, GOLD, 235), (x, y))
        cx = rect.centerx
        self.put("CIRCUIT CHECK", 14, GOLD, center=(cx, y + 16))
        right = n - distance
        if distance == 0:
            self.put(f"{right}/{n} PERFECT CIRCUIT!", 22, (120, 240, 140), center=(cx, y + 42))
        else:
            self.put(f"{right}/{n} GATES CORRECT", 22, WHITE, center=(cx, y + 42))
        c = racer.circuit
        x0 = cx - 17 * n // 2
        for i in range(n):
            bx = x0 + 17 * i + (4 if i >= config.ROWS_PER_LAP else -4)
            self.surface.blit(self._small[(c.target[i], "plain")], (bx - 4, y + 60 - 4))
            ok = c.slots[i] is not None and c.slots[i] == c.target[i]
            self.surface.blit(self._small[(c.slots[i], "ok" if ok else "bad")], (bx - 4, y + 80 - 4))
            if not ok:
                pygame.draw.rect(self.surface, BAD, (bx - 2, y + 56, SMALL + 4, 42), 2,
                                 border_radius=3)
        boost, seconds = racer.check_boost or config.check_boost(distance)
        none = racer.check_boost_none or boost <= 0
        line = "NO BOOST" if none else f"LIGHT SPEED: +{boost:.0%} FOR {seconds:.1f} S"
        self.put(line, 12, CYAN, center=(cx, y + 118))

    def _countdown(self, match: Match) -> None:
        n = match.countdown
        self._centre_text(match, str(n), 80, GOLD)

    def _centre_text(self, match: Match, s: str, px: int, col) -> None:
        for view in self.views[match.race.players]:
            self.put(s, px, col, center=(view.rect.centerx, view.rect.y + view.rect.height * 0.42))

    # --- Screens -----------------------------------------------------------------------------

    def _title(self, match: Match) -> None:
        cx = W // 2
        self.surface.blit(self._wordmark, self._wordmark.get_rect(center=(cx, 100)))
        self.put("STEER THROUGH THE GLOWING GATE TO BUILD THE TARGET CIRCUIT", 14, SOFT,
                 center=(cx, 168))
        rows = title_rows(match)
        self.surface.blit(self.panel(400, 40 * len(rows) + 8, None, 150), (cx - 200, 196))
        for i, (label, value, lo, hi) in enumerate(rows):
            y = 220 + 40 * i
            chosen = match.title_index == i
            col = WHITE if chosen else (150, 156, 180)
            idle = label == "LEVEL" and match.bot_count == 0  # no bots: no level to set
            if idle:
                col = EMPTY if not chosen else (150, 156, 180)
            if chosen:
                self.surface.blit(self.panel(380, 36, (200, 205, 225), 220), (cx - 190, y - 18))
                self.put("▶", 16, GOLD, center=(cx - 168, y))
            if value is None:  # QUIT
                self.put(label, 20, col, center=(cx, y))
                continue
            self.put(label, 20, col, midleft=(cx - 146, y))
            vx = cx + 92
            self.put(value, 20, GOLD if chosen and not idle else col, center=(vx, y))
            if chosen and not idle:
                arrow = (255, 230, 120)
                self.put("◀", 14, arrow if not lo else EMPTY, center=(vx - 70, y))
                self.put("▶", 14, arrow if not hi else EMPTY, center=(vx + 70, y))
        self.put(field_line(match), 13, LABEL, center=(cx, 382))
        # both players read the title: the hints name both their devices ("B / L")
        stick, back, a, start = (self.name(k) for k in ("stick", "back", "a", "start"))
        if (self.frame // 30) % 2 == 0:
            self.put(f"PRESS {start}", 22, (255, 230, 120), center=(cx, 414))
        self.surface.blit(self.panel(720, 58, None, 190), (cx - 360, 443))  # over the car
        self.put_fit(f"{stick} UP / DOWN: CHOOSE   LEFT / RIGHT: CHANGE   {a} OR {start}: RACE",
                     14, 704, SOFT, center=(cx, 458))
        self.put_fit(f"IN THE RACE   {stick}: STEER   {back}: BRAKE   {back} + STEER: DRIFT   "
                     f"{a}: ITEM   {start}: PAUSE", 12, 704, LABEL, center=(cx, 486))
        if match.attract:
            self.put("DEMO", 14, LABEL, topright=(W - 16, 12))
        self.put("MUSIC: VAPORMALL BY BOLT ACTION", 11, LABEL, topleft=(16, 12))  # its licence

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
        p = self.devices.latest  # one player works the menu
        a, b, start = (self.name(k, p) for k in ("a", "b", "start"))
        self.put_fit(f"{a}: PICK   {b} OR {start}: RESUME", 11, w - 16, LABEL,
                     center=(W // 2, y + h - 18))

    def _result(self, match: Match) -> None:
        surf = self.surface
        surf.blit(self._shade[215], (0, 0))
        cx = W // 2
        self.put("RESULTS", 34, WHITE, center=(cx, 32))
        rows = match.results or []
        for i, row in enumerate(rows):
            y = 72 + 26 * i
            col = config.CAR_COLORS[row.colour]
            bright = row.player
            self.put(ordinal(row.place), 18, WHITE if bright else SOFT, midright=(250, y))
            pygame.draw.rect(surf, col, (268, y - 9, 30, 18), border_radius=4)
            pygame.draw.rect(surf, (150, 156, 180), (268, y - 9, 30, 18), 1, border_radius=4)
            self.put(row.label, 18, col if bright else SOFT, midleft=(312, y))
            self.put(race_time(row.time), 16, WHITE if bright else SOFT, midleft=(470, y))
            gates = f"{row.right}/{config.SLOTS} GATES"
            self.put(gates, 16, (255, 230, 120) if bright else (150, 156, 180), midleft=(590, y))
        y = 72 + 26 * len(rows) + 6
        for row in (r for r in rows if r.player):
            self._circuit_rows(match, row, y)
            y += RESULT_PANEL[1] + 6
        if match.t >= config.RESULT_LOCK:
            who = self.devices.latest if match.mode == 1 else None
            a, b = self.name("a", who), self.name("b", who)
            self.put(f"{a}: REMATCH        {b}: TITLE", 18, (255, 230, 120), center=(cx, H - 22))

    def _circuit_rows(self, match: Match, row, y: int) -> None:
        """A player's panel: their accuracy and check on the left; their whole circuit
        under the target's, a ✓ or ✗ under each slot (a row of its own, so nothing
        crowds); and on the right their final state on a Bloch sphere beside the
        target's."""
        target = match.race.target  # the row's own circuit is frozen at the finish
        col = config.PLAYER_COLORS[row.car]
        w, h = RESULT_PANEL
        x = (W - w) // 2
        self.surface.blit(self.panel(w, h, col), (x, y))
        self.put(NAMES[row.car], 24, col, midleft=(x + 16, y + 26))
        self.put(f"{row.right}/{config.SLOTS} GATES", 18, WHITE, midleft=(x + 16, y + 58))
        check = "NO CHECK" if row.check_right is None else \
            f"CHECK {row.check_right}/{config.CHECK_SLOTS}"
        self.put(check, 14, LABEL, midleft=(x + 16, y + 86))
        bx0 = x + 230
        self.put("TARGET", 11, LABEL, midright=(bx0 - 10, y + 24))
        self.put("YOU", 11, LABEL, midright=(bx0 - 10, y + 54))
        boxes = self._result_boxes
        b = RESULT_BOX + 8
        for i in range(config.SLOTS):
            bx = bx0 + RESULT_STEP * i + (RESULT_LAP_GAP if i >= config.ROWS_PER_LAP else 0)
            self.surface.blit(boxes[(target[i], "plain")], (bx - 4, y + 24 - b // 2))
            result = row.results[i]
            if result is None:
                continue
            self.surface.blit(boxes[(row.slots[i], "plain")], (bx - 4, y + 54 - b // 2))
            if not result:
                pygame.draw.rect(self.surface, BAD, (bx - 3, y + 54 - b // 2 + 1, b - 2, b - 2), 2,
                                 border_radius=4)
            dot = self._dots["ok" if result else "bad"]
            self.surface.blit(dot, dot.get_rect(center=(bx + RESULT_BOX // 2, y + 84)))
        # the final states: yours, and the target's
        mine = bloch.state_of(tuple(row.slots))
        aim = bloch.state_of(tuple(target))
        sx = x + w - 2 * SPHERE - 40
        for k, (who, state) in enumerate((("YOU", mine), ("TARGET", aim))):
            px = sx + k * (SPHERE + 24)
            self.surface.blit(self._spheres[state], (px, y + 2))
            self.put(f"{who} {bloch.STATES[state][1]}", 13, bloch.STATES[state][2],
                     center=(px + SPHERE // 2, y + h - 14))
        same = mine == aim
        self.put("=" if same else "≠", 26, OK if same else BAD,
                 center=(sx + SPHERE + 12, y + 2 + SPHERE // 2))


def loading_screen(surface: pygame.Surface, done: float | None = None) -> None:
    """Shown while the sprites are drawn at start-up; with `done` (0 to 1), a bar of how
    far it got."""
    surface.fill((10, 14, 34))
    for s, px, y in (("GATE PRIX", 64, H // 2 - 30), ("LOADING...", 18, H // 2 + 40)):
        img = font(px).render(s, True, WHITE)
        surface.blit(img, img.get_rect(center=(W // 2, y)))
    if done is not None:
        bar = pygame.Rect(0, 0, 300, 8)
        bar.center = (W // 2, H // 2 + 76)
        pygame.draw.rect(surface, (40, 46, 80), bar, border_radius=4)
        pygame.draw.rect(surface, GOLD, (bar.x, bar.y, round(bar.w * min(1.0, done)), bar.h),
                         border_radius=4)
