"""Drawing: a resolution-independent layout, fonts, art and the shared widgets
(key caps, the pad diagram).

The launcher draws at the screen's real resolution rather than a fixed small
one: a PC monitor can be anything from 1366x768 to 4K, and only native drawing
keeps the logos sharp on all of them. Layout is in *units* of a 960x540 design
canvas, centred and letterboxed to 16:9; at 1080p one unit is two pixels.
Press Start 2P is a pixel font that only looks right at multiples of 8 px, so
font sizes snap to those.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from arqade_launcher.catalog import REPO_ROOT, Game

ASSETS = Path(__file__).resolve().parent / "assets"
FONT_FILE = ASSETS / "fonts" / "PressStart2P-Regular.ttf"
WORDMARK_FILE = REPO_ROOT / "quantum-pong" / "batocera" / "arqade-theme" / "art" / "logos" / "mqt-w.png"

DESIGN_W, DESIGN_H = 960, 540

BG = (7, 7, 13)
PANEL = (17, 17, 28)
PANEL_EDGE = (44, 44, 66)
TEXT = (238, 238, 246)
DIM = (150, 150, 172)
FAINT = (84, 84, 106)
ERROR = (255, 96, 96)
# The ARQADE wordmark's gradient, teal -> purple -> magenta.
TEAL = (70, 184, 190)
PURPLE = (118, 82, 216)
MAGENTA = (178, 80, 190)
# The cabinet's sides: left pad blue, right pad red (AGENTS.md).
PLAYER_COLORS = {"p1": (72, 140, 255), "p2": (240, 72, 84)}
PLAYER_NAMES = {"p1": "PLAYER 1", "p2": "PLAYER 2"}


class View:
    """Maps design units onto the actual screen."""

    def __init__(self, size: tuple[int, int]):
        self.w, self.h = size
        self.u = min(self.w / DESIGN_W, self.h / DESIGN_H)
        self.ox = (self.w - DESIGN_W * self.u) / 2
        self.oy = (self.h - DESIGN_H * self.u) / 2

    def x(self, v: float) -> int:
        return round(self.ox + v * self.u)

    def y(self, v: float) -> int:
        return round(self.oy + v * self.u)

    def s(self, v: float) -> int:
        return max(1, round(v * self.u))

    def pt(self, x: float, y: float) -> tuple[int, int]:
        return self.x(x), self.y(y)

    def rect(self, x: float, y: float, w: float, h: float) -> pygame.Rect:
        return pygame.Rect(self.x(x), self.y(y), self.s(w), self.s(h))

    def font_px(self, size: float) -> int:
        return max(8, round(size * self.u / 8) * 8)


_fonts: dict[int, pygame.font.Font] = {}


def font(px: int) -> pygame.font.Font:
    if px not in _fonts:
        _fonts[px] = pygame.font.Font(str(FONT_FILE), px)
    return _fonts[px]


def text(surf: pygame.Surface, view: View, s: str, size: float, color, pos: tuple[float, float],
         anchor: str = "center") -> pygame.Rect:
    """Draw `s` with its `anchor` (a pygame.Rect attribute name) at `pos`, in units."""
    img = font(view.font_px(size)).render(s, False, color)
    rect = img.get_rect(**{anchor: view.pt(*pos)})
    surf.blit(img, rect)
    return rect


def wrap(s: str, size_px: int, max_width_px: int) -> list[str]:
    f = font(size_px)
    lines: list[str] = []
    for paragraph in s.split("\n"):
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}".strip()
            if line and f.size(candidate)[0] > max_width_px:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    return lines


def lerp_color(a, b, t: float):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


# --- art ------------------------------------------------------------------


def radial(color, size: int, strength: int = 255) -> pygame.Surface:
    """A soft round glow, transparent at the edge."""
    n = 64
    small = pygame.Surface((n, n), pygame.SRCALPHA)
    c = (n - 1) / 2
    for yy in range(n):
        for xx in range(n):
            d = min(1.0, ((xx - c) ** 2 + (yy - c) ** 2) ** 0.5 / c)
            small.set_at((xx, yy), (*color, round(strength * (1 - d) ** 2)))
    return pygame.transform.smoothscale(small, (size, size))


def _rounded_mask(size: int, radius: int) -> pygame.Surface:
    """White rounded square with antialiased corners (drawn 4x, scaled down)."""
    big = pygame.Surface((size * 4, size * 4), pygame.SRCALPHA)
    pygame.draw.rect(big, (255, 255, 255, 255), big.get_rect(), border_radius=radius * 4)
    return pygame.transform.smoothscale(big, (size, size))


def _placeholder(game: Game) -> pygame.Surface:
    """For a game without a logo yet: its name on the ARQADE gradient."""
    n = 512
    small = pygame.Surface((2, 2))
    small.set_at((0, 0), TEAL)
    small.set_at((1, 0), PURPLE)
    small.set_at((0, 1), PURPLE)
    small.set_at((1, 1), MAGENTA)
    surf = pygame.transform.smoothscale(small, (n, n))
    dark = pygame.Surface((n, n), pygame.SRCALPHA)
    dark.fill((0, 0, 0, 110))
    surf.blit(dark, (0, 0))
    lines = wrap(game.name.upper(), 48, n - 80)
    f = font(48)
    total = len(lines) * 64 - 16
    for i, line in enumerate(lines):
        img = f.render(line, False, TEXT)
        surf.blit(img, img.get_rect(center=(n // 2, n // 2 - total // 2 + 24 + i * 64)))
    return surf


class Art:
    """Loads each game's logo once and hands out rounded tiles at any size."""

    def __init__(self):
        self._source: dict[str, pygame.Surface] = {}
        self._tiles: dict[tuple[str, int], pygame.Surface] = {}
        self._masks: dict[int, pygame.Surface] = {}
        self._colors: dict[str, tuple[int, int, int]] = {}
        self._wordmark: pygame.Surface | None | bool = False

    def source(self, game: Game) -> pygame.Surface:
        if game.package not in self._source:
            img = None
            if game.art is not None:
                try:
                    img = pygame.image.load(str(game.art)).convert_alpha()
                except (pygame.error, FileNotFoundError):
                    img = None
            if img is None:
                img = _placeholder(game).convert_alpha()
            # Pre-shrink once: every tile is far smaller than the 1024 px logos.
            if img.get_width() > 512:
                img = pygame.transform.smoothscale(img, (512, 512))
            self._source[game.package] = img
        return self._source[game.package]

    def color(self, game: Game) -> tuple[int, int, int]:
        """The logo's average colour, brightened: tints the glow behind it."""
        if game.package not in self._colors:
            r, g, b, *_ = pygame.transform.average_color(self.source(game))
            peak = max(r, g, b, 1)
            self._colors[game.package] = tuple(min(255, round(c * 220 / peak)) for c in (r, g, b))
        return self._colors[game.package]

    def tile(self, game: Game, size: int) -> pygame.Surface:
        key = (game.package, size)
        if key not in self._tiles:
            if len(self._tiles) > 96:  # sizes change while the carousel moves
                self._tiles.clear()
            surf = pygame.transform.smoothscale(self.source(game), (size, size)).convert_alpha()
            if size not in self._masks:
                if len(self._masks) > 96:
                    self._masks.clear()
                self._masks[size] = _rounded_mask(size, max(2, size // 9))
            surf.blit(self._masks[size], (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            self._tiles[key] = surf
        return self._tiles[key]

    def wordmark(self, height: int) -> pygame.Surface | None:
        if self._wordmark is False:
            try:
                img = pygame.image.load(str(WORDMARK_FILE)).convert_alpha()
                self._wordmark = img.subsurface(img.get_bounding_rect()).copy()
            except (pygame.error, FileNotFoundError):
                self._wordmark = None
        if self._wordmark is None:
            return None
        w = round(self._wordmark.get_width() * height / self._wordmark.get_height())
        return pygame.transform.smoothscale(self._wordmark, (w, height))


_backgrounds: dict[tuple[int, int], pygame.Surface] = {}


def background(size: tuple[int, int]) -> pygame.Surface:
    """Near-black with a faint teal glow top left and purple bottom right."""
    if size not in _backgrounds:
        _backgrounds.clear()
        w, h = size
        surf = pygame.Surface(size)
        surf.fill(BG)
        r = round(max(w, h) * 0.9)
        surf.blit(radial(TEAL, r, 34), (-r // 2, -r // 2))
        surf.blit(radial(PURPLE, r, 40), (w - r // 2, h - r // 2))
        _backgrounds[size] = surf.convert()
    return _backgrounds[size]


# --- widgets --------------------------------------------------------------

KEY_LABELS = {
    "return": "ENTER", "enter": "KPENT", "space": "SPACE", "backspace": "BKSP",
    "tab": "TAB", "caps lock": "CAPS", "delete": "DEL", "insert": "INS",
    "page up": "PGUP", "page down": "PGDN",
    "left shift": "LSHFT", "right shift": "RSHFT", "left ctrl": "LCTRL",
    "right ctrl": "RCTRL", "left alt": "LALT", "right alt": "RALT",
    "left meta": "LMETA", "right meta": "RMETA", "left gui": "LWIN", "right gui": "RWIN",
}


def key_label(name: str | None, limit: int = 6) -> str:
    """Short upper-case name for a key cap: 'right shift' -> 'RSHFT'."""
    if not name:
        return "---"
    if name in KEY_LABELS:
        label = KEY_LABELS[name]
    elif name.startswith("[") and name.endswith("]") and len(name) > 2:
        label = "KP" + name[1:-1]  # keypad keys: "[7]" -> "KP7"
    else:
        label = name.upper().replace(" ", "")
    return label[:limit]


def keycap(surf: pygame.Surface, view: View, label: str, at: tuple[float, float],
           size: float = 8, *, anchor: str = "center", color=TEXT, edge=PANEL_EDGE,
           fill=(28, 28, 44)) -> pygame.Rect:
    """A key cap with `label`, its `anchor` point at `at` (units)."""
    img = font(view.font_px(size)).render(label, False, color)
    rect = img.get_rect().inflate(2 * view.s(size * 0.6), 2 * view.s(size * 0.45))
    setattr(rect, anchor, view.pt(*at))
    pygame.draw.rect(surf, fill, rect, border_radius=view.s(3))
    pygame.draw.rect(surf, edge, rect, width=max(1, view.s(1)), border_radius=view.s(3))
    surf.blit(img, img.get_rect(center=rect.center))
    return rect


PAD_W, PAD_H = 340, 210

# Where each control sits on the pad diagram, in units from its top-left:
# the stick on the left, the printed 2x3 grid on the right, Select and Start
# along the bottom.
_STICK, _STICK_R = (84, 104), 30
_STICK_CAPS = {  # (anchor point, which side of the cap sits on it)
    "up": ((84, 104 - 52), "center"), "down": ((84, 104 + 52), "center"),
    "left": ((84 - _STICK_R - 6, 104), "midright"), "right": ((84 + _STICK_R + 6, 104), "midleft"),
}
_GRID = {"l": (204, 66), "x": (256, 66), "r": (308, 66),
         "y": (204, 124), "b": (256, 124), "a": (308, 124)}
_SYSTEM = {"select": 110, "start": 256}  # centre x of each label + cap group
_SYSTEM_Y = 186


def draw_pad(surf: pygame.Surface, view: View, origin: tuple[float, float], player: str,
             keys: dict[str, str | None], *, highlight: str | None = None,
             lit: frozenset[str] | set[str] = frozenset(), blink: bool = True,
             scale: float = 1.0) -> None:
    """One cabinet pad -- stick, the L X R / Y B A grid, Select and Start --
    with the key bound to each. `highlight` rings one control, `lit` fills the
    ones currently held."""
    ox, oy = origin
    color = PLAYER_COLORS[player]
    line = max(1, view.s(2 * scale))

    def p(x: float, y: float) -> tuple[float, float]:
        return ox + x * scale, oy + y * scale

    panel = view.rect(ox, oy, PAD_W * scale, PAD_H * scale)
    pygame.draw.rect(surf, PANEL, panel, border_radius=view.s(10 * scale))
    pygame.draw.rect(surf, lerp_color(PANEL_EDGE, color, 0.45), panel,
                     width=line, border_radius=view.s(10 * scale))
    text(surf, view, PLAYER_NAMES[player], 8 * scale, color, p(14, 14), "topleft")

    def cap(action: str, at: tuple[float, float], anchor: str = "center") -> pygame.Rect:
        name = keys.get(action)
        held = action in lit
        return keycap(surf, view, key_label(name, 5), p(*at), 8 * scale, anchor=anchor,
                      color=ERROR if not name else TEXT,
                      edge=TEXT if highlight == action and blink else (color if held else PANEL_EDGE),
                      fill=lerp_color((28, 28, 44), color, 0.55) if held else (28, 28, 44))

    # Stick: the knob leans the way it's pushed.
    cx, cy = p(*_STICK)
    lean_x = ("right" in lit) - ("left" in lit)
    lean_y = ("down" in lit) - ("up" in lit)
    pygame.draw.circle(surf, (28, 28, 44), view.pt(cx, cy), view.s(_STICK_R * scale))
    pygame.draw.circle(surf, PANEL_EDGE, view.pt(cx, cy), view.s(_STICK_R * scale), line)
    knob = view.pt(cx + lean_x * 12 * scale, cy + lean_y * 12 * scale)
    pygame.draw.circle(surf, color, knob, view.s(12 * scale))
    for action, (at, anchor) in _STICK_CAPS.items():
        cap(action, at, anchor)

    # The 2x3 button grid, as printed on the pad.
    r = 16 * scale
    for action, (bx, by) in _GRID.items():
        center = view.pt(*p(bx, by))
        held = action in lit
        pygame.draw.circle(surf, color if held else (36, 36, 56), center, view.s(r))
        pygame.draw.circle(surf, color, center, view.s(r), line)
        if highlight == action and blink:
            pygame.draw.circle(surf, TEXT, center, view.s(r + 4 * scale), line)
        text(surf, view, action.upper(), 8 * scale, BG if held else TEXT, p(bx + 0.5, by + 0.5))
        cap(action, (bx, by + 29))

    # Measured, not assumed: font sizes snap to whole pixels-per-unit steps,
    # so at other scales the text isn't exactly 8 units per character.
    f = font(view.font_px(8 * scale))
    cap_pad = 2 * view.s(8 * scale * 0.6)
    for action, group_x in _SYSTEM.items():
        label = action.upper()
        label_w = f.size(label)[0] / view.u / scale
        cap_w = (f.size(key_label(keys.get(action), 5))[0] + cap_pad) / view.u / scale
        width = label_w + 6 + cap_w
        left = group_x - width / 2
        bright = (highlight == action and blink) or action in lit
        text(surf, view, label, 8 * scale, TEXT if bright else DIM, p(left, _SYSTEM_Y), "midleft")
        cap(action, (left + width, _SYSTEM_Y), "midright")
