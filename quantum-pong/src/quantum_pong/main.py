"""Entry point: CLI args, window setup, screen flow, game loop.

This module wires pygame I/O to the pure logic in pong.py/gates.py/screens.py/
sound.py/input.py/display.py/pause.py/title.py/tutorial.py. Rendering is not
unit tested (no headless assertions on rendered output make sense); verify by
running it and by the --input-test smoke path. The screen flow in `main()`
(title -> HOW TO PLAY -> match -> winner -> title) is tested with the
screens stubbed out (tests/test_flow.py).
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys

import pygame
from arqade_common import runtime, web
from arqade_common.input import PAD_LAYOUTS

from quantum_pong import config, fonts, screens, sound, sprites, title
from quantum_pong import gates as gates_mod
from quantum_pong import tutorial as tutorial_mod
from quantum_pong.display import make_display, present
from quantum_pong.gates import Gate, is_live
from quantum_pong.input import (
    get_events,
    keyboard_enabled,
    last_device,
    pressed_edge,
    read_keys,
    read_player_raw_input,
    resolve_paddle_direction,
    set_keyboard_enabled,
    set_pad_layout,
    should_quit,
    start_devices,
)
from quantum_pong.pause import PLAY, QUIT_TO_TITLE, PauseInput, PauseMenu, nav_edge
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

# Same as the folder name in the web build and the "id" in game.json.
GAME_ID = "quantum-pong"


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
    parser.add_argument(
        "--no-keyboard",
        action="store_true",
        help="Ignore the keyboard, joysticks only (used on the Batocera cabinet)",
    )
    parser.add_argument(
        "--pad-layout",
        choices=sorted(PAD_LAYOUTS),
        default=None,
        help="How to read pad buttons: encoder (the cabinet's sticks, default), "
        "xbox (an Xbox-style pad on a PC), standard (browser gamepads)",
    )
    return parser.parse_args(argv)


def _new_paddles() -> tuple[Paddle, Paddle]:
    y = config.INTERNAL_HEIGHT / 2 - config.PADDLE_HEIGHT / 2
    return Paddle(y=y, height=config.PADDLE_HEIGHT), Paddle(y=y, height=config.PADDLE_HEIGHT)


def _poll_players(keys: pygame.key.ScancodeWrapper) -> tuple:
    return read_player_raw_input("p1", keys), read_player_raw_input("p2", keys)


def _wants_quit(p1_raw, p2_raw, keys: pygame.key.ScancodeWrapper) -> bool:
    return should_quit(
        p1_start=p1_raw.start_held,
        p1_select=p1_raw.select_held,
        p2_start=p2_raw.start_held,
        p2_select=p2_raw.select_held,
    )


def _wants_start(p1_raw, p2_raw) -> bool:
    return p1_raw.start_held or p2_raw.start_held or p1_raw.confirm_held or p2_raw.confirm_held


def _directions(p1_raw, p2_raw) -> tuple[int, int]:
    """Each player's stick (or dev keys) as -1 up / 0 / 1 down."""
    deadzone = config.INPUT_CONFIG["axis_deadzone"]
    return tuple(
        resolve_paddle_direction(
            up_held=raw.up_held, down_held=raw.down_held,
            axis_value=raw.axis_value, deadzone=deadzone,
        )
        for raw in (p1_raw, p2_raw)
    )


def _title_buttons_held(p1_raw, p2_raw) -> dict[str, tuple]:
    """Like _pause_buttons_held, for the title menu: Start starts, A picks
    the selected item."""
    return {
        "start": (p1_raw.start_held, p2_raw.start_held),
        "back": (p1_raw.back_held, p2_raw.back_held),
        "confirm": (p1_raw.confirm_held, p2_raw.confirm_held),
    }


def _pause_buttons_held(p1_raw, p2_raw) -> dict[str, tuple]:
    """Held state of each pause-menu button, per player (their pad and their
    half of the keyboard), so each player's presses are edge-detected on
    their own."""
    return {
        "pause": (p1_raw.start_held, p2_raw.start_held),
        "back": (p1_raw.back_held, p2_raw.back_held),
        "confirm": (p1_raw.confirm_held, p2_raw.confirm_held),
    }


def _pause_hint() -> str:
    """The pause menu's hint for whoever pressed something last (one player
    works the menu; both players' keys wouldn't fit)."""
    devices = last_device()
    player = devices.latest
    pick, back, start = (devices.label(a, player) for a in ("a", "b", "start"))
    return f"{pick}: PICK   {start} / {back}: RESUME"


def _pressed(previous: dict[str, tuple], held: dict[str, tuple], name: str) -> bool:
    return any(pressed_edge(p, c) for p, c in zip(previous[name], held[name]))


async def run_title_screen(
    surface: pygame.Surface, window: pygame.Surface | None, sounds: sound.Sounds
) -> str:
    """Attract/title screen with its PLAY / QUIT menu. Returns 'start' or
    'quit'. Start always starts; A picks the selected row (see title.py)."""
    internal = surface
    clock = pygame.time.Clock()
    title_font = fonts.load_font(26)
    legend_font = fonts.load_font(9)
    item_font = fonts.load_font(10)
    prompt_font = fonts.load_font(8)
    menu = title.TitleMenu()
    t = 0.0
    # Seed the edge detection with what's held right now: the A that picked
    # QUIT TO TITLE (or the Start that left the winner screen) is usually
    # still held on the first frame here, and must not start a match (or, on
    # QUIT, leave the game) by itself.
    keys = read_keys()
    p1_raw, p2_raw = _poll_players(keys)
    prev_held = _title_buttons_held(p1_raw, p2_raw)
    prev_dirs = _directions(p1_raw, p2_raw)

    while True:
        dt = runtime.frame_seconds(clock.tick(config.FPS) / 1000.0)
        t += dt

        for event in get_events():
            if event.type == pygame.QUIT:
                return "quit"

        keys = read_keys()
        p1_raw, p2_raw = _poll_players(keys)

        if _wants_quit(p1_raw, p2_raw, keys):
            return "quit"

        held = _title_buttons_held(p1_raw, p2_raw)
        dirs = _directions(p1_raw, p2_raw)
        title_input = title.TitleInput(
            start=_pressed(prev_held, held, "start"),
            confirm=_pressed(prev_held, held, "confirm"),
            back=_pressed(prev_held, held, "back"),
            nav=nav_edge(prev_dirs[0], dirs[0]) or nav_edge(prev_dirs[1], dirs[1]),
        )
        prev_held, prev_dirs = held, dirs

        index_before = menu.index
        step = menu.update(title_input)
        if step == title.QUIT:
            return "quit"
        if step == title.START:
            sounds.confirm.play()
            return "start"
        if menu.index != index_before:
            sounds.move.play()

        screens.draw_title_screen(
            internal, title_font, legend_font, item_font, prompt_font, menu.index,
            screens.blink_visible(t, config.TITLE_BLINK_PERIOD),
            start_label=last_device().shared_label("start"),
        )
        present(internal, window)
        pygame.display.flip()
        await asyncio.sleep(0)  # hand the frame to the browser (pygbag); no-op elsewhere


async def run_tutorial_screen(
    surface: pygame.Surface, window: pygame.Surface | None, sounds: sound.Sounds
) -> str:
    """The HOW TO PLAY card (tutorial.py). Returns 'play' once any button is
    pressed (after a short grace period), 'quit' on Start + Select, or 'idle'
    after IDLE_TIMEOUT_SECONDS with nobody pressing anything."""
    internal = surface
    clock = pygame.time.Clock()
    card = tutorial_mod.TutorialCard()
    demo = tutorial_mod.DemoScene()
    tutorial = tutorial_mod.DismissGate()  # attract bots look for this name
    # Presses still queued from the title must not count.
    pygame.event.clear((pygame.JOYBUTTONDOWN, pygame.KEYDOWN))

    while True:
        dt = runtime.frame_seconds(clock.tick(config.FPS) / 1000.0)

        pressed = False
        for event in get_events():
            if event.type == pygame.QUIT:
                return "quit"
            # Any button on either pad; any key only for dev runs.
            if event.type == pygame.JOYBUTTONDOWN or (
                event.type == pygame.KEYDOWN and keyboard_enabled()
            ):
                pressed = True

        keys = read_keys()
        p1_raw, p2_raw = _poll_players(keys)
        if _wants_quit(p1_raw, p2_raw, keys):
            return "quit"
        if tutorial.update(dt, pressed):
            sounds.confirm.play()
            return "play"
        if tutorial.age >= config.IDLE_TIMEOUT_SECONDS:
            return "idle"

        demo.step(dt)
        card.draw(
            internal, demo, tutorial.age,
            screens.blink_visible(tutorial.age, config.TITLE_BLINK_PERIOD), last_device(),
        )
        present(internal, window)
        pygame.display.flip()
        await asyncio.sleep(0)  # hand the frame to the browser (pygbag); no-op elsewhere


async def run_winner_screen(
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
        dt = runtime.frame_seconds(clock.tick(config.FPS) / 1000.0)
        t += dt

        for event in get_events():
            if event.type == pygame.QUIT:
                return "quit"

        keys = read_keys()
        p1_raw, p2_raw = _poll_players(keys)

        if _wants_quit(p1_raw, p2_raw, keys):
            return "quit"
        if t >= config.WINNER_SCREEN_DURATION or _wants_start(p1_raw, p2_raw):
            return "continue"

        screens.draw_winner_screen(internal, big_font, small_font, label, final_score)
        present(internal, window)
        pygame.display.flip()
        await asyncio.sleep(0)  # hand the frame to the browser (pygbag); no-op elsewhere


async def run_game(
    surface: pygame.Surface, window: pygame.Surface | None, sounds: sound.Sounds, show_fps: bool
) -> tuple[str, dict[str, int]]:
    """Play one match. Returns (result, final_score); result is 'p1', 'p2',
    'quit', 'title' (QUIT TO TITLE from the pause menu), or 'idle' (no input
    for IDLE_TIMEOUT_SECONDS -- back to the title screen, since the cabinet
    runs unattended at events)."""
    internal = surface
    clock = pygame.time.Clock()
    font = fonts.load_font(10)
    score_font = fonts.load_font(16)
    gate_font = fonts.load_font(10)
    gate_label_surfaces = sprites.make_gate_label_surfaces(gate_font)
    gate_warning_labels = sprites.make_gate_warning_labels(gate_font)
    pause_hint_font = fonts.load_font(8)
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

    # Start pauses. Seed the edge detection with what's held right now, so the
    # Start (or A) that began the match on the title screen can't also pause
    # it on the first frame.
    pause_menu = PauseMenu()
    keys = read_keys()
    prev_held = _pause_buttons_held(*_poll_players(keys))
    prev_dirs = (0, 0)

    while True:
        dt = runtime.frame_seconds(clock.tick(config.FPS) / 1000.0)

        for event in get_events():
            if event.type == pygame.QUIT:
                return "quit", score
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
                show_fps = not show_fps

        keys = read_keys()
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

        held = _pause_buttons_held(p1_raw, p2_raw)
        pause_input = PauseInput(
            pause=_pressed(prev_held, held, "pause"),
            back=_pressed(prev_held, held, "back"),
            confirm=_pressed(prev_held, held, "confirm"),
            nav=nav_edge(prev_dirs[0], p1_dir) or nav_edge(prev_dirs[1], p2_dir),
        )
        prev_held, prev_dirs = held, (p1_dir, p2_dir)

        was_paused, index_before = pause_menu.paused, pause_menu.index
        step = pause_menu.update(pause_input)
        if step == QUIT_TO_TITLE:
            sounds.confirm.play()
            return "title", score
        if pause_menu.paused != was_paused:
            sounds.confirm.play()
        elif pause_menu.index != index_before:
            sounds.move.play()

        # The idle timeout keeps counting while paused, so a match left paused
        # still drops back to the title; using the menu counts as input.
        active = (p1_dir or p2_dir) if step == PLAY else pause_input.any
        idle_seconds = 0.0 if active else idle_seconds + dt
        if idle_seconds >= config.IDLE_TIMEOUT_SECONDS:
            return "idle", score

        # Paused: nothing below moves -- game_time drives gate spawns and the
        # flashes, so not advancing it freezes those too.
        if step == PLAY:
            game_time += dt

            p1_paddle = move_paddle(p1_paddle, p1_dir, dt, config.INTERNAL_HEIGHT)
            p2_paddle = move_paddle(p2_paddle, p2_dir, dt, config.INTERNAL_HEIGHT)

            balls = [step_ball(b, dt, config.INTERNAL_HEIGHT, config.BALL_RADIUS) for b in balls]

            gate_count_before = len(active_gates)
            active_gates, last_gate_spawn_at = gates_mod.maybe_spawn_gate(
                active_gates, game_time, last_gate_spawn_at, rng
            )
            if len(active_gates) > gate_count_before:
                sounds.announce.play()  # a dashed gate shows where one will appear
            gate_count_before = len(active_gates)
            balls, active_gates = gates_mod.check_gate_collisions(
                balls, active_gates, config.BALL_RADIUS, game_time
            )
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
        sprites.draw_paddle(internal, p1_x, p1_paddle)
        sprites.draw_paddle(internal, p2_x, p2_paddle)

        for gate in active_gates:
            if is_live(gate, game_time):
                sprites.draw_gate(internal, gate_label_surfaces, gate)
            else:
                sprites.draw_gate_warning(internal, gate_warning_labels, gate, game_time)

        for ball in balls:
            sprites.draw_ball(internal, ball)

        for flash in flashes:
            sprites.draw_flash(internal, flash, game_time)

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

        if pause_menu.paused:
            screens.draw_pause_menu(
                internal, score_font, font, pause_hint_font, pause_menu.index, _pause_hint(),
            )

        present(internal, window)
        pygame.display.flip()
        await asyncio.sleep(0)  # hand the frame to the browser (pygbag); no-op elsewhere

        if score["p1"] >= config.WINNING_SCORE:
            return "p1", score
        if score["p2"] >= config.WINNING_SCORE:
            return "p2", score


async def _leave(surface: pygame.Surface, window: pygame.Surface | None) -> bool:
    """A player asked to quit: True ends the program. In the browser there is
    nothing to hand back to, so instead the game tells the page (which may
    take the player back to its game list) and returns to its title -- once
    the quit buttons are let go, or the title would quit again at once."""
    if not runtime.is_browser():
        return True
    web.post_event(web.QUIT, GAME_ID)
    while True:
        get_events()
        keys = read_keys()
        if not _wants_quit(*_poll_players(keys), keys):
            return False
        present(surface, window)
        pygame.display.flip()
        await asyncio.sleep(0)


async def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    set_keyboard_enabled(not args.no_keyboard)
    if args.pad_layout:
        set_pad_layout(PAD_LAYOUTS[args.pad_layout])

    pygame.init()
    pygame.joystick.init()
    start_devices()
    surface, window = make_display(args.fullscreen, args.window_size)
    pygame.display.set_caption("Quantum Pong")

    if args.input_test:
        from quantum_pong.input_test import run_input_test

        run_input_test(surface, window)
    else:
        sounds = sound.load_sounds()
        show_fps = args.fps or config.SHOW_FPS_DEFAULT

        while True:
            action = await run_title_screen(surface, window, sounds)
            if action == "quit":
                if await _leave(surface, window):
                    break
                continue
            # HOW TO PLAY before every match from the title (there's no
            # rematch that skips the title, so that's every match).
            action = await run_tutorial_screen(surface, window, sounds)
            if action == "quit":
                if await _leave(surface, window):
                    break
                continue
            if action == "idle":
                continue

            web.post_event(web.GAME_START, GAME_ID)
            result, final_score = await run_game(surface, window, sounds, show_fps)
            web.post_event(web.GAME_END, GAME_ID)
            if result == "quit":
                if await _leave(surface, window):
                    break
                continue
            if result in ("p1", "p2"):
                sounds.win.play()
                if await run_winner_screen(surface, window, result, final_score) == "quit":
                    if await _leave(surface, window):
                        break
            # result == "idle" or "title" falls straight back to the title screen

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
