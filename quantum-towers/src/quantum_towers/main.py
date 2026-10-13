"""Entry point: CLI args, window setup, screen flow, game loop.

Two players climbing side by side, each with their own tower, target chain,
and charges; reaching CHARGES_TO_ATTACK fires an automatic knockback attack
on the opponent. Or one player against the clock (run_solo): a fresh
equal-difficulty tower, then initials for a top-10 time and the
fastest-clears table. Start pauses (pause.py holds the menu's logic). The
rendering isn't unit tested; verify it by running the game and by the
--input-test smoke path. tests/test_pause.py and tests/test_solo_flow.py do
drive the loops with scripted input, to check pausing, the timer and the
screen flow.
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import fields, replace

import pygame
import pygame.gfxdraw

from quantum_towers import config, fonts, screens, solo, sound, tutorial, visuals
from quantum_towers.display import make_display, present
from quantum_towers.input import (
    PlayerRawInput,
    keyboard_enabled,
    keyboard_quit_held,
    read_keys,
    pressed_edge,
    read_player_raw_input,
    set_keyboard_enabled,
    should_quit,
)
from quantum_towers.notation import render_state
from quantum_towers.pause import PAUSE_ITEMS, PauseButtons, PauseMenu
from quantum_towers.player import PlayerState, apply_action, confirm_climb, knockback, new_player
from quantum_towers.quantum import ACTIONS, states_equal
from quantum_towers.targets import generate_target_sequence
from quantum_towers.times import Times

# Per-half vertical layout (px). The tower fills whatever's left between the
# header and the info strip below it (state + charge bar, kept near the
# climber rather than up at the top); the button legend is shared and shown
# once across the full width, not per half.
TOWER_TOP = 18
INFO_HEIGHT = 32
LEGEND_HEIGHT = 40


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quantum Towers")
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
    return parser.parse_args(argv)


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
        or p1_raw.confirm_held
        or p2_raw.confirm_held
        or keys[pygame.K_RETURN]
        or keys[pygame.K_SPACE]
    )


def _pause_buttons(p1_raw, p2_raw, keys: pygame.key.ScancodeWrapper) -> PauseButtons:
    """The pause menu's buttons, from both pads and the dev keyboard."""
    system = config.INPUT_CONFIG["system"]
    return PauseButtons(
        start=p1_raw.start_held or p2_raw.start_held
        or bool(keys[getattr(pygame, system["keyboard_pause"])]),
        confirm=p1_raw.confirm_held or p2_raw.confirm_held
        or bool(keys[getattr(pygame, system["keyboard_menu_confirm"])]),
        back=p1_raw.back_held or p2_raw.back_held
        or bool(keys[getattr(pygame, system["keyboard_menu_back"])]),
        up=p1_raw.up_held or p2_raw.up_held,
        down=p1_raw.down_held or p2_raw.down_held,
    )


def _merged(p1_raw: PlayerRawInput, p2_raw: PlayerRawInput) -> PlayerRawInput:
    """Both pads as one: in single player either pad plays."""
    values = {}
    for field in fields(PlayerRawInput):
        a, b = getattr(p1_raw, field.name), getattr(p2_raw, field.name)
        values[field.name] = {k: a[k] or b[k] for k in a} if isinstance(a, dict) else a or b
    return PlayerRawInput(**values)


def _menu_held(raw: PlayerRawInput, keys: pygame.key.ScancodeWrapper) -> tuple[int, int, bool, bool]:
    """(dx, dy, A, B) held this frame, for the initials entry. dy = -1 is up."""
    system = config.INPUT_CONFIG["system"]
    return (
        int(raw.right_held) - int(raw.left_held),
        int(raw.down_held) - int(raw.up_held),
        raw.confirm_held or bool(keys[getattr(pygame, system["keyboard_menu_confirm"])]),
        raw.back_held or bool(keys[getattr(pygame, system["keyboard_menu_back"])]),
    )


def _update_pause(pause_menu: PauseMenu, buttons: PauseButtons, sounds: sound.Sounds) -> str:
    """pause_menu.update, with a sound for opening it, moving and picking."""
    was_paused, was_selected = pause_menu.paused, pause_menu.selected
    state = pause_menu.update(buttons)
    if pause_menu.paused != was_paused or state == "title":
        sounds.select.play()
    elif pause_menu.selected != was_selected:
        sounds.move.play()
    return state


def _camera_step(
    anim: tuple[float, float, float] | None, visual_floor: float, floor: int, game_time: float
) -> tuple[tuple[float, float, float] | None, float, float | None]:
    """Eases one tower's camera toward its real (logical) floor whenever that
    changes, rather than snapping, so the tower visibly scrolls and the
    climber's pose has something to sync a "pulling up" motion to. `anim` is
    (from_floor, to_floor, started_at) while a transition is in flight, else
    None. Returns (anim, visual_floor, climb_progress or None)."""
    actual_floor = float(floor)
    if anim is None or anim[1] != actual_floor:
        # Floor changed since the last frame (a climb or a knockback) --
        # (re)start the camera animation from wherever it visually is right
        # now toward the new floor, so an interruption (e.g. a knockback
        # landing mid-climb) blends smoothly rather than snapping.
        anim = (visual_floor, actual_floor, game_time)

    start_v, target_v, started_at = anim
    if start_v == target_v:
        return None, visual_floor, None
    progress = min(1.0, (game_time - started_at) / config.CLIMB_ANIM_DURATION)
    eased = 1 - (1 - progress) ** 2  # ease-out
    visual_floor = start_v + (target_v - start_v) * eased
    return (None if progress >= 1.0 else anim), visual_floor, progress


TITLE_ROWS = tuple(key for key, _label in screens.PLAYER_CHOICES)  # "1p", "2p", "quit"


def run_title_screen(
    surface: pygame.Surface,
    window: pygame.Surface | None,
    selected: str = "2p",
    sounds: sound.Sounds | None = None,
) -> str:
    """Attract/title screen. The stick moves between 1 PLAYER, 2 PLAYERS and
    QUIT (starting on `selected`) and A picks the row: A on QUIT leaves the
    game. Start always starts a match, never quits: with QUIT highlighted it
    starts the player count highlighted last. Returns '1p', '2p' or 'quit'."""
    internal = surface
    sounds = sounds or sound.silent()
    mode = selected if selected in ("1p", "2p") else "2p"
    clock = pygame.time.Clock()
    title_font = fonts.load_font(22)
    legend_font = fonts.load_font(9)
    prompt_font = fonts.load_font(12)
    grid_gate_font = fonts.load_font(8)
    choice_font = fonts.load_font(10)
    t = 0.0
    # A button still held from the screen before (A picking QUIT TO TITLE,
    # Start skipping the winner screen) must be let go first, or this screen
    # would start a new match on its very first frame. The stick likewise
    # counts as held until it is let go.
    armed = False
    prev_up = prev_down = True

    while True:
        dt = clock.tick(config.FPS) / 1000.0
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

        keys = read_keys()
        p1_raw, p2_raw = _poll_players(keys)

        if _wants_quit(p1_raw, p2_raw, keys):
            return "quit"
        up = p1_raw.up_held or p2_raw.up_held
        down = p1_raw.down_held or p2_raw.down_held
        row = TITLE_ROWS.index(selected)
        if pressed_edge(prev_up, up):
            row = max(0, row - 1)
        if pressed_edge(prev_down, down):
            row = min(len(TITLE_ROWS) - 1, row + 1)
        if TITLE_ROWS[row] != selected:
            selected = TITLE_ROWS[row]
            mode = selected if selected != "quit" else mode
            sounds.move.play()
        prev_up, prev_down = up, down
        wants_start = _wants_start(p1_raw, p2_raw, keys)
        if armed and wants_start:
            # A picks the highlighted row; Start (or Enter/Space) always plays.
            start = p1_raw.start_held or p2_raw.start_held or keys[pygame.K_SPACE]
            choice = mode if start else selected
            if choice != "quit":
                sounds.select.play()
            return choice
        armed = armed or not wants_start

        screens.draw_title_screen(
            internal, title_font, legend_font, prompt_font, grid_gate_font,
            screens.blink_visible(t, config.TITLE_BLINK_PERIOD),
            p1_pressed=p1_raw.button_held, p2_pressed=p2_raw.button_held,
            selected=selected, choice_font=choice_font,
        )
        present(internal, window)
        pygame.display.flip()


def run_winner_screen(
    surface: pygame.Surface,
    window: pygame.Surface | None,
    winner: str,
    floors: dict[str, int],
    sounds: sound.Sounds | None = None,
) -> str:
    """Returns 'continue' (back to title) or 'quit'."""
    internal = surface
    clock = pygame.time.Clock()
    big_font = fonts.load_font(18)
    small_font = fonts.load_font(12)
    label = "PLAYER 1" if winner == "p1" else "PLAYER 2"
    t = 0.0
    (sounds or sound.silent()).win.play()

    while True:
        dt = clock.tick(config.FPS) / 1000.0
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

        keys = read_keys()
        p1_raw, p2_raw = _poll_players(keys)

        if _wants_quit(p1_raw, p2_raw, keys):
            return "quit"
        if t >= config.WINNER_SCREEN_DURATION or _wants_start(p1_raw, p2_raw, keys):
            return "continue"

        screens.draw_winner_screen(internal, big_font, small_font, label, floors)
        present(internal, window)
        pygame.display.flip()


def run_tutorial(
    surface: pygame.Surface,
    window: pygame.Surface | None,
    mode: str,
    sounds: sound.Sounds | None = None,
) -> str:
    """HOW TO PLAY (tutorial.py), before a match picked on the title. Any
    button press on either pad closes it, once it has been up for
    tutorial.GRACE seconds; so does any key, unless --no-keyboard. The stick
    doesn't. Returns 'play', 'quit' (Start + Select, or the window closed) or
    'idle' (the idle timeout: back to the title)."""
    internal = surface
    clock = pygame.time.Clock()
    sounds = sounds or sound.silent()
    card = tutorial.Card(mode)
    dismissal = tutorial.Dismissal()
    t = 0.0
    idle_seconds = 0.0
    # Only presses from now on count: anything queued before the card opened
    # is the title's own A or Start.
    pygame.event.clear((pygame.JOYBUTTONDOWN, pygame.KEYDOWN))

    while True:
        dt = clock.tick(config.FPS) / 1000.0
        t += dt

        pressed = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.JOYBUTTONDOWN or (
                event.type == pygame.KEYDOWN and keyboard_enabled()
            ):
                pressed = True

        keys = read_keys()
        p1_raw, p2_raw = _poll_players(keys)
        if _wants_quit(p1_raw, p2_raw, keys):
            return "quit"

        idle_seconds = 0.0 if pressed else idle_seconds + dt
        if idle_seconds >= config.IDLE_TIMEOUT_SECONDS:
            return "idle"
        if dismissal.update(dt, pressed):
            sounds.select.play()
            return "play"

        tutorial.draw_tutorial(internal, card, t, screens.blink_visible(t, config.TITLE_BLINK_PERIOD))
        present(internal, window)
        pygame.display.flip()


def _draw_player_half(
    surface: pygame.Surface,
    half: pygame.Rect,
    label: str,
    player: PlayerState,
    visual_floor: float,
    climb_progress: float | None,
    attack_progress: float | None,
    stun_progress: float | None,
    color: tuple[int, int, int],
    header_font: pygame.font.Font,
    state_font: pygame.font.Font,
    block_fonts: list[pygame.font.Font],
    game_time: float,
    climber_side: str,
) -> tuple[int, int]:
    """Returns the climber's (x, y) screen position, for the attack-beam and
    perfect-floor effects."""
    visuals.blit_outlined_text(
        surface, header_font, f"{label}  FLOOR {player.floor}/{config.TOWER_HEIGHT}",
        config.COLOR_TEXT, (half.x + 8, half.y + 4),
    )

    tower_region = pygame.Rect(
        half.x + 16, half.y + TOWER_TOP, half.width - 32,
        half.height - TOWER_TOP - INFO_HEIGHT - LEGEND_HEIGHT,
    )
    climber_pos = visuals.draw_tower(
        surface, tower_region, player.floor, visual_floor, player.current_target, player.next_target,
        color, block_fonts, game_time, climber_side=climber_side, climb_progress=climb_progress,
        attack_progress=attack_progress, stun_progress=stun_progress,
    )

    # State and charges sit right below the tower -- near the climber's own
    # position, not up in the top HUD row -- since they're about *this
    # player, right now*, not a persistent scoreboard.
    info_y = tower_region.bottom + 4
    bar_rect = pygame.Rect(half.x + 8, info_y, half.width - 16, 8)
    visuals.draw_charge_bar(surface, bar_rect, player.charges, config.CHARGES_TO_ATTACK)

    you_prefix_rect = visuals.blit_outlined_text(
        surface, state_font, "YOU:", color, (half.x + 8, info_y + 12),
    )
    visuals.blit_outlined_text(
        surface, state_font, render_state(player.state), config.COLOR_TEXT,
        (you_prefix_rect.right + 4, info_y + 12),
    )

    return climber_pos


def _draw_attack_beam(
    surface: pygame.Surface,
    from_pos: tuple[int, int],
    to_pos: tuple[int, int],
    color: tuple[int, int, int],
    progress: float,
) -> None:
    """A brief traveling spark from the attacker's climber to the victim's,
    so the knockback reads as one player shooting the other."""
    pygame.draw.line(surface, color, from_pos, to_pos, 2)
    spark_x = round(from_pos[0] + (to_pos[0] - from_pos[0]) * progress)
    spark_y = round(from_pos[1] + (to_pos[1] - from_pos[1]) * progress)
    pygame.gfxdraw.filled_circle(surface, spark_x, spark_y, 5, color)
    pygame.gfxdraw.aacircle(surface, spark_x, spark_y, 5, color)


def _handle_attacks(
    players: dict[str, PlayerState], rng: random.Random
) -> tuple[dict[str, PlayerState], str | None]:
    """If either player has enough charges, fire their attack: knock the
    opponent down and reset the attacker's charges. At most one attack per
    call (mirrors "one event resolved per frame" used elsewhere in this
    codebase's sibling project) -- with two players this just means a
    simultaneous double-charge is resolved over two consecutive frames."""
    for attacker_key, victim_key in (("p1", "p2"), ("p2", "p1")):
        attacker = players[attacker_key]
        if attacker.charges >= config.CHARGES_TO_ATTACK:
            victim = knockback(players[victim_key], config.KNOCKBACK_FLOORS, rng)
            new_attacker = replace(attacker, charges=0)
            return {**players, attacker_key: new_attacker, victim_key: victim}, attacker_key
    return players, None


def run_game(
    surface: pygame.Surface, window: pygame.Surface | None, sounds: sound.Sounds, show_fps: bool
) -> tuple[str, dict[str, PlayerState]]:
    """Play one match. Returns (result, players); result is 'p1'/'p2'
    (reached the top), 'quit', 'idle', or 'title' (picked in the pause menu)."""
    internal = surface
    clock = pygame.time.Clock()
    font = fonts.load_font(10)
    header_font = fonts.load_font(11)
    state_font = fonts.load_font(9)
    # Biggest-first: most block labels fit at 11px, but a general state with
    # a magnitude and an angle (e.g. "1/√2|1>@315°") needs a smaller size to
    # avoid spilling out of the block.
    block_fonts = [fonts.load_font(11), fonts.load_font(9), fonts.load_font(7)]
    grid_gate_font = fonts.load_font(8)
    perfect_font = fonts.load_font(9)
    pause_title_font = fonts.load_font(16)
    pause_item_font = fonts.load_font(10)
    pause_hint_font = fonts.load_font(7)
    background = visuals.make_background(config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT)
    button_grid_data = screens.button_grid()

    rng = random.Random()
    # One shared chain of targets for the whole match -- both players climb
    # the exact same sequence of floors, so neither's puzzles are randomly
    # easier or harder than the other's. +2 so the final floor (TOWER_HEIGHT)
    # can still look up its own next_target without running off the end.
    target_sequence = generate_target_sequence(rng, config.TOWER_HEIGHT + 2)
    players = {"p1": new_player(target_sequence), "p2": new_player(target_sequence)}
    # Everything counts as held at first: the button that closed HOW TO
    # PLAY (any button, gates included) must be let go before it acts.
    prev_held = {"p1": {name: True for name in ACTIONS}, "p2": {name: True for name in ACTIONS}}
    prev_up_held = {"p1": True, "p2": True}
    game_time = 0.0
    idle_seconds = 0.0
    attack_flash: tuple[str, float] | None = None  # (attacker_key, started_at)
    perfect_flash: dict[str, float | None] = {"p1": None, "p2": None}  # started_at per player
    # Matching the target no longer auto-climbs -- pushing up confirms it.
    # Confirming on the WRONG state locks that player's input out until
    # `stun_until[pk]`; `correct_since[pk]` times how long they've been
    # sitting on a correct-but-unconfirmed state, to drive the "push up" hint.
    stun_until: dict[str, float] = {"p1": 0.0, "p2": 0.0}
    correct_since: dict[str, float | None] = {"p1": None, "p2": None}

    # Animated camera position per player (see _camera_step).
    visual_floor = {pk: float(players[pk].floor) for pk in ("p1", "p2")}
    climb_anim: dict[str, tuple[float, float, float] | None] = {"p1": None, "p2": None}

    # While paused, game_time stands still -- every timer in here (stuns,
    # flashes, the climb animation) is measured against it, so they all
    # freeze with it. `frozen_frame` is the last frame drawn before pausing,
    # shown dimmed behind the menu.
    pause_menu = PauseMenu()
    frozen_frame: pygame.Surface | None = None

    left_half = pygame.Rect(0, 0, config.INTERNAL_WIDTH // 2, config.INTERNAL_HEIGHT)
    right_half = pygame.Rect(
        config.INTERNAL_WIDTH // 2, 0, config.INTERNAL_WIDTH // 2, config.INTERNAL_HEIGHT
    )

    while True:
        dt = clock.tick(config.FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit", players
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
                show_fps = not show_fps

        keys = read_keys()
        p1_raw, p2_raw = _poll_players(keys)
        raws = {"p1": p1_raw, "p2": p2_raw}

        if _wants_quit(p1_raw, p2_raw, keys):
            return "quit", players

        # The idle timeout keeps counting while paused: a game abandoned in
        # the pause menu still goes back to the title by itself.
        pause_buttons = _pause_buttons(p1_raw, p2_raw, keys)
        any_input = (
            any(raws[pk].button_held[a] for pk in ("p1", "p2") for a in ACTIONS)
            or pause_buttons.any_held()
        )
        idle_seconds = 0.0 if any_input else idle_seconds + dt
        if idle_seconds >= config.IDLE_TIMEOUT_SECONDS:
            return "idle", players

        pause_state = _update_pause(pause_menu, pause_buttons, sounds)
        if pause_state == "title":
            return "title", players
        if pause_state == "paused":
            # Keep the edge trackers current, so a button pressed in the menu
            # -- A and B are the RESET and H gates -- doesn't fire as a gate
            # on the first frame back.
            for player_key in ("p1", "p2"):
                for name in ACTIONS:
                    prev_held[player_key][name] = raws[player_key].button_held[name]
                prev_up_held[player_key] = raws[player_key].up_held
            if frozen_frame is None:
                frozen_frame = internal.copy()
            internal.blit(frozen_frame, (0, 0))
            if pause_menu.paused:
                screens.draw_pause_menu(
                    internal, pause_title_font, pause_item_font, pause_hint_font, PAUSE_ITEMS,
                    pause_menu.selected,
                    screens.blink_visible(pygame.time.get_ticks() / 1000.0, config.TITLE_BLINK_PERIOD),
                )
            present(internal, window)
            pygame.display.flip()
            continue
        frozen_frame = None
        game_time += dt

        for player_key in ("p1", "p2"):
            raw = raws[player_key]
            stunned = game_time < stun_until[player_key]
            if not stunned:
                for name in ACTIONS:
                    if pressed_edge(prev_held[player_key][name], raw.button_held[name]):
                        players[player_key] = apply_action(players[player_key], name)
                        sounds.gate.play()

                if pressed_edge(prev_up_held[player_key], raw.up_held):
                    before = players[player_key]
                    after, advanced = confirm_climb(before, target_sequence)
                    if advanced:
                        players[player_key] = after
                        sounds.climb.play()
                        if after.charges > before.charges:
                            perfect_flash[player_key] = game_time
                            sounds.perfect.play()
                    else:
                        stun_until[player_key] = game_time + config.STUN_DURATION
                        sounds.stun.play()

            for name in ACTIONS:
                prev_held[player_key][name] = raw.button_held[name]
            prev_up_held[player_key] = raw.up_held

            is_correct_now = states_equal(
                players[player_key].state, players[player_key].current_target
            )
            if is_correct_now:
                if correct_since[player_key] is None:
                    correct_since[player_key] = game_time
            else:
                correct_since[player_key] = None

        players, attacker = _handle_attacks(players, rng)
        if attacker:
            attack_flash = (attacker, game_time)
            sounds.shot.play()

        attack_progress = {"p1": None, "p2": None}
        if attack_flash is not None:
            attacker_key, started_at = attack_flash
            age = game_time - started_at
            if age < config.ATTACK_BEAM_DURATION:
                attack_progress[attacker_key] = age / config.ATTACK_BEAM_DURATION

        perfect_progress = {"p1": None, "p2": None}
        for pk in ("p1", "p2"):
            started_at = perfect_flash[pk]
            if started_at is not None:
                age = game_time - started_at
                if age < config.PERFECT_FLASH_DURATION:
                    perfect_progress[pk] = age / config.PERFECT_FLASH_DURATION
                else:
                    perfect_flash[pk] = None

        stun_progress = {"p1": None, "p2": None}
        for pk in ("p1", "p2"):
            remaining = stun_until[pk] - game_time
            if remaining > 0:
                stun_progress[pk] = 1.0 - remaining / config.STUN_DURATION

        push_up_hint = {"p1": False, "p2": False}
        for pk in ("p1", "p2"):
            started_at = correct_since[pk]
            if started_at is not None and game_time - started_at >= config.PUSH_UP_HINT_DELAY:
                push_up_hint[pk] = True

        climb_progress = {"p1": None, "p2": None}
        for pk in ("p1", "p2"):
            climb_anim[pk], visual_floor[pk], climb_progress[pk] = _camera_step(
                climb_anim[pk], visual_floor[pk], players[pk].floor, game_time
            )

        internal.blit(background, (0, 0))
        pygame.draw.line(
            internal, config.COLOR_TOWER_TRIM,
            (config.INTERNAL_WIDTH // 2, 0), (config.INTERNAL_WIDTH // 2, config.INTERNAL_HEIGHT), 2,
        )

        p1_climber_pos = _draw_player_half(
            internal, left_half, "P1", players["p1"], visual_floor["p1"], climb_progress["p1"],
            attack_progress["p1"], stun_progress["p1"], config.COLOR_PLAYER_1, header_font,
            state_font, block_fonts, game_time, climber_side="right",
        )
        p2_climber_pos = _draw_player_half(
            internal, right_half, "P2", players["p2"], visual_floor["p2"], climb_progress["p2"],
            attack_progress["p2"], stun_progress["p2"], config.COLOR_PLAYER_2, header_font,
            state_font, block_fonts, game_time, climber_side="left",
        )

        legend_y = config.INTERNAL_HEIGHT - LEGEND_HEIGHT // 2
        visuals.draw_button_grid(
            internal, (config.INTERNAL_WIDTH // 4, legend_y), button_grid_data,
            grid_gate_font,
            accent_color=config.COLOR_PLAYER_1, pressed=raws["p1"].button_held,
        )
        visuals.draw_button_grid(
            internal, (config.INTERNAL_WIDTH * 3 // 4, legend_y), button_grid_data,
            grid_gate_font,
            accent_color=config.COLOR_PLAYER_2, pressed=raws["p2"].button_held,
        )

        climber_pos_by_player = {"p1": p1_climber_pos, "p2": p2_climber_pos}
        color_by_player = {"p1": config.COLOR_PLAYER_1, "p2": config.COLOR_PLAYER_2}
        for pk in ("p1", "p2"):
            if attack_progress[pk] is not None:
                visuals.draw_muzzle_flash(
                    internal, *climber_pos_by_player[pk], color_by_player[pk], attack_progress[pk]
                )
            if perfect_progress[pk] is not None:
                visuals.draw_perfect_flash(
                    internal, *climber_pos_by_player[pk], color_by_player[pk], perfect_progress[pk],
                    perfect_font,
                )
            if stun_progress[pk] is not None:
                visuals.draw_stun_flash(internal, *climber_pos_by_player[pk], stun_progress[pk], perfect_font)
            elif push_up_hint[pk]:
                visuals.draw_push_up_hint(internal, *climber_pos_by_player[pk], perfect_font)

        if attack_flash is not None:
            attacker_key, started_at = attack_flash
            age = game_time - started_at
            if age < config.ATTACK_BEAM_DURATION:
                from_pos = p1_climber_pos if attacker_key == "p1" else p2_climber_pos
                to_pos = p2_climber_pos if attacker_key == "p1" else p1_climber_pos
                _draw_attack_beam(
                    internal, from_pos, to_pos,
                    config.COLOR_PLAYER_1 if attacker_key == "p1" else config.COLOR_PLAYER_2,
                    age / config.ATTACK_BEAM_DURATION,
                )
            else:
                attack_flash = None

        if show_fps:
            fps_surf = font.render(f"{clock.get_fps():.0f} fps", False, config.COLOR_FPS)
            internal.blit(fps_surf, (4, 4))

        present(internal, window)
        pygame.display.flip()

        if players["p1"].floor >= config.TOWER_HEIGHT:
            return "p1", players
        if players["p2"].floor >= config.TOWER_HEIGHT:
            return "p2", players


def _solo_tower_region() -> pygame.Rect:
    """The same size of tower region as one versus half, placed so the tower
    body (not the region) is centred on screen. The climber hangs on its
    right wall."""
    width = config.INTERNAL_WIDTH // 2 - 32
    tower_width = round(width * visuals.TOWER_WIDTH_RATIO)
    return pygame.Rect(
        config.INTERNAL_WIDTH // 2 - tower_width // 2, config.SOLO_TOWER_TOP, width,
        config.INTERNAL_HEIGHT - config.SOLO_TOWER_TOP - INFO_HEIGHT - LEGEND_HEIGHT,
    )


def run_solo(
    surface: pygame.Surface,
    window: pygame.Surface | None,
    sounds: sound.Sounds,
    show_fps: bool,
    times: Times,
) -> tuple[str, float]:
    """One time-trial climb: a fresh equal-difficulty tower, centred and
    playable from either pad; 3, 2, 1, GO, then the clock runs until the top
    floor. Wrong confirms stun as in versus; there are no charges or attacks.
    Returns (result, seconds on the clock): result is 'done' (reached the top,
    after the finish banner), 'quit', 'idle' or 'title' (picked in the pause
    menu)."""
    internal = surface
    clock = pygame.time.Clock()
    fps_font = fonts.load_font(10)
    header_font = fonts.load_font(11)
    state_font = fonts.load_font(9)
    block_fonts = [fonts.load_font(11), fonts.load_font(9), fonts.load_font(7)]
    grid_gate_font = fonts.load_font(8)
    perfect_font = fonts.load_font(9)
    timer_font = fonts.load_font(16)
    countdown_font = fonts.load_font(32)
    banner_note_font = fonts.load_font(8)
    pause_title_font = fonts.load_font(16)
    pause_item_font = fonts.load_font(10)
    pause_hint_font = fonts.load_font(7)
    background = visuals.make_background(config.INTERNAL_WIDTH, config.INTERNAL_HEIGHT)
    button_grid_data = screens.button_grid()
    tower_region = _solo_tower_region()

    target_sequence = solo.equal_difficulty_tower(
        random.Random(), config.TOWER_HEIGHT, config.SOLO_TOTAL_PRESSES
    )
    player = new_player(target_sequence)
    prev_held = {name: False for name in ACTIONS}
    prev_up_held = False
    # game_time runs from the start of the countdown and, as in run_game,
    # stands still while paused; the run's clock is `timer`, which only
    # counts from GO until the top floor.
    game_time = 0.0
    timer = solo.Timer()
    idle_seconds = 0.0
    stun_until = 0.0
    correct_since: float | None = None
    perfect_at: float | None = None
    finished_at: float | None = None
    finish_note = ""
    visual_floor = 0.0
    climb_anim: tuple[float, float, float] | None = None
    pause_menu = PauseMenu()
    frozen_frame: pygame.Surface | None = None

    while True:
        dt = clock.tick(config.FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit", timer.seconds
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
                show_fps = not show_fps

        keys = read_keys()
        p1_raw, p2_raw = _poll_players(keys)
        raw = _merged(p1_raw, p2_raw)

        if _wants_quit(p1_raw, p2_raw, keys):
            return "quit", timer.seconds

        pause_buttons = _pause_buttons(p1_raw, p2_raw, keys)
        any_input = any(raw.button_held.values()) or pause_buttons.any_held()
        idle_seconds = 0.0 if any_input else idle_seconds + dt
        if idle_seconds >= config.IDLE_TIMEOUT_SECONDS:
            return "idle", timer.seconds

        # Once the top is reached there is nothing left to pause.
        pause_state = _update_pause(pause_menu, pause_buttons, sounds) if finished_at is None else "play"
        if pause_state == "title":
            return "title", timer.seconds
        timer.paused = pause_state == "paused"
        if timer.paused:
            # As in run_game: keep the edge trackers current, so a button
            # pressed in the menu doesn't fire as a gate on the first frame back.
            for name in ACTIONS:
                prev_held[name] = raw.button_held[name]
            prev_up_held = raw.up_held
            if frozen_frame is None:
                frozen_frame = internal.copy()
            internal.blit(frozen_frame, (0, 0))
            if pause_menu.paused:
                screens.draw_pause_menu(
                    internal, pause_title_font, pause_item_font, pause_hint_font, PAUSE_ITEMS,
                    pause_menu.selected,
                    screens.blink_visible(pygame.time.get_ticks() / 1000.0, config.TITLE_BLINK_PERIOD),
                )
            present(internal, window)
            pygame.display.flip()
            continue
        frozen_frame = None
        previous_time, game_time = game_time, game_time + dt
        # 3, 2, 1 and GO!: a beep as each one appears.
        for beep_at in (0.0, 1.0, 2.0):
            if previous_time <= beep_at < game_time:
                sounds.tick.play()
        if previous_time <= config.SOLO_COUNTDOWN < game_time:
            sounds.go.play()

        playing = finished_at is None and game_time >= config.SOLO_COUNTDOWN
        if playing:
            # The clock starts exactly at GO, not at the frame boundary after it.
            timer.update(game_time - max(previous_time, config.SOLO_COUNTDOWN))
            if game_time >= stun_until:
                for name in ACTIONS:
                    if pressed_edge(prev_held[name], raw.button_held[name]):
                        player = apply_action(player, name)
                        sounds.gate.play()
                if pressed_edge(prev_up_held, raw.up_held):
                    after, advanced = confirm_climb(player, target_sequence)
                    if advanced:
                        sounds.climb.play()
                        # A minimum-press floor still earns its PERFECT, but
                        # the charge it adds does nothing in a solo run.
                        if after.charges > player.charges:
                            perfect_at = game_time
                            sounds.perfect.play()
                        player = after
                        if player.floor >= config.TOWER_HEIGHT:
                            finished_at = game_time
                            sounds.win.play()
                            finish_note = (
                                "A TOP 10 TIME!" if times.qualifies(timer.seconds)
                                else f"BEST {solo.format_time(times.entries[0].seconds)}"
                            )
                    else:
                        stun_until = game_time + config.STUN_DURATION
                        sounds.stun.play()
        for name in ACTIONS:
            prev_held[name] = raw.button_held[name]
        prev_up_held = raw.up_held

        if finished_at is not None and game_time - finished_at >= config.SOLO_FINISH_DURATION:
            return "done", timer.seconds

        if states_equal(player.state, player.current_target):
            if correct_since is None:
                correct_since = game_time
        else:
            correct_since = None
        perfect_progress = None
        if perfect_at is not None and game_time - perfect_at < config.PERFECT_FLASH_DURATION:
            perfect_progress = (game_time - perfect_at) / config.PERFECT_FLASH_DURATION
        stun_progress = None
        if stun_until > game_time:
            stun_progress = 1.0 - (stun_until - game_time) / config.STUN_DURATION
        push_up_hint = (
            correct_since is not None and finished_at is None
            and game_time - correct_since >= config.PUSH_UP_HINT_DELAY
        )
        climb_anim, visual_floor, climb_progress = _camera_step(
            climb_anim, visual_floor, player.floor, game_time
        )

        internal.blit(background, (0, 0))
        climber_pos = visuals.draw_tower(
            internal, tower_region, player.floor, visual_floor, player.current_target,
            player.next_target, config.COLOR_PLAYER_1, block_fonts, game_time,
            climber_side="right", climb_progress=climb_progress, stun_progress=stun_progress,
        )
        visuals.blit_outlined_text(
            internal, header_font, f"FLOOR {player.floor}/{config.TOWER_HEIGHT}",
            config.COLOR_TEXT, (8, 6),
        )
        visuals.blit_outlined_text_centered(
            internal, timer_font, timer.format(), config.COLOR_TEXT, config.INTERNAL_WIDTH // 2, 4
        )
        info_y = tower_region.bottom + 8
        you_rect = visuals.blit_outlined_text(
            internal, state_font, "YOU:", config.COLOR_PLAYER_1,
            (tower_region.x, info_y),
        )
        visuals.blit_outlined_text(
            internal, state_font, render_state(player.state), config.COLOR_TEXT,
            (you_rect.right + 4, info_y),
        )
        visuals.draw_button_grid(
            internal, (config.INTERNAL_WIDTH // 2, config.INTERNAL_HEIGHT - LEGEND_HEIGHT // 2),
            button_grid_data, grid_gate_font,
            accent_color=config.COLOR_PLAYER_1, pressed=raw.button_held,
        )

        if perfect_progress is not None:
            visuals.draw_perfect_flash(
                internal, *climber_pos, config.COLOR_PLAYER_1, perfect_progress, perfect_font
            )
        if stun_progress is not None:
            visuals.draw_stun_flash(internal, *climber_pos, stun_progress, perfect_font)
        elif push_up_hint:
            visuals.draw_push_up_hint(internal, *climber_pos, perfect_font)

        if game_time < config.SOLO_COUNTDOWN:
            screens.draw_countdown(internal, countdown_font, str(3 - int(game_time)))
        elif game_time < config.SOLO_COUNTDOWN + config.SOLO_GO_DURATION:
            screens.draw_countdown(internal, countdown_font, "GO!")
        if finished_at is not None:
            screens.draw_finish_banner(
                internal, pause_title_font, timer_font, banner_note_font, timer.format(), finish_note
            )

        if show_fps:
            fps_surf = fps_font.render(f"{clock.get_fps():.0f} fps", False, config.COLOR_FPS)
            internal.blit(fps_surf, (4, config.INTERNAL_HEIGHT - 12))

        present(internal, window)
        pygame.display.flip()


def run_initials(
    surface: pygame.Surface, window: pygame.Surface | None, times: Times, seconds: float
) -> tuple[str, int | None]:
    """Three initials for a top-10 time, as in Gate Drop: the stick changes
    the letter and moves, A goes on and finishes on the last letter, B steps
    back. Saves the entry and returns (result, its rank): 'done', 'idle'
    (abandoned; saved as typed so far) or 'quit' (not saved)."""
    internal = surface
    clock = pygame.time.Clock()
    title_font = fonts.load_font(16)
    letter_font = fonts.load_font(24)
    small_font = fonts.load_font(8)
    entry = screens.NameEntry()
    repeat_x, repeat_y = screens.AutoRepeat(), screens.AutoRepeat()
    time_text = solo.format_time(seconds)
    t = 0.0
    idle_seconds = 0.0
    # A or B still held from the run (both are gates there: RESET and H),
    # or a stick still pushed from the last climb, must be let go before it
    # counts, or it would pick a letter on the first frame.
    prev_confirm = prev_back = True
    stick_free = False

    def save() -> int | None:
        rank = times.add(entry.name, seconds)
        return rank if rank >= 0 else None

    while True:
        dt = clock.tick(config.FPS) / 1000.0
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit", None

        keys = read_keys()
        p1_raw, p2_raw = _poll_players(keys)
        if _wants_quit(p1_raw, p2_raw, keys):
            return "quit", None

        raw = _merged(p1_raw, p2_raw)
        dx, dy, confirm, back = _menu_held(raw, keys)
        any_input = dx or dy or confirm or back or raw.start_held or any(raw.button_held.values())
        idle_seconds = 0.0 if any_input else idle_seconds + dt
        if idle_seconds >= config.IDLE_TIMEOUT_SECONDS:
            return "idle", save()

        stick_free = stick_free or (dx == 0 and dy == 0)
        if not stick_free:
            dx = dy = 0
        entry.update(
            repeat_x.update(dt, dx), repeat_y.update(dt, dy),
            pressed_edge(prev_confirm, confirm), pressed_edge(prev_back, back),
        )
        prev_confirm, prev_back = confirm, back
        if entry.done:
            return "done", save()

        screens.draw_initials(internal, title_font, letter_font, small_font, entry, time_text, t)
        present(internal, window)
        pygame.display.flip()


def run_times_table(
    surface: pygame.Surface, window: pygame.Surface | None, times: Times, new_rank: int | None
) -> str:
    """FASTEST CLEARS, with `new_rank`'s entry blinking. Returns 'done' after
    TIMES_TABLE_DURATION, or on A, B or Start after TIMES_TABLE_LOCK; or
    'quit'."""
    internal = surface
    clock = pygame.time.Clock()
    title_font = fonts.load_font(16)
    row_font = fonts.load_font(10)
    small_font = fonts.load_font(8)
    t = 0.0
    prev_pressed = True  # a button held from the screen before must be let go

    while True:
        dt = clock.tick(config.FPS) / 1000.0
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

        keys = read_keys()
        p1_raw, p2_raw = _poll_players(keys)
        if _wants_quit(p1_raw, p2_raw, keys):
            return "quit"

        raw = _merged(p1_raw, p2_raw)
        _dx, _dy, confirm, back = _menu_held(raw, keys)
        pressed = confirm or back or _wants_start(p1_raw, p2_raw, keys)
        if t >= config.TIMES_TABLE_DURATION:
            return "done"
        if t >= config.TIMES_TABLE_LOCK and pressed_edge(prev_pressed, pressed):
            return "done"
        prev_pressed = pressed

        screens.draw_times_table(internal, title_font, row_font, small_font, times.entries, new_rank, t)
        present(internal, window)
        pygame.display.flip()


def run_solo_flow(
    surface: pygame.Surface,
    window: pygame.Surface | None,
    sounds: sound.Sounds,
    show_fps: bool,
    times: Times,
) -> str:
    """A solo run and what follows a finished one: initials for a top-10 time,
    then the table. Returns 'quit' to leave the game; anything else means back
    to the title."""
    result, seconds = run_solo(surface, window, sounds, show_fps, times)
    if result != "done":
        return result
    new_rank = None
    if times.qualifies(seconds):
        result, new_rank = run_initials(surface, window, times, seconds)
        if result != "done":
            return result
    return run_times_table(surface, window, times, new_rank)


def run_flow(
    surface: pygame.Surface,
    window: pygame.Surface | None,
    sounds: sound.Sounds,
    show_fps: bool,
    times: Times,
) -> None:
    """Title, HOW TO PLAY, a match, and back to the title, until someone
    quits. Every match picked on the title gets the tutorial first; there is
    no rematch that skips it."""
    mode = "2p"  # the title starts on whichever was played last

    while True:
        action = run_title_screen(surface, window, mode, sounds)
        if action == "quit":
            return
        mode = action

        result = run_tutorial(surface, window, mode, sounds)
        if result == "quit":
            return
        if result == "idle":
            continue

        if mode == "1p":
            if run_solo_flow(surface, window, sounds, show_fps, times) == "quit":
                return
            continue

        result, players = run_game(surface, window, sounds, show_fps)
        if result == "quit":
            return
        if result in ("p1", "p2"):
            floors = {"p1": players["p1"].floor, "p2": players["p2"].floor}
            if run_winner_screen(surface, window, result, floors, sounds) == "quit":
                return
        # result == "idle" or "title" falls straight back to the title screen


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    set_keyboard_enabled(not args.no_keyboard)

    pygame.init()
    pygame.joystick.init()
    surface, window = make_display(args.fullscreen, args.window_size)
    pygame.display.set_caption("Quantum Towers")

    if args.input_test:
        from quantum_towers.input_test import run_input_test

        run_input_test(surface, window)
    else:
        sounds = sound.load_sounds()
        show_fps = args.fps or config.SHOW_FPS_DEFAULT
        run_flow(surface, window, sounds, show_fps, Times(config.TIMES_FILE))

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
