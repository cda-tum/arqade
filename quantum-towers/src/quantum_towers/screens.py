"""Title/attract and winner screens, the pause menu overlay, and the solo
time trial's countdown, finish banner, initials entry and fastest-clears table.

The rendering functions here are pygame-drawing glue (not unit tested, same
convention as main.py, apart from a smoke test of the table) except
`blink_visible`, `NameEntry` and `AutoRepeat`, which are plain, pure logic
worth testing on their own.
"""

from __future__ import annotations

import pygame

from quantum_towers import config, visuals
from quantum_towers.solo import format_time

LEGEND_LINES = [
    "Apply gates to match the target state",
    "Phase matters -- watch the sign / i!",
    "X Y Z: Pauli   H: Hadamard   RESET: |0>",
    "Match it in the minimum presses for a charge",
    "Push UP to confirm -- wrong state stuns you!",
]
# 1 PLAYER has no charges, so its fourth line is about the clock instead.
SOLO_LEGEND_LINES = [
    *LEGEND_LINES[:3], f"Climb all {config.TOWER_HEIGHT} floors as fast as you can", *LEGEND_LINES[4:]
]


def button_grid() -> list[list[tuple[str, str | None]]]:
    """The cabinet's 6 physical buttons as they actually sit -- two rows of
    three -- each cell (button_label, gate_name), or (button_label, None)
    for a position with no gate mapped to it. This reflects the cabinet's
    fixed PRINTED layout (BUTTON_LABELS + GATE_AT_POSITION), which is the
    same for both players' pads regardless of how each pad is individually
    wired -- see INPUT_CONFIG's "buttons" dicts for the actual raw hardware
    numbers, which are a completely separate mapping (deliberately not used
    here; conflating the two was the first real-hardware mapping bug)."""
    cells = list(zip(config.BUTTON_LABELS, config.GATE_AT_POSITION))
    return [cells[0:3], cells[3:6]]


def blink_visible(t: float, period: float) -> bool:
    """True for the first half of each `period`-second cycle."""
    return (t % period) < (period / 2)


def draw_title_screen(
    surface: pygame.Surface,
    title_font: pygame.font.Font,
    legend_font: pygame.font.Font,
    prompt_font: pygame.font.Font,
    grid_gate_font: pygame.font.Font,
    show_prompt: bool,
    p1_pressed: dict[str, bool] | None = None,
    p2_pressed: dict[str, bool] | None = None,
    selected: str = "2p",
    choice_font: pygame.font.Font | None = None,
) -> None:
    surface.fill(config.COLOR_BACKGROUND)

    title = title_font.render("QUANTUM TOWERS", False, config.COLOR_TEXT)
    surface.blit(title, title.get_rect(center=(config.INTERNAL_WIDTH // 2, 40)))

    y = 90
    for line in SOLO_LEGEND_LINES if selected == "1p" else LEGEND_LINES:
        line_surf = legend_font.render(line, False, config.COLOR_TEXT)
        surface.blit(line_surf, line_surf.get_rect(center=(config.INTERNAL_WIDTH // 2, y)))
        y += 20

    y += 14
    grid = button_grid()
    visuals.draw_button_grid(
        surface, (config.INTERNAL_WIDTH // 4, y), grid, grid_gate_font,
        accent_color=config.COLOR_PLAYER_1, pressed=p1_pressed,
    )
    visuals.draw_button_grid(
        surface, (config.INTERNAL_WIDTH * 3 // 4, y), grid, grid_gate_font,
        accent_color=config.COLOR_PLAYER_2, pressed=p2_pressed,
    )
    # The player-count choice sits between the two pads' legends.
    _draw_player_choice(surface, choice_font or legend_font, selected, y, show_prompt)

    if show_prompt:
        prompt = prompt_font.render("PRESS A OR START", False, config.COLOR_FPS)
        surface.blit(
            prompt, prompt.get_rect(center=(config.INTERNAL_WIDTH // 2, config.INTERNAL_HEIGHT - 28))
        )


PLAYER_CHOICES = (("1p", "1 PLAYER"), ("2p", "2 PLAYERS"))


def _draw_player_choice(
    surface: pygame.Surface, font: pygame.font.Font, selected: str, centery: int, show_cursor: bool
) -> None:
    centerx = config.INTERNAL_WIDTH // 2
    widest = max(font.size(label)[0] for _key, label in PLAYER_CHOICES)
    left = centerx - widest // 2
    line = font.get_height() + 8
    for i, (key, label) in enumerate(PLAYER_CHOICES):
        y = centery - line + i * line
        active = key == selected
        color = config.COLOR_HINT if active else config.COLOR_TOWER
        visuals.blit_outlined_text(surface, font, label, color, (left, y))
        if active and show_cursor:
            visuals.blit_outlined_text(surface, font, ">", color, (left - font.size("> ")[0], y))


def draw_winner_screen(
    surface: pygame.Surface,
    big_font: pygame.font.Font,
    small_font: pygame.font.Font,
    winner_label: str,
    floors: dict[str, int],
) -> None:
    surface.fill(config.COLOR_BACKGROUND)

    text = big_font.render(f"{winner_label} WINS", False, config.COLOR_TEXT)
    surface.blit(
        text, text.get_rect(center=(config.INTERNAL_WIDTH // 2, config.INTERNAL_HEIGHT // 2 - 20))
    )

    floor_surf = small_font.render(
        f"{floors['p1']} - {floors['p2']}", False, config.COLOR_TEXT
    )
    surface.blit(
        floor_surf,
        floor_surf.get_rect(center=(config.INTERNAL_WIDTH // 2, config.INTERNAL_HEIGHT // 2 + 20)),
    )


PAUSE_HINT = "A: PICK   START/B: RESUME"


def draw_pause_menu(
    surface: pygame.Surface,
    title_font: pygame.font.Font,
    item_font: pygame.font.Font,
    hint_font: pygame.font.Font,
    items: tuple[str, ...],
    selected: int,
    show_cursor: bool,
) -> None:
    """A centred panel over the frozen game, which stays visible (dimmed)
    behind it so nobody wonders where their climb went."""
    veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    veil.fill((*config.COLOR_BACKGROUND, 160))
    surface.blit(veil, (0, 0))

    centerx = config.INTERNAL_WIDTH // 2
    box = pygame.Rect(0, 0, 240, 64 + 18 * len(items))
    box.center = (centerx, config.INTERNAL_HEIGHT // 2)
    pygame.draw.rect(surface, config.COLOR_BACKGROUND, box, border_radius=6)
    pygame.draw.rect(surface, config.COLOR_TOWER, box, 2, border_radius=6)

    visuals.blit_outlined_text_centered(
        surface, title_font, "PAUSED", config.COLOR_TARGET, centerx, box.y + 12
    )
    for i, item in enumerate(items):
        y = box.y + 38 + i * 18
        active = i == selected
        rect = visuals.blit_outlined_text_centered(
            surface, item_font, item, config.COLOR_HINT if active else config.COLOR_TEXT, centerx, y
        )
        if active and show_cursor:
            visuals.blit_outlined_text(
                surface, item_font, ">", config.COLOR_HINT, (rect.x - 16, y)
            )
    visuals.blit_outlined_text_centered(
        surface, hint_font, PAUSE_HINT, config.COLOR_TOWER, centerx, box.bottom - 16
    )


# --- Solo time trial ----------------------------------------------------------


def draw_countdown(surface: pygame.Surface, font: pygame.font.Font, text: str) -> None:
    """3, 2, 1 and GO!, big on both sides of the centred tower, so the first
    target stays readable (and plannable) during the countdown."""
    color = config.COLOR_HINT if text == "GO!" else config.COLOR_TEXT
    y = config.INTERNAL_HEIGHT // 2 - font.get_height()
    for centerx in (config.INTERNAL_WIDTH // 5, config.INTERNAL_WIDTH * 4 // 5):
        visuals.blit_outlined_text_centered(surface, font, text, color, centerx, y)


def _panel(surface: pygame.Surface, box: pygame.Rect) -> None:
    pygame.draw.rect(surface, config.COLOR_BACKGROUND, box, border_radius=6)
    pygame.draw.rect(surface, config.COLOR_TOWER, box, 2, border_radius=6)


def draw_finish_banner(
    surface: pygame.Surface,
    big_font: pygame.font.Font,
    time_font: pygame.font.Font,
    small_font: pygame.font.Font,
    time_text: str,
    note: str,
) -> None:
    """The top floor reached: the final time, and a line on what comes next."""
    centerx = config.INTERNAL_WIDTH // 2
    width = max(big_font.size("TOP REACHED!")[0], small_font.size(note)[0]) + 32
    box = pygame.Rect(0, 0, width, 92)
    box.center = (centerx, config.INTERNAL_HEIGHT // 2)
    _panel(surface, box)
    visuals.blit_outlined_text_centered(
        surface, big_font, "TOP REACHED!", config.COLOR_TARGET, centerx, box.y + 12
    )
    visuals.blit_outlined_text_centered(
        surface, time_font, time_text, config.COLOR_TEXT, centerx, box.y + 36
    )
    visuals.blit_outlined_text_centered(
        surface, small_font, note, config.COLOR_HINT, centerx, box.bottom - 18
    )


LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class NameEntry:
    """Three initials, as in Gate Drop: the stick changes the letter (up =
    next) and moves the cursor, A moves on and finishes on the last letter,
    B steps back."""

    def __init__(self) -> None:
        self.letters = [0, 0, 0]
        self.pos = 0
        self.done = False

    @property
    def name(self) -> str:
        return "".join(LETTERS[i] for i in self.letters)

    def update(self, dx: int, dy: int, confirm: bool, back: bool) -> bool:
        """One frame's presses: dx and dy are -1, 0 or 1 (screen directions,
        so dy = -1 is up). Returns whether anything was pressed."""
        if dy:
            self.letters[self.pos] = (self.letters[self.pos] - dy) % len(LETTERS)
        if dx:
            self.pos = max(0, min(2, self.pos + dx))
        if confirm:
            if self.pos < 2:
                self.pos += 1
            else:
                self.done = True
        if back:
            self.pos = max(0, self.pos - 1)
        return bool(dx or dy or confirm or back)


class AutoRepeat:
    """Turns a held direction (-1, 0 or 1) into presses: one at once, then one
    after `delay`, then one every `interval`, so a held stick scrolls through
    the letters."""

    def __init__(
        self, delay: float = config.NAME_REPEAT_DELAY, interval: float = config.NAME_REPEAT_INTERVAL
    ) -> None:
        self.delay, self.interval = delay, interval
        self.held = 0
        self.timer = 0.0

    def update(self, dt: float, value: int) -> int:
        if value == 0:
            self.held = 0
            return 0
        if value != self.held:
            self.held = value
            self.timer = self.delay
            return value
        self.timer -= dt
        if self.timer <= 0:
            self.timer += self.interval
            return value
        return 0


def initials_hint(entry: NameEntry) -> str:
    """The footer, saying what A does from where the cursor is."""
    return f"STICK: LETTER   A: {'DONE' if entry.pos == 2 else 'NEXT'}   B: BACK"


def _draw_arrow(surface: pygame.Surface, centerx: int, tip_y: int, pointing_up: bool) -> None:
    """A small filled triangle, 9 px wide and 5 px tall, tip at tip_y."""
    base_y = tip_y + 4 if pointing_up else tip_y - 4
    points = [(centerx, tip_y), (centerx - 4, base_y), (centerx + 4, base_y)]
    pygame.draw.polygon(surface, config.COLOR_HINT, points)


def draw_initials(
    surface: pygame.Surface,
    title_font: pygame.font.Font,
    letter_font: pygame.font.Font,
    small_font: pygame.font.Font,
    entry: NameEntry,
    time_text: str,
    t: float,
) -> None:
    surface.fill(config.COLOR_BACKGROUND)
    centerx = config.INTERNAL_WIDTH // 2
    visuals.blit_outlined_text_centered(
        surface, title_font, "A TOP 10 CLEAR!", config.COLOR_TARGET, centerx, 30
    )
    visuals.blit_outlined_text_centered(surface, title_font, time_text, config.COLOR_TEXT, centerx, 56)
    visuals.blit_outlined_text_centered(
        surface, small_font, "ENTER YOUR INITIALS", config.COLOR_TEXT, centerx, 88
    )
    for i, letter in enumerate(entry.name):
        box = pygame.Rect(centerx - 60 + i * 44, 118, 32, 40)
        active = i == entry.pos
        accent = config.COLOR_HINT if active else config.COLOR_TOWER
        pygame.draw.rect(surface, config.COLOR_TOWER_TRIM, box, border_radius=5)
        pygame.draw.rect(surface, accent, box, 2, border_radius=5)
        visuals.blit_outlined_text_centered(
            surface, letter_font, letter, accent if active else config.COLOR_TEXT, box.centerx,
            box.centery - letter_font.get_height() // 2,
        )
        if active and blink_visible(t, 0.5):
            _draw_arrow(surface, box.centerx, box.y - 9, pointing_up=True)
            _draw_arrow(surface, box.centerx, box.bottom + 8, pointing_up=False)
    visuals.blit_outlined_text_centered(
        surface, small_font, initials_hint(entry), config.COLOR_TOWER, centerx,
        config.INTERNAL_HEIGHT - 22,
    )


def draw_times_table(
    surface: pygame.Surface,
    title_font: pygame.font.Font,
    row_font: pygame.font.Font,
    small_font: pygame.font.Font,
    entries: list,
    new_rank: int | None,
    t: float,
) -> None:
    """FASTEST CLEARS: rank, initials and time, with the new entry blinking.
    `entries` are times.Entry (name, seconds), fastest first. `t` is the
    seconds on this screen; the A: CONTINUE hint shows once it takes input."""
    surface.fill(config.COLOR_BACKGROUND)
    centerx = config.INTERNAL_WIDTH // 2
    visuals.blit_outlined_text_centered(
        surface, title_font, "FASTEST CLEARS", config.COLOR_TARGET, centerx, 14
    )
    box = pygame.Rect(centerx - 130, 40, 260, 196)
    _panel(surface, box)
    if not entries:
        visuals.blit_outlined_text_centered(
            surface, small_font, "NO CLEARS YET - BE THE FIRST!", config.COLOR_TEXT, centerx,
            box.centery - small_font.get_height() // 2,
        )
    for i, entry in enumerate(entries):
        fresh = i == new_rank
        if fresh and not blink_visible(t, 0.5):
            continue
        y = box.y + 10 + i * 18
        color = config.COLOR_HINT if fresh else config.COLOR_TEXT
        for x, text in (
            (box.x + 41, f"{i + 1:>2}."), (box.x + 95, entry.name), (box.x + 149, format_time(entry.seconds)),
        ):
            visuals.blit_outlined_text(surface, row_font, text, color, (x, y))
    if t >= config.TIMES_TABLE_LOCK:
        visuals.blit_outlined_text_centered(
            surface, small_font, "A: CONTINUE", config.COLOR_TOWER, centerx, config.INTERNAL_HEIGHT - 22
        )
