"""Entry point: CLI args, window setup, screen flow, game loop.

This module wires pygame I/O to the pure logic in pong.py/gates.py/screens.py/
sound.py/input.py/display.py. It is not unit tested (no headless assertions on
rendered output make sense); verify by running it and by the --input-test
smoke path.
"""

from __future__ import annotations

import argparse
import random
import sys

import pygame

from quantum_pong import config, fonts, gates as gates_mod, screens, sound
from quantum_pong.display import make_display, present
from quantum_pong.gates import Gate
from quantum_pong.input import (
    keyboard_quit_held,
    read_player_raw_input,
    resolve_paddle_direction,
    should_quit,
)
from quantum_pong.pong import (
    Ball,
    Paddle,
    move_paddle,
    reached_left_paddle_line,
    reached_right_paddle_line,
    resolve_ball_at_paddle,
    serve_ball,
    step_ball,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quantum Pong")
    parser.add_argument(
        "--input-test",
        action="store_true",
        help="Show live joystick/keyboard state instead of running the game",
    )
    parser.add_argument(
        "--fullscreen", action="store_true", help="Run fullscreen at desktop resolution"
    )
    parser.add_argument("--fps", action="store_true", help="Force the FPS overlay on")
    parser.add_argument(
        "--window-size",
        default="960x540",
        help="Windowed size as WxH, e.g. 960x540 (ignored with --fullscreen)",
    )
    return parser.parse_args(argv)


def _new_paddles() -> tuple[Paddle, Paddle]:
    y = config.INTERNAL_HEIGHT / 2 - config.PADDLE_HEIGHT / 2
    return Paddle(y=y, height=config.PADDLE_HEIGHT), Paddle(y=y, height=config.PADDLE_HEIGHT)


def _draw_ball(surface: pygame.Surface, ball: Ball) -> None:
    pos = (round(ball.x), round(ball.y))
    pygame.draw.circle(surface, config.COLOR_BALL, pos, config.BALL_RADIUS)
    pygame.draw.circle(surface, config.COLOR_BACKGROUND, pos, config.BALL_RADIUS, 1)


def _make_gate_label_surfaces(font: pygame.font.Font) -> dict[str, pygame.Surface]:
    """Pre-render each gate letter once -- there are only 4 possible labels,
    no need to re-rasterize text every frame for every gate on screen."""
    return {kind: font.render(kind, False, config.COLOR_BACKGROUND) for kind in config.GATE_COLORS}


def _draw_gate(
    surface: pygame.Surface,
    label_surfaces: dict[str, pygame.Surface],
    gate: Gate,
    game_time: float,
) -> None:
    age = game_time - gate.spawned_at
    remaining = config.GATE_LIFETIME - age
    if remaining < config.GATE_BLINK_WARNING and int(age * config.GATE_BLINK_RATE) % 2 == 0:
        return  # about to expire -- blink as a warning

    color = config.GATE_COLORS[gate.kind]
    size = config.GATE_RADIUS * 2
    rect = pygame.Rect(0, 0, size, size)
    rect.center = (round(gate.x), round(gate.y))

    pygame.draw.rect(surface, color, rect, border_radius=6)
    pygame.draw.rect(surface, config.COLOR_TEXT, rect, width=2, border_radius=6)

    label = label_surfaces[gate.kind]
    surface.blit(label, label.get_rect(center=rect.center))


def _draw_flash(surface: pygame.Surface, flash: tuple[float, float, float], game_time: float) -> None:
    """Draw a brief expanding ring at a paddle catch/score point. Caller is
    responsible for dropping flashes older than FLASH_DURATION."""
    x, y, started_at = flash
    age = game_time - started_at
    t = min(1.0, age / config.FLASH_DURATION)
    radius = config.BALL_RADIUS + round(t * config.FLASH_MAX_GROWTH)
    pygame.draw.circle(surface, config.COLOR_FLASH, (round(x), round(y)), radius, 2)


def _poll_players(keys: pygame.key.ScancodeWrapper) -> tuple:
    return read_player_raw_input("p1", keys), read_player_raw_input("p2", keys)


def _wants_quit(p1_raw, p2_raw, keys: pygame.key.ScancodeWrapper) -> bool:
    return should_quit(
        p1_start=p1_raw.start_held,
        p1_select=p1_raw.select_held,
        p2_start=p2_raw.start_held,
        p2_select=p2_raw.select_held,
        keyboard_quit=keyboard_quit_held(keys),
    )


def _wants_start(p1_raw, p2_raw, keys: pygame.key.ScancodeWrapper) -> bool:
    return (
        p1_raw.start_held
        or p2_raw.start_held
        or keys[pygame.K_RETURN]
        or keys[pygame.K_SPACE]
    )


def run_title_screen(surface: pygame.Surface, window: pygame.Surface | None) -> str:
    """Attract/title screen. Returns 'start' or 'quit'."""
    internal = surface
    clock = pygame.time.Clock()
    title_font = fonts.load_font(26)
    legend_font = fonts.load_font(9)
    prompt_font = fonts.load_font(12)
    t = 0.0

    while True:
        dt = clock.tick(config.FPS) / 1000.0
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

        keys = pygame.key.get_pressed()
        p1_raw, p2_raw = _poll_players(keys)

        if _wants_quit(p1_raw, p2_raw, keys):
            return "quit"
        if _wants_start(p1_raw, p2_raw, keys):
            return "start"

        screens.draw_title_screen(
            internal, title_font, legend_font, prompt_font,
            screens.blink_visible(t, config.TITLE_BLINK_PERIOD),
        )
        present(internal, window)
        pygame.display.flip()


def run_winner_screen(
    surface: pygame.Surface, window: pygame.Surface | None, winner: str, final_score: dict[str, int]
) -> str:
    """Returns 'continue' (back to title) or 'quit'."""
    internal = surface
    clock = pygame.time.Clock()
    big_font = fonts.load_font(20)
    small_font = fonts.load_font(14)
    label = "PLAYER 1" if winner == "p1" else "PLAYER 2"
    t = 0.0

    while True:
        dt = clock.tick(config.FPS) / 1000.0
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

        keys = pygame.key.get_pressed()
        p1_raw, p2_raw = _poll_players(keys)

        if _wants_quit(p1_raw, p2_raw, keys):
            return "quit"
        if t >= config.WINNER_SCREEN_DURATION or _wants_start(p1_raw, p2_raw, keys):
            return "continue"

        screens.draw_winner_screen(internal, big_font, small_font, label, final_score)
        present(internal, window)
        pygame.display.flip()


def run_game(
    surface: pygame.Surface, window: pygame.Surface | None, sounds: sound.Sounds, show_fps: bool
) -> tuple[str, dict[str, int]]:
    """Play one match. Returns (result, final_score); result is 'p1', 'p2',
    'quit', or 'idle' (no input for IDLE_TIMEOUT_SECONDS -- back to the title
    screen, since the cabinet runs unattended at events)."""
    internal = surface
    clock = pygame.time.Clock()
    font = fonts.load_font(10)
    score_font = fonts.load_font(16)
    gate_font = fonts.load_font(10)
    gate_label_surfaces = _make_gate_label_surfaces(gate_font)
    rng = random.Random()

    cached_score: dict[str, int] | None = None
    cached_score_surf: pygame.Surface | None = None

    p1_paddle, p2_paddle = _new_paddles()
    balls: list[Ball] = [serve_ball(direction=1)]
    active_gates: list[Gate] = []
    last_gate_spawn_at = 0.0
    game_time = 0.0
    idle_seconds = 0.0
    flashes: list[tuple[float, float, float]] = []  # (x, y, started_at); several can overlap

    score = {"p1": 0, "p2": 0}

    p1_x = float(config.PADDLE_MARGIN)
    p2_x = float(config.INTERNAL_WIDTH - config.PADDLE_MARGIN - config.PADDLE_WIDTH)
    deadzone = config.INPUT_CONFIG["axis_deadzone"]

    while True:
        dt = clock.tick(config.FPS) / 1000.0
        game_time += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit", score
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
                show_fps = not show_fps

        keys = pygame.key.get_pressed()
        p1_raw, p2_raw = _poll_players(keys)

        if _wants_quit(p1_raw, p2_raw, keys):
            return "quit", score

        p1_dir = resolve_paddle_direction(
            up_held=p1_raw.up_held, down_held=p1_raw.down_held,
            axis_value=p1_raw.axis_value, deadzone=deadzone,
        )
        p2_dir = resolve_paddle_direction(
            up_held=p2_raw.up_held, down_held=p2_raw.down_held,
            axis_value=p2_raw.axis_value, deadzone=deadzone,
        )

        idle_seconds = 0.0 if (p1_dir or p2_dir) else idle_seconds + dt
        if idle_seconds >= config.IDLE_TIMEOUT_SECONDS:
            return "idle", score

        p1_paddle = move_paddle(p1_paddle, p1_dir, dt, config.INTERNAL_HEIGHT)
        p2_paddle = move_paddle(p2_paddle, p2_dir, dt, config.INTERNAL_HEIGHT)

        balls = [step_ball(b, dt, config.INTERNAL_HEIGHT, config.BALL_RADIUS) for b in balls]

        active_gates = gates_mod.expire_gates(active_gates, game_time)
        active_gates, last_gate_spawn_at = gates_mod.maybe_spawn_gate(
            active_gates, game_time, last_gate_spawn_at, rng
        )
        gate_count_before = len(active_gates)
        balls, active_gates = gates_mod.check_gate_collisions(balls, active_gates, config.BALL_RADIUS)
        if len(active_gates) < gate_count_before:
            sounds.gate.play()

        remaining_balls: list[Ball] = []
        scorers: list[str] = []
        flashes = [f for f in flashes if game_time - f[2] < config.FLASH_DURATION]
        for ball in balls:
            if reached_left_paddle_line(ball, p1_x, config.PADDLE_WIDTH, config.BALL_RADIUS):
                bounced, caught = resolve_ball_at_paddle(
                    ball, p1_paddle, bounce_direction=1, grace=config.PADDLE_CATCH_GRACE
                )
                flashes.append((ball.x, ball.y, game_time))
                if caught:
                    sounds.bounce.play()
                    remaining_balls.append(bounced)
                else:
                    sounds.score.play()
                    scorers.append("p2")
            elif reached_right_paddle_line(ball, p2_x, config.BALL_RADIUS):
                bounced, caught = resolve_ball_at_paddle(
                    ball, p2_paddle, bounce_direction=-1, grace=config.PADDLE_CATCH_GRACE
                )
                flashes.append((ball.x, ball.y, game_time))
                if caught:
                    sounds.bounce.play()
                    remaining_balls.append(bounced)
                else:
                    sounds.score.play()
                    scorers.append("p1")
            else:
                remaining_balls.append(ball)
        balls = remaining_balls

        for scorer in scorers:
            score[scorer] += 1
        if not balls:
            # Field's empty (every ball just scored/was caught away) -- fresh serve.
            # Toward whichever side conceded; if several scored this frame, the
            # last one wins the serve direction.
            balls = [serve_ball(direction=1 if (scorers and scorers[-1] == "p1") else -1)]

        internal.fill(config.COLOR_BACKGROUND)
        pygame.draw.line(
            internal, config.COLOR_MIDLINE,
            (config.INTERNAL_WIDTH // 2, 0), (config.INTERNAL_WIDTH // 2, config.INTERNAL_HEIGHT), 1,
        )
        pygame.draw.rect(
            internal, config.COLOR_PADDLE,
            (p1_x, p1_paddle.y, config.PADDLE_WIDTH, p1_paddle.height),
            border_radius=2,
        )
        pygame.draw.rect(
            internal, config.COLOR_PADDLE,
            (p2_x, p2_paddle.y, config.PADDLE_WIDTH, p2_paddle.height),
            border_radius=2,
        )

        for gate in active_gates:
            _draw_gate(internal, gate_label_surfaces, gate, game_time)

        for ball in balls:
            _draw_ball(internal, ball)

        for flash in flashes:
            _draw_flash(internal, flash, game_time)

        if score != cached_score:
            cached_score = dict(score)
            cached_score_surf = score_font.render(
                f"{score['p1']}  -  {score['p2']}", False, config.COLOR_TEXT
            )
        internal.blit(
            cached_score_surf,
            (config.INTERNAL_WIDTH // 2 - cached_score_surf.get_width() // 2, 6),
        )

        if show_fps:
            fps_surf = font.render(f"{clock.get_fps():.0f} fps", False, config.COLOR_FPS)
            internal.blit(fps_surf, (4, 4))

        present(internal, window)
        pygame.display.flip()

        if score["p1"] >= config.WINNING_SCORE:
            return "p1", score
        if score["p2"] >= config.WINNING_SCORE:
            return "p2", score


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    pygame.init()
    pygame.joystick.init()
    surface, window = make_display(args.fullscreen, args.window_size)
    pygame.display.set_caption("Quantum Pong")

    if args.input_test:
        from quantum_pong.input_test import run_input_test

        run_input_test(surface, window)
    else:
        sounds = sound.load_sounds()
        show_fps = args.fps or config.SHOW_FPS_DEFAULT

        while True:
            action = run_title_screen(surface, window)
            if action == "quit":
                break

            result, final_score = run_game(surface, window, sounds, show_fps)
            if result == "quit":
                break
            if result in ("p1", "p2"):
                sounds.win.play()
                if run_winner_screen(surface, window, result, final_score) == "quit":
                    break
            # result == "idle" falls straight back to the title screen

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
