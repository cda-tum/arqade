"""Smooth, procedurally-drawn scene: sky/grass background, a stone tower
taller than the viewport (scrolled via a camera that eases toward the
player's floor), and a climber scaling its outer wall.

Anti-aliased shapes via pygame.gfxdraw and simple shading/highlights, rather
than flat single-color pixel-art rects -- deliberately a step up from Quantum
Pong's retro-arcade look, per design direction. Not unit tested: pure
pygame-Surface drawing, verified by running the game.
"""

from __future__ import annotations

import math

import pygame
import pygame.gfxdraw

from quantum_towers import config
from quantum_towers.notation import render_state
from quantum_towers.quantum import State

TOWER_WIDTH_RATIO = 0.55  # fraction of the region's width the tower body occupies

Color = tuple[int, int, int]


def _lighten(color: Color, amount: float) -> Color:
    return tuple(min(255, round(c + (255 - c) * amount)) for c in color)


def _darken(color: Color, amount: float) -> Color:
    return tuple(max(0, round(c * (1 - amount))) for c in color)


def _luminance(color: Color) -> float:
    return 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]


def _contrasting_text_color(background: Color) -> Color:
    """Dark text on light backgrounds, light text on dark ones -- readability
    was the #1 complaint, and a fixed text color against varying panel colors
    (e.g. white-on-gold) was a real contrast failure, not just a size issue."""
    return config.COLOR_TEXT_SHADOW if _luminance(background) > 150 else config.COLOR_TEXT


def _aa_filled_circle(surface: pygame.Surface, x: int, y: int, radius: int, color: Color) -> None:
    pygame.gfxdraw.filled_circle(surface, x, y, radius, color)
    pygame.gfxdraw.aacircle(surface, x, y, radius, color)


# --- Background -------------------------------------------------------------


def _draw_vertical_gradient(
    surface: pygame.Surface, rect: pygame.Rect, top_color: Color, bottom_color: Color, bands: int = 10
) -> None:
    band_h = rect.height / bands
    for i in range(bands):
        frac = i / (bands - 1)
        color = tuple(round(top_color[c] + (bottom_color[c] - top_color[c]) * frac) for c in range(3))
        band_rect = pygame.Rect(rect.x, round(rect.y + i * band_h), rect.width, round(band_h) + 1)
        pygame.draw.rect(surface, color, band_rect)


def _draw_cloud(surface: pygame.Surface, x: int, y: int) -> None:
    for dx, dy, r in ((-14, 4, 9), (0, -4, 13), (14, 4, 9), (25, 3, 7)):
        _aa_filled_circle(surface, x + dx, y + dy, r, config.COLOR_CLOUD)


def make_background(width: int, height: int) -> pygame.Surface:
    """Static-per-match scene (sky, sun, clouds, grass) -- rendered once and
    blitted each frame rather than redrawn, since none of it animates."""
    surface = pygame.Surface((width, height))
    horizon_y = round(height * 0.6)

    sky_rect = pygame.Rect(0, 0, width, horizon_y)
    _draw_vertical_gradient(surface, sky_rect, config.COLOR_SKY_TOP, config.COLOR_SKY_BOTTOM)

    _aa_filled_circle(surface, width - 46, 36, 20, config.COLOR_SUN)
    _draw_cloud(surface, 70, 34)
    _draw_cloud(surface, width // 2 + 10, 54)

    grass_rect = pygame.Rect(0, horizon_y, width, height - horizon_y)
    pygame.draw.rect(surface, config.COLOR_GRASS, grass_rect)
    pygame.draw.rect(surface, config.COLOR_GRASS_DARK, (0, horizon_y, width, 5))
    # a few short grass-blade tufts for texture, cheap fixed set of lines
    for x in range(6, width, 17):
        blade_h = 5 + (x % 3) * 2
        pygame.draw.line(
            surface, config.COLOR_GRASS_DARK, (x, horizon_y + 3), (x, horizon_y + 3 + blade_h), 2
        )

    return surface


# --- Climber -----------------------------------------------------------------


def draw_climber(
    surface: pygame.Surface,
    wall_x: int,
    y: int,
    color: Color,
    t: float,
    facing: int,
    climb_progress: float | None = None,
    attack_progress: float | None = None,
    stun_progress: float | None = None,
) -> None:
    """A humanoid clinging to and scaling a vertical wall at x=wall_x (the
    tower's edge), feet-level at `y`. `facing` is +1 (wall is to the right)
    or -1 (wall is to the left): the whole pose leans and reaches toward it.

    `climb_progress`, when given (0..1, during a floor change), drives a
    one-shot reach-and-pull arc plus a small rise-and-settle bob, instead of
    the idle gentle sway used the rest of the time -- a continuous idle sway
    alone reads as "standing," not "climbing"; this is what actually sells
    the motion when a floor is gained or lost.

    `attack_progress` (0..1, during the attack-beam window), when given,
    thrusts a free arm out toward the opponent -- away from this climber's
    own wall, i.e. -facing -- so firing an attack reads as the character
    doing something, not just a beam appearing from nowhere.

    `stun_progress` (0..1, while locked out after confirming on the wrong
    state), when given, overrides the pose with a fast side-to-side jitter,
    so a punished wrong confirm reads as "that hurt," not "nothing happened."
    """
    if stun_progress is not None:
        jitter = round(math.sin(stun_progress * 50.0) * 3)
    else:
        jitter = 0

    if climb_progress is not None:
        reach = math.sin(climb_progress * math.pi)  # 0 -> 1 -> 0: reach, then pull through
        bob = -round(reach * 5)
    else:
        reach = math.sin(t * 5.0) * 0.5 + 0.5
        bob = 0

    y += bob
    body_x = wall_x - facing * 9 + jitter  # body offset out from the wall, leaning in
    lean = facing * 4

    hip = (body_x, y - 9)
    shoulder = (body_x + lean, hip[1] - 14)
    head_center = (shoulder[0] + lean // 2, shoulder[1] - 8)

    near_foot = (wall_x, y)
    far_foot = (wall_x, y - 10 - round(reach * 6))
    pygame.draw.line(surface, color, hip, near_foot, 3)
    pygame.draw.line(surface, color, hip, far_foot, 3)

    upper_hand = (wall_x, shoulder[1] - 10 - round(reach * 10))
    lower_hand = (wall_x, shoulder[1] + 2 - round((1 - reach) * 8))
    pygame.draw.line(surface, color, shoulder, upper_hand, 3)
    pygame.draw.line(surface, color, shoulder, lower_hand, 3)

    pygame.draw.line(surface, color, hip, shoulder, 4)
    _aa_filled_circle(surface, round(head_center[0]), round(head_center[1]), 6, color)

    if attack_progress is not None:
        punch = math.sin(attack_progress * math.pi)  # 0 -> 1 -> 0: thrust out, then draw back
        thrust_dir = -facing
        elbow = (shoulder[0] + thrust_dir * 6, shoulder[1] + 2)
        hand = (shoulder[0] + thrust_dir * (10 + round(punch * 8)), shoulder[1] + 2 - round(punch * 2))
        pygame.draw.line(surface, color, shoulder, elbow, 3)
        pygame.draw.line(surface, color, elbow, hand, 3)


# --- Tower -------------------------------------------------------------------


_OUTLINE_OFFSETS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def blit_outlined_text(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: Color,
    topleft: tuple[int, int],
    outline_color: Color = config.COLOR_TEXT_SHADOW,
) -> pygame.Rect:
    """Draws `text` at `topleft` with a 4-direction outline for contrast --
    needed now that the background is a sky/grass scene, not flat black, so
    plain single-color text can land on a similarly-bright patch of sky.
    Returns the main text's rect (useful for laying out following lines)."""
    outline_surf = font.render(text, False, outline_color)
    main_surf = font.render(text, False, color)
    x, y = topleft
    for dx, dy in _OUTLINE_OFFSETS:
        surface.blit(outline_surf, (x + dx, y + dy))
    surface.blit(main_surf, (x, y))
    return main_surf.get_rect(topleft=topleft)


def blit_outlined_text_centered(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: Color,
    centerx: int,
    y: int,
    outline_color: Color = config.COLOR_TEXT_SHADOW,
) -> pygame.Rect:
    """Same as `blit_outlined_text`, but horizontally centered on `centerx`
    -- used for the always-on button legend, which spans the full screen
    rather than starting from a per-half left margin."""
    width = font.size(text)[0]
    return blit_outlined_text(surface, font, text, color, (centerx - width // 2, y), outline_color)


def _pick_fitting_font(
    fonts_ladder: list[pygame.font.Font], lines: list[str], max_width: int
) -> pygame.font.Font:
    """`fonts_ladder` is biggest-first. A general state like "1/√2|1>@315°"
    is too wide for a block at the normal block font size -- rather than
    truncating or shrinking every label, only drop to a smaller size for the
    (rare) labels that actually need it."""
    for candidate in fonts_ladder:
        if all(candidate.size(line)[0] <= max_width for line in lines):
            return candidate
    return fonts_ladder[-1]


def _draw_wrapped_label(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    fonts_ladder: list[pygame.font.Font],
    color: Color,
) -> None:
    """Renders `label` (split onto multiple lines at " + " if present)
    centered in `rect`, with a 4-direction outline in the opposite brightness
    for contrast against any panel color."""
    outline_color = config.COLOR_TEXT if _luminance(color) < 128 else config.COLOR_TEXT_SHADOW
    lines = label.split(" + ") if " + " in label else [label]
    font = _pick_fitting_font(fonts_ladder, lines, rect.width - 4)
    line_surfs = [font.render(line, False, color) for line in lines]
    outline_surfs = [font.render(line, False, outline_color) for line in lines]
    total_h = sum(s.get_height() for s in line_surfs)
    y = rect.centery - total_h // 2
    for surf, outline_surf in zip(line_surfs, outline_surfs):
        pos = surf.get_rect(centerx=rect.centerx, y=y)
        for dx, dy in _OUTLINE_OFFSETS:
            surface.blit(outline_surf, (pos.x + dx, pos.y + dy))
        surface.blit(surf, pos)
        y += surf.get_height()


def _draw_crenellations(surface: pygame.Surface, rect: pygame.Rect, color: Color) -> None:
    tooth_w = 10
    gap = 8
    x = rect.left + 4
    while x + tooth_w <= rect.right - 4:
        pygame.draw.rect(surface, color, (x, rect.top - 9, tooth_w, 11))
        x += tooth_w + gap


def _floor_kind(floor_number: int, player_floor: int) -> str:
    if floor_number <= player_floor:
        return "cleared"
    if floor_number == player_floor + 1:
        return "current"
    if floor_number == player_floor + 2:
        return "next"
    return "unknown"


def _draw_one_band(
    surface: pygame.Surface,
    band_rect: pygame.Rect,
    kind: str,
    current_target: State,
    next_target: State,
    fonts_ladder: list[pygame.font.Font],
) -> None:
    pygame.draw.line(
        surface, config.COLOR_TOWER_TRIM,
        (band_rect.left + 5, band_rect.bottom), (band_rect.right - 5, band_rect.bottom), 2,
    )

    if kind == "cleared":
        window = pygame.Rect(0, 0, 10, 16)
        window.center = band_rect.center
        pygame.draw.rect(surface, _darken(config.COLOR_TOWER, 0.4), window, border_radius=2)
        return

    fill = {
        "current": config.COLOR_TARGET,
        "next": config.COLOR_NEXT_TARGET,
        "unknown": config.COLOR_UNKNOWN,
    }[kind]
    label = {
        "current": render_state(current_target),
        "next": render_state(next_target),
        "unknown": "?",
    }[kind]

    panel = band_rect.inflate(-20, -12)
    pygame.draw.rect(surface, _darken(config.COLOR_TOWER, 0.35), panel.inflate(6, 6), border_radius=3)
    pygame.draw.rect(surface, fill, panel, border_radius=3)
    _draw_wrapped_label(surface, panel, label, fonts_ladder, _contrasting_text_color(fill))


def _draw_tower_body(
    surface: pygame.Surface,
    rect: pygame.Rect,
    player_floor: int,
    visual_floor: float,
    current_target: State,
    next_target: State,
    fonts_ladder: list[pygame.font.Font],
) -> None:
    """A stone structure taller than `rect`: floor bands are positioned by
    their absolute floor number relative to `visual_floor` (the animated
    camera position), clipped to `rect`, so the tower visibly scrolls past
    as `visual_floor` eases toward `player_floor` -- rather than 4 fixed
    bands whose *labels* silently swap in place, which read as the tower
    sliding rather than the player climbing.

    The roof (the structure's actual top, one band above the final floor)
    only gets its cap drawn once the camera has scrolled close enough that
    it's really within `rect` -- otherwise the tower must visibly keep going
    above the top edge of the viewport, since there are still many floors
    left to climb. Showing the cap right at `rect.top` regardless of
    progress used to make the tower look one floor tall from the very first
    frame.

    Floor TOWER_HEIGHT is the last *real* band -- matching it is the win --
    so it must still render; only floors beyond that are capped off."""
    band_height = config.TOWER_BAND_HEIGHT
    top_floor = config.TOWER_HEIGHT  # the winning floor -- its target band must still render
    roof_y = rect.bottom - (top_floor + 1 - visual_floor) * band_height
    body_top = min(max(rect.top, round(roof_y)), rect.bottom)
    body_rect = pygame.Rect(rect.x, body_top, rect.width, rect.bottom - body_top)

    pygame.draw.rect(surface, _darken(config.COLOR_TOWER, 0.55), body_rect.move(3, 4))
    pygame.draw.rect(surface, config.COLOR_TOWER, body_rect)

    lowest = int(math.floor(visual_floor)) - 1
    highest = min(int(math.ceil(visual_floor + rect.height / band_height)) + 1, top_floor)

    previous_clip = surface.get_clip()
    surface.set_clip(body_rect)
    for f in range(lowest, highest + 1):
        band_bottom = rect.bottom - (f - visual_floor) * band_height
        band_rect = pygame.Rect(rect.x, round(band_bottom - band_height), rect.width, round(band_height))
        if band_rect.bottom < body_top - 2 or band_rect.top > rect.bottom + 2:
            continue
        _draw_one_band(
            surface, band_rect, _floor_kind(f, player_floor), current_target, next_target, fonts_ladder
        )
    surface.set_clip(previous_clip)

    if roof_y >= rect.top:
        _draw_crenellations(surface, body_rect, config.COLOR_TOWER_TRIM)
    pygame.draw.rect(surface, config.COLOR_TOWER_TRIM, body_rect, width=3)
    for x in (rect.left + 3, rect.right - 3):
        pygame.draw.line(surface, config.COLOR_TOWER_TRIM, (x, body_top), (x, rect.bottom), 3)


def draw_tower(
    surface: pygame.Surface,
    region: pygame.Rect,
    player_floor: int,
    visual_floor: float,
    current_target: State,
    next_target: State,
    color: Color,
    fonts_ladder: list[pygame.font.Font],
    t: float,
    climber_side: str = "right",
    climb_progress: float | None = None,
    attack_progress: float | None = None,
    stun_progress: float | None = None,
) -> tuple[int, int]:
    """Draws the tower body (toward one edge of `region`) and the climber
    scaling its wall, facing the other side. `climber_side` is which side of
    the tower body the climber is on ("left" or "right") -- pass "right" for
    the left-hand player (climbs their tower's right wall, toward the middle)
    and "left" for the right-hand player. `fonts_ladder` is biggest-first;
    block labels drop to a smaller size only when the normal size would
    overflow. Returns the climber's (x, y) position in surface coordinates,
    for the attack-beam effect."""
    tower_width = round(region.width * TOWER_WIDTH_RATIO)
    if climber_side == "right":
        tower_rect = pygame.Rect(region.x, region.y, tower_width, region.height)
        wall_x = tower_rect.right
        facing = -1  # wall is to the climber's left
    else:
        tower_rect = pygame.Rect(region.right - tower_width, region.y, tower_width, region.height)
        wall_x = tower_rect.left
        facing = 1  # wall is to the climber's right

    _draw_tower_body(
        surface, tower_rect, player_floor, visual_floor, current_target, next_target, fonts_ladder
    )

    # The climber's screen anchor is fixed (it's the *camera*, via
    # visual_floor, that moves the tower past them) -- climb_progress's pose
    # animation is what actually reads as "I moved," not this position.
    climber_y = round(tower_rect.bottom - config.TOWER_BAND_HEIGHT)
    draw_climber(
        surface, wall_x, climber_y, color, t, facing, climb_progress, attack_progress, stun_progress
    )

    climber_x = wall_x + facing * 10
    return climber_x, climber_y


# --- HUD: button legend, charge bar, celebration/attack effects --------------


def draw_button_grid(
    surface: pygame.Surface,
    center: tuple[int, int],
    grid: list[list[tuple[str, str | None]]],
    gate_font: pygame.font.Font,
    label_font: pygame.font.Font,
    accent_color: Color = config.COLOR_TOWER_TRIM,
    pressed: dict[str, bool] | None = None,
) -> None:
    """The cabinet's real 2x3 button grid, drawn as the same shape: each
    button-shaped box holds the gate it fires, with the physical button's
    own name just beside it -- so a player matches this to their hands
    directly instead of reading a line of text. A cell whose gate is None
    (no action mapped to that button) draws as an empty, dim outline instead
    of a filled box, so it visibly reads as "nothing here" rather than
    silently showing a stale or blank label.

    `accent_color` tints the box borders (and, per-cell, the pressed fill)
    -- since each player has their own independent press state, this is what
    lets two side-by-side grids (one per player, in that player's color)
    read as separate at a glance. `pressed` (gate_name -> currently held)
    makes a held button's box fill with `accent_color` and pop a bright
    border, so a press gives visible feedback even when the gate itself
    does nothing to the target."""
    box_label_gap = 3
    col_gap = 10
    row_gap = 4

    all_gates = [gate for row in grid for _, gate in row if gate is not None]
    all_labels = [label for row in grid for label, _ in row]
    box_w = max(gate_font.size(gate)[0] for gate in all_gates) + 8
    box_h = gate_font.get_height() + 4
    label_w = max(label_font.size(label)[0] for label in all_labels)

    cell_w = box_w + box_label_gap + label_w
    cols = len(grid[0])
    rows = len(grid)
    total_w = cols * cell_w + (cols - 1) * col_gap
    total_h = rows * box_h + (rows - 1) * row_gap
    origin_x = center[0] - total_w // 2
    origin_y = center[1] - total_h // 2

    for row_index, row in enumerate(grid):
        for col_index, (button_label, gate) in enumerate(row):
            box_rect = pygame.Rect(
                origin_x + col_index * (cell_w + col_gap), origin_y + row_index * (box_h + row_gap),
                box_w, box_h,
            )
            if gate is None:
                pygame.draw.rect(surface, accent_color, box_rect, width=1, border_radius=4)
                continue
            is_pressed = bool(pressed and pressed.get(gate))
            if is_pressed:
                fill = accent_color
                pygame.draw.rect(surface, fill, box_rect, border_radius=4)
                pygame.draw.rect(surface, config.COLOR_TEXT, box_rect, width=2, border_radius=4)
            else:
                fill = config.COLOR_TOWER
                pygame.draw.rect(surface, fill, box_rect, border_radius=4)
                pygame.draw.rect(surface, accent_color, box_rect, width=2, border_radius=4)
            gate_surf = gate_font.render(gate, False, _contrasting_text_color(fill))
            surface.blit(gate_surf, gate_surf.get_rect(center=box_rect.center))
            blit_outlined_text(
                surface, label_font, button_label, config.COLOR_TEXT,
                (box_rect.right + box_label_gap, box_rect.centery - label_font.get_height() // 2),
            )


def draw_charge_bar(
    surface: pygame.Surface, rect: pygame.Rect, charges: int, max_charges: int
) -> None:
    """A single bar that fills up toward the attack, with thin ticks marking
    each discrete threshold -- reads as build-up toward one payoff, unlike
    three separate dots which read more like a checklist."""
    pygame.draw.rect(surface, config.COLOR_CHARGE_EMPTY, rect, border_radius=3)
    fill_w = round(rect.width * charges / max_charges)
    if fill_w > 0:
        fill_rect = pygame.Rect(rect.x, rect.y, fill_w, rect.height)
        pygame.draw.rect(surface, config.COLOR_CHARGE_FULL, fill_rect, border_radius=3)
    for i in range(1, max_charges):
        tick_x = rect.x + round(rect.width * i / max_charges)
        pygame.draw.line(surface, config.COLOR_TOWER_TRIM, (tick_x, rect.top), (tick_x, rect.bottom), 1)
    pygame.draw.rect(surface, config.COLOR_TOWER_TRIM, rect, width=2, border_radius=3)


def _draw_radiating_ticks(
    surface: pygame.Surface,
    x: int,
    y: int,
    color: Color,
    progress: float,
    count: int,
    base_radius: int,
    length: int,
) -> None:
    radius = base_radius + round(base_radius * progress)
    for i in range(count):
        angle = 2 * math.pi * i / count
        inner = (x + math.cos(angle) * radius, y + math.sin(angle) * radius)
        outer = (x + math.cos(angle) * (radius + length), y + math.sin(angle) * (radius + length))
        pygame.draw.line(surface, color, inner, outer, 2)


def draw_muzzle_flash(surface: pygame.Surface, x: int, y: int, color: Color, progress: float) -> None:
    """A brief radiating burst at the shooter's position, timed with the
    attack beam, so firing reads as originating from the character."""
    _draw_radiating_ticks(surface, x, y, color, progress, count=6, base_radius=4, length=5)


def draw_perfect_flash(
    surface: pygame.Surface, x: int, y: int, color: Color, progress: float, font: pygame.font.Font
) -> None:
    """Celebration for matching a target in the true minimum number of gate
    presses -- otherwise earning a charge is invisible next to an ordinary
    floor-advance, and the skill involved goes unnoticed."""
    _draw_radiating_ticks(surface, x, y, color, progress, count=8, base_radius=10, length=4 + round(4 * progress))
    label = "PERFECT!"
    rise = round(16 * progress)
    label_w = font.size(label)[0]
    blit_outlined_text(surface, font, label, color, (x - label_w // 2, y - 22 - rise))


def draw_stun_flash(
    surface: pygame.Surface, x: int, y: int, progress: float, font: pygame.font.Font
) -> None:
    """Punishment feedback for confirming a climb on the wrong state -- a
    warning-colored burst plus a label, so getting stunned reads as a clear
    penalty rather than the input silently failing."""
    _draw_radiating_ticks(
        surface, x, y, config.COLOR_STUN, progress, count=8, base_radius=8, length=5
    )
    label = "WRONG!"
    label_w = font.size(label)[0]
    blit_outlined_text(surface, font, label, config.COLOR_STUN, (x - label_w // 2, y - 22))


def draw_push_up_hint(surface: pygame.Surface, x: int, y: int, font: pygame.font.Font) -> None:
    """A nudge shown once a player has been sitting on a correct-but-not-yet-
    confirmed state for a while -- for anyone who hasn't realized matching
    the target no longer climbs by itself."""
    label = "PUSH UP!"
    label_w = font.size(label)[0]
    blit_outlined_text(surface, font, label, config.COLOR_HINT, (x - label_w // 2, y - 22))
