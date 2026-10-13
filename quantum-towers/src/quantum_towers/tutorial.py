"""HOW TO PLAY: the card shown before every match started from the title.

The goal in three lines, a looping demo climb, the controls on the cabinet's
own button cluster, and PRESS ANY BUTTON TO START. The demo is not a
recording: `demo_frame` replays a short script of presses through the
game's real rules (player.py), so the tower, the kets and the PERFECT! and
WRONG! flashes are exactly what a match shows. Its button presses also light
the matching button in the controls cluster.

`Dismissal` and `demo_frame` are pure and unit tested; `draw_tutorial` is
pygame drawing glue, like screens.py. The loop that runs the card is
`run_tutorial` in main.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from quantum_towers import config, fonts, screens, visuals
from quantum_towers.notation import render_state
from quantum_towers.player import PlayerState, apply_action, confirm_climb, new_player
from quantum_towers.quantum import apply_h, apply_x, apply_z, zero_state

# Presses in the first GRACE seconds don't dismiss the card: the A or Start
# that picked the mode on the title (or its bounce) must not skip it unseen.
GRACE = 0.3

GOAL_LINES = {
    "2p": (
        "USE GATES TO MAKE YOUR STATE MATCH THE GOLD FLOOR,",
        "THEN PUSH UP TO CLIMB. FIRST TO THE TOP WINS!",
        "3 PERFECT FLOORS KNOCK YOUR RIVAL DOWN!",
    ),
    "1p": (
        "USE GATES TO MAKE YOUR STATE MATCH THE GOLD FLOOR,",
        f"THEN PUSH UP TO CLIMB. REACH FLOOR {config.TOWER_HEIGHT} FAST!",
        "PUSH UP ON A WRONG STATE AND YOU ARE STUNNED.",
    ),
}
PROMPT = "PRESS ANY BUTTON TO START"


class Dismissal:
    """Any button closes the card, but only once it has been up for GRACE
    seconds. Stick moves never count: the caller only reports buttons."""

    def __init__(self) -> None:
        self.age = 0.0

    def update(self, dt: float, button_pressed: bool) -> bool:
        """One frame: `button_pressed` is whether a button went down this
        frame. Returns True when the card should close."""
        self.age += dt
        return button_pressed and self.age >= GRACE


# --- The demo climb -------------------------------------------------------------

# Two floors, the second with a mistake: X and Z make -|1> (a PERFECT floor,
# two presses), then a push up one gate too soon (WRONG!, a second's stun),
# then H and up (PERFECT again).
_T1 = apply_z(apply_x(zero_state()))  # -|1>
_T2 = apply_h(_T1)  # -|->
_T3 = apply_x(_T2)
DEMO_TARGETS = [_T1, _T2, _T3, apply_h(_T3)]
DEMO_SCRIPT: tuple[tuple[float, str], ...] = (
    (0.8, "X"), (1.4, "Z"), (2.0, "UP"), (3.0, "UP"), (4.2, "H"), (4.8, "UP"),
)
DEMO_LOOP = 6.4  # seconds, then it starts over
DEMO_PRESS = 0.25  # how long each scripted press is held (lights its button)


@dataclass(frozen=True)
class DemoFrame:
    player: PlayerState
    visual_floor: float
    climb_progress: float | None
    stun_progress: float | None
    perfect_progress: float | None
    pressed: str | None  # the gate whose button is held right now
    stick_up: bool


def _progress(started: float | None, t: float, duration: float) -> float | None:
    if started is None or not 0 <= t - started < duration:
        return None
    return (t - started) / duration


def demo_frame(t: float) -> DemoFrame:
    """The demo at `t` seconds into the card (it loops every DEMO_LOOP).
    Replays DEMO_SCRIPT up to `t` through apply_action and confirm_climb,
    timing the flashes the way run_game does."""
    t %= DEMO_LOOP
    player = new_player(DEMO_TARGETS)
    climbed_at = perfect_at = stun_at = None
    last: tuple[float, str] | None = None
    for at, move in DEMO_SCRIPT:
        if at > t:
            break
        last = (at, move)
        if move != "UP":
            player = apply_action(player, move)
            continue
        after, advanced = confirm_climb(player, DEMO_TARGETS)
        if advanced:
            climbed_at = at
            if after.charges > player.charges:
                perfect_at = at
            player = after
        else:
            stun_at = at

    climb_progress = _progress(climbed_at, t, config.CLIMB_ANIM_DURATION)
    visual_floor = float(player.floor)
    if climb_progress is not None:
        visual_floor -= (1 - climb_progress) ** 2  # main._camera_step's ease-out
    held = last is not None and t - last[0] < DEMO_PRESS
    return DemoFrame(
        player=player,
        visual_floor=visual_floor,
        climb_progress=climb_progress,
        stun_progress=_progress(stun_at, t, config.STUN_DURATION),
        perfect_progress=_progress(perfect_at, t, config.PERFECT_FLASH_DURATION),
        pressed=last[1] if held and last[1] != "UP" else None,
        stick_up=held and last[1] == "UP",
    )


# --- Drawing ------------------------------------------------------------------

_W, _H = config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT
LINE = 11  # px per line of 8 px text
GOAL_BOX = pygame.Rect(8, 28, _W - 16, 14 + LINE * 4)
CONTROLS_BOX = pygame.Rect(236, GOAL_BOX.bottom + 6, _W - 244, 0)
CONTROLS_BOX.height = _H - 24 - CONTROLS_BOX.y
DEMO_TOWER = pygame.Rect(40, GOAL_BOX.bottom + 12, 150, 0)
DEMO_TOWER.height = _H - 40 - DEMO_TOWER.y


class Card:
    """Fonts and the background for one showing of the card."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.heading_font = fonts.load_font(16)
        self.text_font = fonts.load_font(8)
        # The match's own sizes, so the demo tower looks like the real one.
        self.block_fonts = [fonts.load_font(11), fonts.load_font(9), fonts.load_font(7)]
        self.flash_font = fonts.load_font(9)
        self.grid_font = fonts.load_font(8)
        self.grid = screens.button_grid()
        self.background = visuals.make_background(_W, _H)


def _panel(surface: pygame.Surface, box: pygame.Rect) -> None:
    """The pause menu's panel, over the scene."""
    pygame.draw.rect(surface, config.COLOR_BACKGROUND, box, border_radius=6)
    pygame.draw.rect(surface, config.COLOR_TOWER, box, 2, border_radius=6)


def draw_tutorial(surface: pygame.Surface, card: Card, t: float, show_prompt: bool) -> None:
    """The whole card, `t` seconds after it opened."""
    surface.blit(card.background, (0, 0))
    font = card.text_font
    visuals.blit_outlined_text_centered(
        surface, card.heading_font, "HOW TO PLAY", config.COLOR_TARGET, _W // 2, 6
    )

    _panel(surface, GOAL_BOX)
    visuals.blit_outlined_text(
        surface, font, "GOAL", config.COLOR_TARGET, (GOAL_BOX.x + 8, GOAL_BOX.y + 7)
    )
    for i, line in enumerate(GOAL_LINES[card.mode]):
        visuals.blit_outlined_text(
            surface, font, line, config.COLOR_TEXT, (GOAL_BOX.x + 8, GOAL_BOX.y + 7 + LINE * (i + 1))
        )

    demo = demo_frame(t)
    _draw_demo(surface, card, demo, t)
    _draw_controls(surface, card, demo)

    if show_prompt:
        visuals.blit_outlined_text_centered(surface, font, PROMPT, config.COLOR_FPS, _W // 2, _H - 14)


def _draw_demo(surface: pygame.Surface, card: Card, demo: DemoFrame, t: float) -> None:
    """One climber on one tower, and the match's own button legend lighting
    up with each press, all drawn by the match's own functions."""
    color = config.COLOR_PLAYER_1
    x, y = visuals.draw_tower(
        surface, DEMO_TOWER, demo.player.floor, demo.visual_floor, demo.player.current_target,
        demo.player.next_target, color, card.block_fonts, t, climber_side="right",
        climb_progress=demo.climb_progress, stun_progress=demo.stun_progress,
    )
    if demo.perfect_progress is not None:
        visuals.draw_perfect_flash(surface, x, y, color, demo.perfect_progress, card.flash_font)
    if demo.stun_progress is not None:
        visuals.draw_stun_flash(surface, x, y, demo.stun_progress, card.flash_font)

    tower_right = DEMO_TOWER.x + round(DEMO_TOWER.width * visuals.TOWER_WIDTH_RATIO)
    visuals.draw_button_grid(
        surface, ((tower_right + CONTROLS_BOX.x) // 2 + 8, DEMO_TOWER.bottom - 18), card.grid,
        card.grid_font, accent_color=color, pressed={demo.pressed: True} if demo.pressed else None,
    )

    info_y = DEMO_TOWER.bottom + 6
    you = visuals.blit_outlined_text(surface, card.flash_font, "YOU:", color, (DEMO_TOWER.x, info_y))
    visuals.blit_outlined_text(
        surface, card.flash_font, render_state(demo.player.state), config.COLOR_TEXT,
        (you.right + 4, info_y),
    )


# The cluster's geometry: a round button with its printed letter, and beside
# it the gate it fires, in the in-game legend's square.
_BUTTON_R = 9
_BOX = 16
_CELL_W = 2 * _BUTTON_R + 3 + _BOX
_COL_GAP = 7
_ROW_H = 2 * _BUTTON_R + 8


def _draw_button(
    surface: pygame.Surface,
    font: pygame.font.Font,
    center: tuple[int, int],
    label: str,
    gate: str | None,
    pressed: bool,
) -> None:
    """One cabinet button: the printed label on the cap, then its gate.
    An unused button (no gate) is a dim outline, as in the in-game legend."""
    cx, cy = center
    if gate is None:
        pygame.draw.circle(surface, config.COLOR_TOWER_TRIM, center, _BUTTON_R, 2)
        text = font.render(label, False, config.COLOR_TOWER)
        surface.blit(text, text.get_rect(center=(cx + 1, cy + 1)))
        return
    cap = config.COLOR_TARGET if pressed else config.COLOR_TEXT
    pygame.draw.circle(surface, cap, center, _BUTTON_R)
    if pressed:
        pygame.draw.circle(surface, config.COLOR_TEXT, center, _BUTTON_R + 2, 1)
    text = font.render(label, False, config.COLOR_TEXT_SHADOW)
    surface.blit(text, text.get_rect(center=(cx + 1, cy + 1)))

    box = pygame.Rect(cx + _BUTTON_R + 3, cy - _BOX // 2, _BOX, _BOX)
    fill = config.COLOR_TARGET if pressed else config.COLOR_TOWER
    pygame.draw.rect(surface, fill, box, border_radius=3)
    pygame.draw.rect(surface, config.COLOR_TEXT if pressed else config.COLOR_TARGET, box, 2, border_radius=3)
    ink = visuals._contrasting_text_color(fill)
    if gate == "RESET":
        visuals.draw_reset_icon(surface, box.center, ink)
    else:
        gate_surf = font.render(gate, False, ink)
        surface.blit(gate_surf, gate_surf.get_rect(center=(box.centerx + 1, box.centery + 1)))


def _draw_stick(surface: pygame.Surface, center: tuple[int, int], up: bool) -> None:
    """The stick from above-front: a base, the shaft, and the ball top, which
    leans up while the demo pushes."""
    cx, cy = center
    pygame.draw.ellipse(surface, config.COLOR_TOWER_TRIM, (cx - 12, cy + 4, 24, 9))
    pygame.draw.ellipse(surface, config.COLOR_TOWER, (cx - 12, cy + 4, 24, 9), 1)
    ball = (cx, cy - 10 if up else cy - 4)
    pygame.draw.line(surface, config.COLOR_TOWER, (cx, cy + 8), ball, 3)
    pygame.draw.circle(surface, config.COLOR_TARGET if up else config.COLOR_TEXT, ball, 7)
    if up:
        # a small arrow above, the way it is pushed
        pygame.draw.polygon(surface, config.COLOR_HINT, [(cx, cy - 26), (cx - 4, cy - 21), (cx + 4, cy - 21)])


def _draw_controls(surface: pygame.Surface, card: Card, demo: DemoFrame) -> None:
    box = CONTROLS_BOX
    font = card.text_font
    _panel(surface, box)
    left = box.x + 8
    visuals.blit_outlined_text(surface, font, "CONTROLS", config.COLOR_TARGET, (left, box.y + 7))

    top = box.y + 24
    # The printed layout, L X R over Y B A, each with the gate it fires.
    cluster_w = 3 * _CELL_W + 2 * _COL_GAP
    origin_x = box.right - 8 - cluster_w
    _draw_stick(surface, ((box.x + origin_x) // 2, top + _ROW_H // 2 + 9), demo.stick_up)
    for i, (label, gate) in enumerate(zip(config.BUTTON_LABELS, config.GATE_AT_POSITION)):
        row, col = divmod(i, 3)
        center = (origin_x + col * (_CELL_W + _COL_GAP) + _BUTTON_R, top + _BUTTON_R + row * _ROW_H)
        _draw_button(surface, font, center, label, gate, pressed=gate is not None and demo.pressed == gate)

    y = top + 2 * _ROW_H + 4
    step = LINE + 2
    lines = ("STICK UP: CLIMB", "X Y Z H: GATES", "  : RESET TO |0>", "START: PAUSE")
    for i, text in enumerate(lines):
        visuals.blit_outlined_text(surface, font, text, config.COLOR_TEXT, (left, y + i * step))
    # The RESET icon stands in for the word, as on the legend.
    visuals.draw_reset_icon(surface, (left + 6, y + 2 * step + 4), config.COLOR_TEXT)

    who_y = box.bottom - 8 - 8
    if card.mode == "2p":
        p1 = visuals.blit_outlined_text(surface, font, "P1: LEFT", config.COLOR_PLAYER_1, (left, who_y))
        visuals.blit_outlined_text(surface, font, "P2: RIGHT", config.COLOR_PLAYER_2, (p1.right + 16, who_y))
    else:
        visuals.blit_outlined_text(surface, font, "EITHER PAD PLAYS", config.COLOR_PLAYER_1, (left, who_y))
