"""Title/attract and winner screens.

The rendering functions here are pygame-drawing glue (not unit tested, same
convention as main.py) except `blink_visible`, which is plain, pure timing
logic worth testing on its own.
"""

from __future__ import annotations

import pygame

from quantum_towers import config, visuals

LEGEND_LINES = [
    "Apply gates to match the target state",
    "Phase matters -- watch the sign / i!",
    "X Y Z: Pauli   H: Hadamard   RESET: |0>",
    "Match it in the minimum presses for a charge",
    "Push UP to confirm -- wrong state stuns you!",
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
    grid_label_font: pygame.font.Font,
    show_prompt: bool,
    p1_pressed: dict[str, bool] | None = None,
    p2_pressed: dict[str, bool] | None = None,
) -> None:
    surface.fill(config.COLOR_BACKGROUND)

    title = title_font.render("QUANTUM TOWERS", False, config.COLOR_TEXT)
    surface.blit(title, title.get_rect(center=(config.INTERNAL_WIDTH // 2, 40)))

    y = 90
    for line in LEGEND_LINES:
        line_surf = legend_font.render(line, False, config.COLOR_TEXT)
        surface.blit(line_surf, line_surf.get_rect(center=(config.INTERNAL_WIDTH // 2, y)))
        y += 20

    y += 14
    grid = button_grid()
    visuals.draw_button_grid(
        surface, (config.INTERNAL_WIDTH // 4, y), grid, grid_gate_font, grid_label_font,
        accent_color=config.COLOR_PLAYER_1, pressed=p1_pressed,
    )
    visuals.draw_button_grid(
        surface, (config.INTERNAL_WIDTH * 3 // 4, y), grid, grid_gate_font, grid_label_font,
        accent_color=config.COLOR_PLAYER_2, pressed=p2_pressed,
    )

    if show_prompt:
        prompt = prompt_font.render("PRESS START", False, config.COLOR_FPS)
        surface.blit(
            prompt, prompt.get_rect(center=(config.INTERNAL_WIDTH // 2, config.INTERNAL_HEIGHT - 28))
        )


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
