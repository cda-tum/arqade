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


def button_grid(player_key: str = "p1") -> list[list[tuple[str, str | None]]]:
    """The cabinet's 6 physical buttons as they actually sit -- two rows of
    three -- each cell (button_label, gate_name), or (button_label, None)
    for a button with no gate mapped to it. BUTTON_LABELS' index order is
    row-major over that 2x3 grid (indices 0-2 top row, 3-5 bottom row), so
    this never drifts out of sync with the actual mapping. Same button
    layout is assumed for both players' pads."""
    buttons = config.INPUT_CONFIG[player_key]["buttons"]
    gate_by_index = {index: action for action, index in buttons.items()}
    cells = [
        (config.BUTTON_LABELS[i], gate_by_index.get(i)) for i in range(len(config.BUTTON_LABELS))
    ]
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
