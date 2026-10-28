"""Title/attract and winner screens, and the pause menu overlay.

The rendering functions here are pygame-drawing glue (not unit tested, same
convention as main.py) except `blink_visible`, which is plain, pure timing
logic worth testing on its own.
"""

from __future__ import annotations

import pygame

from arqade_common import keycaps

from quantum_pong import config
from quantum_pong.pause import PAUSE_ITEMS
from quantum_pong.title import TITLE_ITEMS

LEGEND_LINES = [
    "H: split the ball in two",
    "X: bounce left / right",
    "Z: bounce up / down",
    "SWAP: teleport + reverse",
]


def blink_visible(t: float, period: float) -> bool:
    """True for the first half of each `period`-second cycle."""
    return (t % period) < (period / 2)


def _draw_items(
    surface: pygame.Surface,
    font: pygame.font.Font,
    items: tuple[str, ...],
    selected: int,
    center_x: int,
    top_y: int,
) -> None:
    """A vertical menu, the selected row in the highlight colour with a '>'."""
    for i, item in enumerate(items):
        active = i == selected
        color = config.COLOR_FPS if active else config.COLOR_TEXT
        item_surf = font.render(item, False, color)
        rect = item_surf.get_rect(center=(center_x, top_y + i * 18))
        surface.blit(item_surf, rect)
        if active:
            arrow = font.render(">", False, color)
            surface.blit(arrow, arrow.get_rect(midright=(rect.left - 8, rect.centery)))


def draw_title_screen(
    surface: pygame.Surface,
    title_font: pygame.font.Font,
    legend_font: pygame.font.Font,
    item_font: pygame.font.Font,
    prompt_font: pygame.font.Font,
    selected: int,
    show_prompt: bool,
    start_label: str = "START",
) -> None:
    """`start_label` names Start for the players' devices, e.g. "SPACE / ENTER"."""
    surface.fill(config.COLOR_BACKGROUND)

    title = title_font.render("QUANTUM PONG", False, config.COLOR_TEXT)
    surface.blit(title, title.get_rect(center=(config.INTERNAL_WIDTH // 2, 40)))

    y = 88
    for line in LEGEND_LINES:
        line_surf = legend_font.render(line, False, config.COLOR_TEXT)
        surface.blit(line_surf, line_surf.get_rect(center=(config.INTERNAL_WIDTH // 2, y)))
        y += 18

    _draw_items(surface, item_font, TITLE_ITEMS, selected, config.INTERNAL_WIDTH // 2, 182)

    if show_prompt:
        prompt = prompt_font.render(f"PRESS {start_label}", False, config.COLOR_FPS)
        surface.blit(
            prompt, prompt.get_rect(center=(config.INTERNAL_WIDTH // 2, config.INTERNAL_HEIGHT - 22))
        )


def draw_winner_screen(
    surface: pygame.Surface,
    big_font: pygame.font.Font,
    small_font: pygame.font.Font,
    winner_label: str,
    score: dict[str, int],
) -> None:
    surface.fill(config.COLOR_BACKGROUND)

    text = big_font.render(f"{winner_label} WINS", False, config.COLOR_TEXT)
    surface.blit(
        text, text.get_rect(center=(config.INTERNAL_WIDTH // 2, config.INTERNAL_HEIGHT // 2 - 20))
    )

    score_surf = small_font.render(f"{score['p1']} - {score['p2']}", False, config.COLOR_TEXT)
    surface.blit(
        score_surf,
        score_surf.get_rect(center=(config.INTERNAL_WIDTH // 2, config.INTERNAL_HEIGHT // 2 + 20)),
    )


def draw_pause_menu(
    surface: pygame.Surface,
    big_font: pygame.font.Font,
    item_font: pygame.font.Font,
    hint_font: pygame.font.Font,
    selected: int,
    hint_text: str | tuple = "A: PICK   START / B: RESUME",
) -> None:
    """Centred box over the frozen field, which the caller has already drawn.
    `hint_text` names the buttons for the device of whoever is using the menu:
    text for a pad, or keycap hints for the keyboard (see keycaps.draw_key_hint)."""
    veil = pygame.Surface((config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT), pygame.SRCALPHA)
    veil.fill((*config.COLOR_BACKGROUND, 170))
    surface.blit(veil, (0, 0))

    box = pygame.Rect(0, 0, 264, 112)
    box.center = (config.INTERNAL_WIDTH // 2, config.INTERNAL_HEIGHT // 2)
    pygame.draw.rect(surface, config.COLOR_BACKGROUND, box, border_radius=6)
    pygame.draw.rect(surface, config.COLOR_TEXT, box, width=2, border_radius=6)

    title = big_font.render("PAUSED", False, config.COLOR_TEXT)
    surface.blit(title, title.get_rect(center=(box.centerx, box.y + 20)))

    _draw_items(surface, item_font, PAUSE_ITEMS, selected, box.centerx, box.y + 48)

    if isinstance(hint_text, str):
        hint = hint_font.render(hint_text, False, config.COLOR_HINT)
        surface.blit(hint, hint.get_rect(center=(box.centerx, box.bottom - 14)))
    else:
        width = keycaps.key_hint_size(hint_font, hint_text)[0]
        keycaps.draw_key_hint(surface, hint_font, hint_text, (box.centerx - width // 2, box.bottom - 14),
                              config.COLOR_BACKGROUND, config.COLOR_HINT, config.COLOR_TEXT, config.COLOR_HINT)
