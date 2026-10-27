"""HOW TO PLAY card, shown before every match started from the title.

Three parts:

- `DismissGate` (pure): when a button press may dismiss the card. Any button
  on either pad does, but not in the first TUTORIAL_IGNORE_SECONDS, so the A
  or Start that left the title (or its bounce) can't skip it unseen.
- `DemoScene` (pure): a looping mini-match played by the game's own rules
  (pong.py, gates.py). Each scene announces one gate as a dashed outline,
  then it appears and a served ball runs into it -- H, X, Z and SWAP in turn.
  Both paddles return everything, so the scene never stalls.
- `TutorialCard`: draws the card with the game's own sprites (sprites.py).
  pygame glue, not unit tested, like screens.py.

main.py runs the screen's loop (`run_tutorial_screen`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pygame
from arqade_common.input import KEYBOARD, PAD, PLAYERS, LastDevice

from quantum_pong import config, fonts, sprites
from quantum_pong.gates import Gate, check_gate_collisions, is_live
from quantum_pong.pong import (
    Ball,
    Paddle,
    move_paddle,
    reached_left_paddle_line,
    reached_right_paddle_line,
    resolve_ball_at_paddle,
    step_ball,
)

# --- The demo field, in internal-resolution px. It is centred horizontally,
# so SWAP (which mirrors x across the whole screen) mirrors within it too.
# Simulation y runs 0..FIELD_HEIGHT; drawing shifts it down by FIELD_TOP.
FIELD_LEFT = 40
FIELD_WIDTH = config.INTERNAL_WIDTH - 2 * FIELD_LEFT
FIELD_TOP = 74
FIELD_HEIGHT = 110
LEFT_PADDLE_X = FIELD_LEFT + 6
RIGHT_PADDLE_X = FIELD_LEFT + FIELD_WIDTH - 6 - config.PADDLE_WIDTH

DEMO_KINDS = ("H", "X", "Z", "SWAP")
CAPTIONS = {
    "H": "H: SPLITS THE BALL IN TWO",
    "X": "X: BOUNCES IT LEFT / RIGHT",
    "Z": "Z: BOUNCES IT UP / DOWN",
    "SWAP": "SWAP: TELEPORTS + REVERSES IT",
}
WARNING_CAPTION = "DASHED: A GATE IS ABOUT TO APPEAR"

GOAL_LINES = (
    "MOVE YOUR PADDLE TO RETURN THE BALL.",
    "SCORE BY GETTING IT PAST THE OTHER ONE.",
    f"FIRST TO {config.WINNING_SCORE} WINS.  P1 LEFT, P2 RIGHT.",
)

# The served ball reaches the gate this long after the gate has appeared.
_HIT_AFTER_LIVE = 0.3


@dataclass
class DismissGate:
    """Whether this frame's button press dismisses the card."""

    age: float = 0.0  # seconds the card has been up

    def update(self, dt: float, pressed: bool) -> bool:
        """Advance one frame. `pressed`: a button went down this frame (an
        event, so a button merely held since before the card opened, or a
        stick, never counts). True once the card should close."""
        self.age += dt
        return pressed and self.age >= config.TUTORIAL_IGNORE_SECONDS


def _serve(kind: str) -> tuple[Ball, float, Gate]:
    """The scene's ball (resting on the left paddle), when it launches, and
    the gate: announced at t=0 at mid-field, appearing GATE_WARNING_SECONDS
    later, just before the ball gets there."""
    gate = Gate(
        kind=kind, x=config.INTERNAL_WIDTH / 2, y=FIELD_HEIGHT / 2,
        spawned_at=config.GATE_WARNING_SECONDS,
    )
    x0 = LEFT_PADDLE_X + config.PADDLE_WIDTH + config.BALL_RADIUS + 1
    y0 = gate.y - 30
    dx, dy = gate.x - x0, gate.y - y0
    distance = math.hypot(dx, dy)
    speed = config.BALL_START_SPEED
    ball = Ball(x=x0, y=y0, vx=speed * dx / distance, vy=speed * dy / distance)
    travel = (distance - config.GATE_RADIUS - config.BALL_RADIUS) / speed
    launch_at = max(0.0, gate.spawned_at + _HIT_AFTER_LIVE - travel)
    return ball, launch_at, gate


def _centred(paddle_center: float) -> Paddle:
    y = min(max(paddle_center - config.PADDLE_HEIGHT / 2, 0.0), FIELD_HEIGHT - config.PADDLE_HEIGHT)
    return Paddle(y=y, height=config.PADDLE_HEIGHT)


@dataclass
class DemoScene:
    """The looping demo, one gate kind per TUTORIAL_SCENE_SECONDS scene."""

    scene: int = 0
    t: float = 0.0  # seconds into the current scene
    balls: list[Ball] = field(default_factory=list)
    gates: list[Gate] = field(default_factory=list)
    flashes: list[tuple[float, float, float]] = field(default_factory=list)
    left: Paddle = field(default_factory=lambda: _centred(FIELD_HEIGHT / 2))
    right: Paddle = field(default_factory=lambda: _centred(FIELD_HEIGHT / 2))
    launch_at: float = 0.0

    def __post_init__(self) -> None:
        self._reset()

    @property
    def kind(self) -> str:
        return DEMO_KINDS[self.scene % len(DEMO_KINDS)]

    def _reset(self) -> None:
        ball, self.launch_at, gate = _serve(self.kind)
        self.t = 0.0
        self.balls, self.gates, self.flashes = [ball], [gate], []
        self.left, self.right = _centred(ball.y), _centred(FIELD_HEIGHT / 2)

    def gate_is_live(self) -> bool:
        return any(is_live(g, self.t) for g in self.gates)

    def _track(self, paddle: Paddle, toward: int, dt: float) -> Paddle:
        """Follow the nearest ball heading this paddle's way, a little above
        its centre so the return comes off at an angle."""
        coming = [b for b in self.balls if b.vx * toward > 0]
        if not coming:
            return paddle
        line = LEFT_PADDLE_X if toward < 0 else RIGHT_PADDLE_X
        target = min(coming, key=lambda b: abs(b.x - line)).y + 6
        gap = target - (paddle.y + paddle.height / 2)
        direction = 0 if abs(gap) < 2 else (1 if gap > 0 else -1)
        return move_paddle(paddle, direction, dt, FIELD_HEIGHT)

    def step(self, dt: float) -> None:
        self.t += dt
        if self.t >= config.TUTORIAL_SCENE_SECONDS:
            self.scene += 1
            self._reset()
            return
        self.flashes = [f for f in self.flashes if self.t - f[2] < config.FLASH_DURATION]
        if self.t < self.launch_at:
            return  # the ball waits on the left paddle until its serve

        self.left = self._track(self.left, -1, dt)
        self.right = self._track(self.right, 1, dt)
        balls = [step_ball(b, dt, FIELD_HEIGHT, config.BALL_RADIUS) for b in self.balls]
        balls, self.gates = check_gate_collisions(balls, self.gates, config.BALL_RADIUS, self.t)

        kept: list[Ball] = []
        for ball in balls:
            if reached_left_paddle_line(ball, LEFT_PADDLE_X, config.PADDLE_WIDTH, config.BALL_RADIUS):
                paddle, direction = self.left, 1
            elif reached_right_paddle_line(ball, RIGHT_PADDLE_X, config.BALL_RADIUS):
                paddle, direction = self.right, -1
            else:
                kept.append(ball)
                continue
            bounced, caught = resolve_ball_at_paddle(
                ball, paddle, bounce_direction=direction, grace=config.PADDLE_CATCH_GRACE
            )
            self.flashes.append((ball.x, ball.y, self.t))
            if caught:
                kept.append(bounced)
        self.balls = kept


# --- The card's layout (internal px, 480x270). Press Start 2P at its native
# 8 px and at 16 px, whole multiples, so the x4 upscale stays crisp.
HEADING_Y = 14
GOAL_TOP = 32
LINE_PITCH = 12
CAPTION_Y = FIELD_TOP + FIELD_HEIGHT + 10
CONTROLS_Y = CAPTION_Y + 24
PROMPT_Y = config.INTERNAL_HEIGHT - 14


class TutorialCard:
    """Fonts and text pre-rendered once; `draw` paints one frame."""

    def __init__(self) -> None:
        heading_font = fonts.load_font(16)
        self.font = fonts.load_font(8)
        gate_font = fonts.load_font(10)  # the in-game gate label size
        self.heading = heading_font.render("HOW TO PLAY", False, config.COLOR_TEXT)
        self.goal = [self.font.render(line, False, config.COLOR_TEXT) for line in GOAL_LINES]
        self.captions = {k: self.font.render(v, False, config.COLOR_TEXT) for k, v in CAPTIONS.items()}
        self.warning_caption = self.font.render(WARNING_CAPTION, False, config.COLOR_HINT)
        self.stick_text = self.font.render("STICK: MOVE YOUR PADDLE", False, config.COLOR_TEXT)
        self.start_text = self.font.render("START: PAUSE", False, config.COLOR_TEXT)
        self._texts: dict[tuple[str, tuple[int, int, int]], pygame.Surface] = {}
        self.gate_labels = sprites.make_gate_label_surfaces(gate_font)
        self.warning_labels = sprites.make_gate_warning_labels(gate_font)
        self.field_rect = pygame.Rect(FIELD_LEFT, FIELD_TOP, FIELD_WIDTH, FIELD_HEIGHT)

    def _text(self, text: str, color: tuple[int, int, int]) -> pygame.Surface:
        """Rendered once per text: the hints change only when a player
        switches between keyboard and pad."""
        if (text, color) not in self._texts:
            self._texts[text, color] = self.font.render(text, False, color)
        return self._texts[text, color]

    def draw(
        self, surface: pygame.Surface, demo: DemoScene, t: float, show_prompt: bool,
        devices: LastDevice | None = None,
    ) -> None:
        """`devices`: what each player is using, for the control hints
        (None: pads, as on the cabinet)."""
        surface.fill(config.COLOR_BACKGROUND)
        cx = config.INTERNAL_WIDTH // 2

        surface.blit(self.heading, self.heading.get_rect(center=(cx, HEADING_Y)))
        for i, line in enumerate(self.goal):
            surface.blit(line, line.get_rect(midtop=(cx, GOAL_TOP + i * LINE_PITCH)))

        self._draw_demo(surface, demo)
        caption = self.captions[demo.kind] if demo.gate_is_live() or not demo.gates else self.warning_caption
        surface.blit(caption, caption.get_rect(center=(cx, CAPTION_Y)))

        on_pads = devices is None or devices.everyone_on(PAD)
        if on_pads:
            self._draw_controls(surface)
        else:
            self._draw_key_controls(surface, devices)

        if show_prompt:
            on_keys = devices is not None and devices.everyone_on(KEYBOARD)
            prompt = "PRESS ANY KEY TO START" if on_keys else "PRESS ANY BUTTON TO START"
            text = self._text(prompt, config.COLOR_FPS)
            surface.blit(text, text.get_rect(center=(cx, PROMPT_Y)))

    def _draw_demo(self, surface: pygame.Surface, demo: DemoScene) -> None:
        # Draw in simulation coordinates on a strip the field's height: x is
        # already screen x, y only needs the strip's offset.
        strip = surface.subsurface((0, FIELD_TOP, config.INTERNAL_WIDTH, FIELD_HEIGHT))
        strip.set_clip(pygame.Rect(FIELD_LEFT, 0, FIELD_WIDTH, FIELD_HEIGHT))
        pygame.draw.line(strip, config.COLOR_MIDLINE, (config.INTERNAL_WIDTH // 2, 0),
                         (config.INTERNAL_WIDTH // 2, FIELD_HEIGHT), 1)
        sprites.draw_paddle(strip, LEFT_PADDLE_X, demo.left)
        sprites.draw_paddle(strip, RIGHT_PADDLE_X, demo.right)
        for gate in demo.gates:
            if is_live(gate, demo.t):
                sprites.draw_gate(strip, self.gate_labels, gate)
            else:
                sprites.draw_gate_warning(strip, self.warning_labels, gate, demo.t)
        for ball in demo.balls:
            sprites.draw_ball(strip, ball)
        for flash in demo.flashes:
            sprites.draw_flash(strip, flash, demo.t)
        pygame.draw.rect(surface, config.COLOR_MIDLINE, self.field_rect.inflate(2, 2), 1)

    def _draw_key_controls(self, surface: pygame.Surface, devices: LastDevice) -> None:
        """The same two controls as text, when anyone is on the keyboard:
        each player's own keys (or STICK for a player on a pad)."""
        y = CONTROLS_Y + 2
        moves = dict.fromkeys(
            "STICK" if devices[p] == PAD else f"{devices.label('up', p)}/{devices.label('down', p)}"
            for p in PLAYERS
        )
        move = self._text(f"{', '.join(moves)}: MOVE", config.COLOR_TEXT)
        surface.blit(move, move.get_rect(midleft=(FIELD_LEFT, y)))
        pause = self._text(f"{devices.shared_label('start')}: PAUSE", config.COLOR_TEXT)
        surface.blit(pause, pause.get_rect(midright=(FIELD_LEFT + FIELD_WIDTH, y)))

    def _draw_controls(self, surface: pygame.Surface) -> None:
        """The stick and START, the only controls a match uses (both pads
        alike): a small arcade stick with its up/down arrows, and the round
        START button, lit."""
        y = CONTROLS_Y
        # Stick: base, shaft, ball top, and the two directions it moves.
        sx = 70
        pygame.draw.rect(surface, config.COLOR_HINT, (sx - 8, y + 6, 16, 4), border_radius=1)
        pygame.draw.line(surface, config.COLOR_TEXT, (sx, y + 6), (sx, y - 2), 2)
        pygame.draw.circle(surface, config.COLOR_TEXT, (sx, y - 4), 4)
        for direction in (-1, 1):
            tip = y + 2 + direction * 11
            base = tip - direction * 4
            pygame.draw.polygon(surface, config.COLOR_TEXT,
                                [(sx + 13, tip), (sx + 9, base), (sx + 17, base)])
        surface.blit(self.stick_text, self.stick_text.get_rect(midleft=(sx + 26, y + 2)))

        # START: a lit round button.
        bx = 300
        pygame.draw.circle(surface, config.COLOR_FPS, (bx, y + 2), 7)
        pygame.draw.circle(surface, config.COLOR_TEXT, (bx, y + 2), 7, 1)
        surface.blit(self.start_text, self.start_text.get_rect(midleft=(bx + 14, y + 2)))
