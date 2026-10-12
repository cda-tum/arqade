"""The launcher's screens and main loop.

Screens sit on a stack: the menu at the bottom, settings, key mapping and
dialogs pushed over it. Only the top one gets input. Overlay screens (dialogs)
draw over the one below instead of replacing it.

While a game runs, the launcher closes its own window and just waits for the
game's process: two fullscreen windows fighting over focus is far more
trouble than the brief gap between them.
"""

from __future__ import annotations

import copy
import math
import random
import time
from collections.abc import Callable
from pathlib import Path

import pygame

from arqade_launcher import gfx, runner, settings as settings_mod, video
from arqade_launcher.catalog import Game
from arqade_launcher.gfx import DIM, ERROR, FAINT, PANEL, PANEL_EDGE, PLAYER_COLORS, TEXT, View
from arqade_launcher.settings import ACTIONS, LABELS, PLAYERS, Settings

FPS = 60
# After a game exits, ignore input briefly: the key that quit the game may
# still be held, and must not fire anything in the menu.
INPUT_GRACE = 0.4
# How long the loading card (with the controls) shows before a game starts.
LOADING_TIME = 1.6
# Seconds on the game menu without input before the attract reels play, as
# EmulationStation's screensaver does on the cabinet.
ATTRACT_DELAY = 15.0
# What counts as someone being there: it resets that timer, and ends the reel.
INPUT_EVENTS = {pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEWHEEL, pygame.MOUSEMOTION}

# Keys that always work in the menus, whatever the mapping.
FIXED_KEYS = {
    pygame.K_LEFT: "left", pygame.K_RIGHT: "right", pygame.K_UP: "up", pygame.K_DOWN: "down",
    pygame.K_RETURN: "confirm", pygame.K_KP_ENTER: "confirm", pygame.K_SPACE: "confirm",
    pygame.K_ESCAPE: "back", pygame.K_BACKSPACE: "back", pygame.K_TAB: "settings",
}
# ...plus both pads, with the cabinet's convention: A confirms, Start starts,
# B goes back (AGENTS.md, "Button convention").
PAD_INTENTS = {
    "up": "up", "down": "down", "left": "left", "right": "right",
    "a": "confirm", "start": "confirm", "b": "back", "select": "settings",
}

Hint = tuple[list[str], str]  # ([key cap labels], what they do)


class Screen:
    overlay = False

    def __init__(self, app: App):
        self.app = app

    def handle(self, event: pygame.event.Event, intent: str | None) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, surf: pygame.Surface, view: View) -> None:
        pass


class App:
    def __init__(self, games: list[Game], settings: Settings, settings_path: Path | None, *,
                 kiosk: bool = False, window_size: tuple[int, int] = (1280, 720),
                 run_game: Callable[..., runner.Result] = runner.run_game,
                 persisted_fullscreen: bool | None = None):
        self.games = games
        self.settings = settings
        self.settings_path = settings_path
        self.kiosk = kiosk
        self.window_size = window_size
        self.run_game = run_game
        # A --windowed/--fullscreen flag is for this session only; this is
        # what gets saved unless the display is changed in the menu.
        self.persisted_fullscreen = settings.fullscreen if persisted_fullscreen is None else persisted_fullscreen
        self.art = gfx.Art()
        self.screens: list[Screen] = []
        self.running = True
        self.surface: pygame.Surface | None = None
        self.block_until = 0.0
        self.toast_text, self.toast_until = "", 0.0
        self.mouse_seen = -10.0
        self.mouse_visible = True
        self.key_intents: dict[int, str] = {}
        self.refresh_keys()

    # --- state ---------------------------------------------------------------

    def refresh_keys(self) -> None:
        self.key_intents = {}
        for player in PLAYERS:
            for action, intent in PAD_INTENTS.items():
                code = runner.key_code(self.settings.keys[player].get(action))
                if code is not None:
                    self.key_intents.setdefault(code, intent)
        self.key_intents.update(FIXED_KEYS)

    def save(self) -> None:
        if self.settings_path is None:
            return
        stored = copy.deepcopy(self.settings)
        stored.fullscreen = self.persisted_fullscreen
        settings_mod.save(stored, self.settings_path)

    def toast(self, message: str, seconds: float = 2.5) -> None:
        self.toast_text, self.toast_until = message, time.monotonic() + seconds

    def push(self, screen: Screen) -> None:
        self.screens.append(screen)

    def pop(self, screen: Screen | None = None) -> None:
        if self.screens and (screen is None or self.screens[-1] is screen):
            self.screens.pop()

    def quit(self) -> None:
        self.running = False

    # --- display -------------------------------------------------------------

    def open_display(self) -> None:
        pygame.display.set_caption("Munich Quantum Arcade")
        if self.settings.fullscreen:
            size = pygame.display.get_desktop_sizes()[0]
            self.surface = pygame.display.set_mode(size, pygame.FULLSCREEN)
        else:
            self.surface = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        self.mouse_visible = not self.settings.fullscreen
        pygame.mouse.set_visible(self.mouse_visible)

    def set_fullscreen(self, fullscreen: bool) -> None:
        if not self.settings.fullscreen and self.surface is not None:
            self.window_size = self.surface.get_size()
        self.settings.fullscreen = self.persisted_fullscreen = fullscreen
        self.save()
        self.open_display()

    def play(self, game: Game) -> None:
        """Run a game to completion, then bring the menu back."""
        size = self.surface.get_size() if self.surface is not None else self.window_size
        if not self.settings.fullscreen:
            self.window_size = size
        # Key names only resolve with the display up, so the game's input
        # config is worked out before the menu lets go of the display.
        config = runner.input_config(self.settings)
        pygame.display.quit()
        try:
            result = self.run_game(game, self.settings, size, config)
        finally:
            pygame.display.init()
            self.open_display()
            pygame.event.clear()
            self.block_until = time.monotonic() + INPUT_GRACE
        if result.code != 0:
            self.push(ErrorScreen(self, game, result))

    # --- loop ----------------------------------------------------------------

    def run(self) -> None:
        self.open_display()
        self.push(MenuScreen(self))
        clock = pygame.time.Clock()
        while self.running:
            dt = min(0.1, clock.tick(FPS) / 1000)
            self.step(pygame.event.get(), dt)
            pygame.display.flip()

    def step(self, events: list[pygame.event.Event], dt: float) -> None:
        for event in events:
            self.handle(event)
            if not self.running:
                return
        self.screens[-1].update(dt)
        if not self.running or self.surface is None:
            return
        if (self.settings.fullscreen and self.mouse_visible
                and time.monotonic() - self.mouse_seen > 2.0):
            self.mouse_visible = False
            pygame.mouse.set_visible(False)
        self.draw()

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            if not self.kiosk:
                self.quit()
            return
        if event.type == pygame.MOUSEMOTION:
            self.mouse_seen = time.monotonic()
            if not self.mouse_visible:
                self.mouse_visible = True
                pygame.mouse.set_visible(True)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_q and event.mod & pygame.KMOD_CTRL:
                self.quit()  # the way out of kiosk mode, too
                return
            if event.key == pygame.K_F11:
                if not self.kiosk:
                    self.set_fullscreen(not self.settings.fullscreen)
                return
        if (event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEWHEEL)
                and time.monotonic() < self.block_until):
            return
        intent = self.key_intents.get(event.key) if event.type == pygame.KEYDOWN else None
        self.screens[-1].handle(event, intent)

    def draw(self) -> None:
        surf = self.surface
        view = View(surf.get_size())
        first = len(self.screens) - 1
        while first > 0 and self.screens[first].overlay:
            first -= 1
        for screen in self.screens[first:]:
            screen.draw(surf, view)
        if self.toast_text and time.monotonic() < self.toast_until:
            img = gfx.font(view.font_px(8)).render(self.toast_text, False, TEXT)
            rect = img.get_rect(center=view.pt(480, 480)).inflate(view.s(24), view.s(14))
            pygame.draw.rect(surf, PANEL, rect, border_radius=view.s(6))
            pygame.draw.rect(surf, gfx.PURPLE, rect, max(1, view.s(1)), border_radius=view.s(6))
            surf.blit(img, img.get_rect(center=rect.center))


# --- shared drawing --------------------------------------------------------


def draw_hints(surf: pygame.Surface, view: View, hints: list[Hint], y: float = 516) -> None:
    """A centred row of `[KEY] ACTION` hints."""
    f = gfx.font(view.font_px(8))
    gap, inner = view.s(22), view.s(6)

    def cap_w(label: str) -> int:
        return f.size(label)[0] + 2 * view.s(8 * 0.6)

    widths = [sum(cap_w(c) + inner for c in caps) + f.size(label)[0] for caps, label in hints]
    x = view.x(480) - (sum(widths) + gap * (len(hints) - 1)) // 2
    for (caps, label), width in zip(hints, widths):
        for c in caps:
            w = cap_w(c)
            gfx.keycap(surf, view, c, ((x + w / 2 - view.ox) / view.u, y))
            x += w + inner
        img = f.render(label, False, DIM)
        surf.blit(img, img.get_rect(midleft=(x, view.y(y))))
        x += img.get_width() + gap


def dim_behind(surf: pygame.Surface) -> None:
    shade = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 170))
    surf.blit(shade, (0, 0))


def draw_panel(surf: pygame.Surface, view: View, rect: pygame.Rect, edge=PANEL_EDGE) -> None:
    pygame.draw.rect(surf, PANEL, rect, border_radius=view.s(10))
    pygame.draw.rect(surf, edge, rect, max(1, view.s(2)), border_radius=view.s(10))


# --- the game menu ---------------------------------------------------------

# The carousel, by distance from the centre slot: (x offset, tile size, alpha).
SLOTS = [(0, 250, 255), (232, 150, 185), (382, 104, 90), (470, 80, 0)]


def _slot(distance: float) -> tuple[float, float, float]:
    d = min(abs(distance), len(SLOTS) - 1.0)
    i = min(int(d), len(SLOTS) - 2)
    t = d - i
    a, b = SLOTS[i], SLOTS[i + 1]
    x, size, alpha = (a[k] + (b[k] - a[k]) * t for k in range(3))
    return (x if distance >= 0 else -x), size, alpha


class MenuScreen(Screen):
    CENTER = (480, 236)

    def __init__(self, app: App):
        super().__init__(app)
        self.target = 0  # unbounded; the selected game is target % n
        self.pos = 0.0
        self.hits: list[tuple[pygame.Rect, int]] = []
        self.glows: dict[tuple[str, int], pygame.Surface] = {}
        self.clock = 0.0
        self.idle = 0.0

    @property
    def selected(self) -> Game:
        return self.app.games[self.target % len(self.app.games)]

    def offset(self, i: int, pos: float) -> float:
        n = len(self.app.games)
        return (i - pos + n / 2) % n - n / 2

    def handle(self, event, intent):
        if event.type in INPUT_EVENTS:
            self.idle = 0.0
        if not self.app.games:
            if intent == "back" and not self.app.kiosk:
                self.app.push(QuitScreen(self.app))
            return
        if intent == "left":
            self.target -= 1
        elif intent == "right":
            self.target += 1
        elif intent == "confirm":
            self.app.push(LoadingScreen(self.app, self.selected))
        elif intent == "back" and not self.app.kiosk:
            self.app.push(QuitScreen(self.app))
        elif intent == "settings" and not self.app.kiosk:
            self.app.push(SettingsScreen(self.app))
        elif event.type == pygame.MOUSEWHEEL:
            step = event.x or -event.y
            self.target += (step > 0) - (step < 0)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, i in reversed(self.hits):  # nearest tile first
                if rect.collidepoint(event.pos):
                    delta = round(self.offset(i, self.target))
                    if delta == 0:
                        self.app.push(LoadingScreen(self.app, self.selected))
                    else:
                        self.target += delta
                    break

    def update(self, dt):
        self.clock += dt
        self.pos += (self.target - self.pos) * min(1.0, dt * 14)
        if abs(self.target - self.pos) < 0.002:
            self.pos = float(self.target)
        self.idle += dt
        if self.idle >= ATTRACT_DELAY:
            self.idle = 0.0
            if self.app.settings.attract and video.reels():
                self.app.push(AttractScreen(self.app))

    def glow(self, game: Game, size: int) -> pygame.Surface:
        key = (game.package, size)
        if key not in self.glows:
            self.glows[key] = gfx.radial(self.app.art.color(game), size, 110)
        return self.glows[key]

    def draw(self, surf, view):
        surf.blit(gfx.background(surf.get_size()), (0, 0))
        mark = self.app.art.wordmark(view.s(62))
        if mark is not None:
            surf.blit(mark, mark.get_rect(midtop=view.pt(480, 20)))
        else:
            gfx.text(surf, view, "MUNICH QUANTUM ARQADE", 16, TEXT, (480, 50))

        games = self.app.games
        if not games:
            gfx.text(surf, view, "NO GAMES FOUND", 16, TEXT, (480, 240))
            gfx.text(surf, view, "Run from the arqade repo, or pass --games-root", 8, DIM, (480, 280))
            return

        cx, cy = self.CENTER
        game = self.selected
        glow = self.glow(game, view.s(560))
        glow.set_alpha(round(200 + 55 * math.sin(self.clock * 1.6)))
        surf.blit(glow, glow.get_rect(center=view.pt(cx, cy)))

        self.hits = []
        order = sorted(range(len(games)), key=lambda i: -abs(self.offset(i, self.pos)))
        for i in order:
            d = self.offset(i, self.pos)
            x, size, alpha = _slot(d)
            if alpha <= 1:
                continue
            tile = self.app.art.tile(games[i], view.s(size))
            tile.set_alpha(round(alpha))
            rect = tile.get_rect(center=view.pt(cx + x, cy))
            surf.blit(tile, rect)
            tile.set_alpha(255)
            self.hits.append((rect, i))

        frame = view.rect(cx - 125, cy - 125, 250, 250).inflate(view.s(12), view.s(12))
        pygame.draw.rect(surf, TEXT, frame, max(1, view.s(2)), border_radius=view.s(250 / 9 + 6))

        gfx.text(surf, view, game.name.upper(), 16, TEXT, (480, 392))
        px = view.font_px(8)
        lines = gfx.wrap(game.description, px, view.s(620))[:3]
        for k, line in enumerate(lines):
            gfx.text(surf, view, line, 8, DIM, (480, 424 + k * 15))

        n = len(games)
        dot_w, gap = 10, 6
        x0 = 480 - (n * dot_w + (n - 1) * gap) / 2
        for i in range(n):
            selected = i == self.target % n
            color = gfx.lerp_color(gfx.TEAL, gfx.MAGENTA, i / max(1, n - 1)) if selected else FAINT
            pygame.draw.rect(surf, color, view.rect(x0 + i * (dot_w + gap), 484, dot_w, 4),
                             border_radius=view.s(2))

        hints: list[Hint] = [(["<", ">"], "CHOOSE"), (["ENTER"], "PLAY")]
        if not self.app.kiosk:
            hints += [(["TAB"], "SETTINGS"), (["ESC"], "QUIT")]
        draw_hints(surf, view, hints)


class LoadingScreen(Screen):
    """Shown for a moment before a game starts: the ARQADE logo turning, the
    game's name, and the keys."""

    def __init__(self, app: App, game: Game):
        super().__init__(app)
        self.game = game
        self.t = 0.0
        self.frames = 0
        self.spin: video.Player | None = None

    def handle(self, event, intent):
        if intent == "confirm":
            self.t = max(self.t, LOADING_TIME)
        elif intent == "back":
            self.leave()

    def leave(self) -> None:
        if self.spin is not None:
            self.spin.close()
        self.app.pop(self)

    def update(self, dt):
        self.t += dt
        if self.t >= LOADING_TIME and self.frames >= 2:
            self.leave()
            self.app.play(self.game)

    def draw_spin(self, surf: pygame.Surface, view: View, center: tuple[float, float], width: float) -> bool:
        """The logo turning, centred on `center` (units). False without video."""
        if not video.available(video.SPIN):
            return False
        crop = video.SPIN_CROP
        size = (view.s(width), view.s(width * crop.h / crop.w))
        if self.spin is None or self.spin.size != size:
            if self.spin is not None:
                self.spin.close()
            self.spin = video.Player(video.SPIN, size, crop=crop)
        frame = self.spin.frame()
        if frame is not None:
            # The render is on black: MAX keeps the background glow around it.
            surf.blit(frame, frame.get_rect(center=view.pt(*center)), special_flags=pygame.BLEND_RGB_MAX)
        return True

    def draw(self, surf, view):
        self.frames += 1
        surf.blit(gfx.background(surf.get_size()), (0, 0))
        pads = self.app.settings.pads
        if pads:
            logo_y, name_y = 84, 190
        else:
            logo_y, name_y = 170, 310
        if not self.draw_spin(surf, view, (480, logo_y), 380 if pads else 560):
            size = 120 if pads else 200
            tile = self.app.art.tile(self.game, view.s(size))
            surf.blit(tile, tile.get_rect(midbottom=view.pt(480, name_y - 26)))
        gfx.text(surf, view, self.game.name.upper(), 16, TEXT, (480, name_y))
        dots = "." * (1 + int(self.t * 4) % 3)
        gfx.text(surf, view, f"LOADING{dots:<3}", 8, DIM, (480, name_y + 26))
        if pads:
            for k, player in enumerate(PLAYERS):
                x = 480 - 12 - gfx.PAD_W if k == 0 else 480 + 12
                gfx.draw_pad(surf, view, (x, 278), player, self.app.settings.keys[player])
        else:
            gfx.text(surf, view, "EACH GAME USES ITS OWN KEYBOARD CONTROLS", 8, DIM,
                     (480, name_y + 66))
        draw_hints(surf, view, [(["ESC"], "IN A GAME: BACK TO THE MENU")])


class AttractScreen(Screen):
    """The attract reels, full screen, until anyone touches anything: the
    launcher's version of the cabinet's screensaver. Like ES, it plays one
    reel at random to its end, then another (never the same one twice in a
    row). The input that ends it does nothing else, so a passer-by can't
    start a game by accident."""

    def __init__(self, app: App):
        super().__init__(app)
        self.reels = video.reels()
        self.reel: Path | None = None
        self.player: video.Player | None = None

    def handle(self, event, intent):
        if event.type not in INPUT_EVENTS:
            return
        if event.type == pygame.MOUSEMOTION and abs(event.rel[0]) + abs(event.rel[1]) < 4:
            return  # a nudged desk, not a person
        if self.player is not None:
            self.player.close()
        self.app.pop(self)

    def next_reel(self, size: tuple[int, int]) -> None:
        if self.player is not None:
            self.player.close()
        others = [r for r in self.reels if r != self.reel] or self.reels
        self.reel = random.choice(others)
        self.player = video.Player(self.reel, size, loop=False)

    def draw(self, surf, view):
        surf.fill((0, 0, 0))
        area = view.rect(0, 0, gfx.DESIGN_W, gfx.DESIGN_H)
        if self.player is None or self.player.size != area.size or self.player.done:
            self.next_reel(area.size)
        frame = self.player.frame()
        if frame is not None:
            surf.blit(frame, area)


# --- settings --------------------------------------------------------------


class SettingsScreen(Screen):
    def __init__(self, app: App):
        super().__init__(app)
        self.index = 0
        s = app.settings
        self.items: list[tuple[str, Callable[[], str], Callable[[int], None], str]] = [
            ("DISPLAY", lambda: "FULLSCREEN" if s.fullscreen else "WINDOW",
             lambda d: app.set_fullscreen(not s.fullscreen),
             "Games start the same way. F11 switches from anywhere in the menu."),
            ("GAME CONTROLS", lambda: "KEYBOARD PADS" if s.pads else "GAME'S OWN KEYS",
             self.toggle_pads, ""),
            ("FPS COUNTER IN GAMES", lambda: "ON" if s.show_fps else "OFF",
             self.toggle_fps, "Shows each game's frame rate in a corner."),
            ("ATTRACT MODE", lambda: "ON" if s.attract else "OFF", self.toggle_attract,
             f"After {ATTRACT_DELAY:.0f} s without input the menu plays the gameplay reels, "
             "like the cabinet's screensaver. Any key brings the menu back."),
            ("PLAYER 1 KEYS", lambda: ">", lambda d: d == 0 and app.push(KeysScreen(app, "p1")),
             "Choose the keys for the left (blue) pad."),
            ("PLAYER 2 KEYS", lambda: ">", lambda d: d == 0 and app.push(KeysScreen(app, "p2")),
             "Choose the keys for the right (red) pad."),
            ("RESET KEYS", lambda: "", lambda d: d == 0 and self.reset_keys(),
             "Put both pads back on the default keys."),
            ("QUIT", lambda: "", lambda d: d == 0 and app.push(QuitScreen(app)),
             "Close the arcade. Ctrl+Q also quits from anywhere."),
            ("BACK", lambda: "", lambda d: d == 0 and app.pop(self), ""),
        ]

    def help_text(self) -> str:
        label, _, _, help_text = self.items[self.index]
        if label == "GAME CONTROLS":
            if self.app.settings.pads:
                return ("Your keys act as the cabinet's two pads, the same in every game. "
                        "The games' own keyboard controls are off.")
            return "Each game reads the keyboard its own way, as in development. Real gamepads work too."
        return help_text

    def toggle_pads(self, d: int) -> None:
        self.app.settings.pads = not self.app.settings.pads
        self.app.save()

    def toggle_fps(self, d: int) -> None:
        self.app.settings.show_fps = not self.app.settings.show_fps
        self.app.save()

    def toggle_attract(self, d: int) -> None:
        self.app.settings.attract = not self.app.settings.attract
        self.app.save()

    def reset_keys(self) -> None:
        self.app.settings.keys = settings_mod.default_keys()
        self.app.save()
        self.app.refresh_keys()
        self.app.toast("KEYS RESET TO THE DEFAULTS")

    def handle(self, event, intent):
        if intent == "up":
            self.index = (self.index - 1) % len(self.items)
        elif intent == "down":
            self.index = (self.index + 1) % len(self.items)
        elif intent in ("confirm", "left", "right"):
            label, value, activate, _ = self.items[self.index]
            if intent == "confirm" or value() not in ("", ">"):
                activate(0 if intent == "confirm" else (1 if intent == "right" else -1))
        elif intent in ("back", "settings"):
            self.app.pop(self)

    def draw(self, surf, view):
        surf.blit(gfx.background(surf.get_size()), (0, 0))
        gfx.text(surf, view, "SETTINGS", 16, TEXT, (480, 56))
        row_h, top = 30, 92
        for k, (label, value, _, _) in enumerate(self.items):
            y = top + k * row_h
            selected = k == self.index
            if selected:
                draw_panel(surf, view, view.rect(200, y, 560, row_h - 6), edge=gfx.PURPLE)
            color = TEXT if selected else DIM
            gfx.text(surf, view, label, 8, color, (224, y + (row_h - 6) / 2), "midleft")
            v = value()
            if v:
                gfx.text(surf, view, v, 8, TEXT if selected else DIM, (736, y + (row_h - 6) / 2), "midright")
        help_text = self.help_text()
        if help_text:
            for k, line in enumerate(gfx.wrap(help_text, view.font_px(8), view.s(560))[:3]):
                gfx.text(surf, view, line, 8, DIM, (480, 392 + k * 16))
        draw_hints(surf, view, [(["^", "v"], "MOVE"), (["ENTER"], "CHANGE"), (["ESC"], "BACK")])


class KeysScreen(Screen):
    """One pad's key mapping, with the pad drawn live: held keys light up."""

    ROWS = ("all", *ACTIONS)
    ROW_LABELS = {
        "all": "ASSIGN ALL IN TURN",
        **{d: f"STICK {LABELS[d]}" for d in ("up", "down", "left", "right")},
        **{b: f"BUTTON {LABELS[b]}" for b in ("l", "x", "r", "y", "b", "a")},
        "start": "START", "select": "SELECT",
    }

    def __init__(self, app: App, player: str):
        super().__init__(app)
        self.player = player
        self.index = 0
        self.capture: str | None = None  # the action waiting for a key
        self.capture_all = False
        self.clock = 0.0

    @property
    def keys(self) -> dict[str, str | None]:
        return self.app.settings.keys[self.player]

    def start_capture(self, action: str, all_in_turn: bool) -> None:
        self.capture, self.capture_all = action, all_in_turn
        self.index = self.ROWS.index(action)

    def handle(self, event, intent):
        if event.type != pygame.KEYDOWN:
            return
        key = event.key
        if self.capture is not None:
            if key == pygame.K_ESCAPE:
                self.capture, self.capture_all = None, False
                return
            self.assign(self.capture, pygame.key.name(key))
            if self.capture_all and self.capture != ACTIONS[-1]:
                self.start_capture(ACTIONS[ACTIONS.index(self.capture) + 1], True)
            else:
                self.capture, self.capture_all = None, False
            return
        # Only fixed keys navigate here, so the mapped keys can be tested on
        # the pad drawing without moving the cursor.
        fixed = FIXED_KEYS.get(key)
        row = self.ROWS[self.index]
        if fixed == "up":
            self.index = (self.index - 1) % len(self.ROWS)
        elif fixed == "down":
            self.index = (self.index + 1) % len(self.ROWS)
        elif fixed in ("left", "right", "settings"):
            other = PLAYERS[1 - PLAYERS.index(self.player)]
            self.app.pop(self)
            self.app.push(KeysScreen(self.app, other))
        elif fixed == "confirm":
            if row == "all":
                self.start_capture(ACTIONS[0], True)
            else:
                self.start_capture(row, False)
        elif key == pygame.K_DELETE and row != "all":
            self.assign(row, None)
        elif fixed == "back":
            self.app.pop(self)

    def assign(self, action: str, key: str | None) -> None:
        if key == settings_mod.EXIT_KEY:
            return
        moved = self.app.settings.bind(self.player, action, key)
        self.app.save()
        self.app.refresh_keys()
        if moved is not None:
            other_player, other_action = moved
            self.app.toast(f"{gfx.key_label(key)} WAS P{PLAYERS.index(other_player) + 1} "
                           f"{LABELS[other_action]}, NOW UNSET")

    def update(self, dt):
        self.clock += dt

    def held_actions(self) -> set[str]:
        pressed = pygame.key.get_pressed()
        lit = set()
        for action, name in self.keys.items():
            code = runner.key_code(name)
            if code is not None:
                try:
                    if pressed[code]:
                        lit.add(action)
                except IndexError:
                    pass
        return lit

    def draw(self, surf, view):
        surf.blit(gfx.background(surf.get_size()), (0, 0))
        color = PLAYER_COLORS[self.player]
        gfx.text(surf, view, f"{gfx.PLAYER_NAMES[self.player]} KEYS", 16, color, (480, 48))
        side = "LEFT" if self.player == "p1" else "RIGHT"
        gfx.text(surf, view, f"THE CABINET'S {side} PAD", 8, DIM, (480, 74))

        row_h, top = 25, 100
        for k, row in enumerate(self.ROWS):
            y = top + k * row_h
            mid = y + (row_h - 4) / 2
            selected = k == self.index
            if selected:
                draw_panel(surf, view, view.rect(70, y, 330, row_h - 4),
                           edge=TEXT if self.capture else color)
            gfx.text(surf, view, self.ROW_LABELS[row], 8, TEXT if selected else DIM, (88, mid), "midleft")
            if row == "all":
                continue
            if self.capture == row:
                blink = int(self.clock * 3) % 2 == 0
                gfx.text(surf, view, "PRESS A KEY" if blink else "", 8, TEXT, (384, mid), "midright")
            else:
                name = self.keys.get(row)
                label = gfx.key_label(name, 12) if name else "UNSET"
                gfx.text(surf, view, label, 8, TEXT if name else ERROR, (384, mid), "midright")

        highlight = self.capture or (self.ROWS[self.index] if self.ROWS[self.index] != "all" else None)
        blink = self.capture is None or int(self.clock * 3) % 2 == 0
        gfx.draw_pad(surf, view, (470, 112), self.player, self.keys,
                     highlight=highlight, lit=self.held_actions(), blink=blink)
        if self.capture:
            msg = f"PRESS THE KEY FOR {LABELS[self.capture]}.   ESC CANCELS."
        else:
            msg = "PRESS YOUR KEYS TO TEST THEM: THEY LIGHT UP ON THE PAD."
        for k, line in enumerate(gfx.wrap(msg, view.font_px(8), view.s(340))):
            gfx.text(surf, view, line, 8, TEXT if self.capture else DIM, (640, 352 + k * 16))

        if self.capture:
            hints: list[Hint] = [(["ESC"], "CANCEL")]
        else:
            hints = [(["^", "v"], "MOVE"), (["ENTER"], "CHANGE"), (["DEL"], "UNSET"),
                     (["TAB"], "OTHER PLAYER"), (["ESC"], "BACK")]
        draw_hints(surf, view, hints)


# --- dialogs ---------------------------------------------------------------


class QuitScreen(Screen):
    overlay = True

    def __init__(self, app: App):
        super().__init__(app)
        self.yes = True

    def handle(self, event, intent):
        if intent in ("left", "right"):
            self.yes = not self.yes
        elif intent == "confirm":
            if self.yes:
                self.app.quit()
            else:
                self.app.pop(self)
        elif intent == "back":
            self.app.pop(self)

    def draw(self, surf, view):
        dim_behind(surf)
        draw_panel(surf, view, view.rect(300, 190, 360, 140), edge=gfx.PURPLE)
        gfx.text(surf, view, "QUIT THE ARCADE?", 16, TEXT, (480, 230))
        for k, (label, value) in enumerate((("NO", False), ("YES", True))):
            x = 420 + k * 120
            chosen = self.yes == value
            if chosen:
                draw_panel(surf, view, view.rect(x - 40, 268, 80, 28), edge=TEXT)
            gfx.text(surf, view, label, 8, TEXT if chosen else DIM, (x, 282))


class ErrorScreen(Screen):
    overlay = True

    def __init__(self, app: App, game: Game, result: runner.Result):
        super().__init__(app)
        self.game = game
        self.result = result
        lines = [line.strip() for line in result.stderr_tail if line.strip()]
        self.reason = lines[-1] if lines else "No error output."

    def handle(self, event, intent):
        if intent in ("confirm", "back"):
            self.app.pop(self)

    def draw(self, surf, view):
        dim_behind(surf)
        lines = gfx.wrap(self.reason, view.font_px(8), view.s(600))[:6]
        height = 136 + 16 * len(lines)
        top = 270 - height / 2
        draw_panel(surf, view, view.rect(150, top, 660, height), edge=ERROR)
        gfx.text(surf, view, f"{self.game.name.upper()} STOPPED", 16, ERROR, (480, top + 34))
        gfx.text(surf, view, f"EXIT CODE {self.result.code}. THE FULL LOG IS IN THE TERMINAL.",
                 8, DIM, (480, top + 62))
        for k, line in enumerate(lines):
            gfx.text(surf, view, line, 8, TEXT, (480, top + 92 + k * 16))
        draw_hints(surf, view, [(["ENTER"], "OK")], y=top + height - 26)
