"""Title/attract and winner screens.

The rendering functions here are pygame-drawing glue (not unit tested, same
convention as main.py) except `blink_visible`, which is plain, pure timing
logic worth testing on its own.
"""

from __future__ import annotations

import pygame

from quantum_pong import config

LEGEND_LINES = [
    "H: split the ball in two",
    "X: bounce left / right",
    "Z: bounce up / down",
    "SWAP: teleport + reverse",
]


def blink_visible(t: float, period: float) -> bool:
    """True for the first half of each `period`-second cycle."""
    return (t % period) < (period / 2)


def draw_title_screen(
    surface: pygame.Surface,
    title_font: pygame.font.Font,
    legend_font: pygame.font.Font,
    prompt_font: pygame.font.Font,
    show_prompt: bool,
) -> None:
    surface.fill(config.COLOR_BACKGROUND)

    title = title_font.render("QUANTUM PONG", False, config.COLOR_TEXT)
    surface.blit(title, title.get_rect(center=(config.INTERNAL_WIDTH // 2, 46)))

    y = 110
    for line in LEGEND_LINES:
        line_surf = legend_font.render(line, False, config.COLOR_TEXT)
        surface.blit(line_surf, line_surf.get_rect(center=(config.INTERNAL_WIDTH // 2, y)))
        y += 20

    if show_prompt:
        prompt = prompt_font.render("PRESS A OR START", False, config.COLOR_FPS)
        surface.blit(
            prompt, prompt.get_rect(center=(config.INTERNAL_WIDTH // 2, config.INTERNAL_HEIGHT - 28))
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
