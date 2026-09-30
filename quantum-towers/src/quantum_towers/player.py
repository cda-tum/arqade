"""Per-player tower-climbing state and floor-advance logic."""

from __future__ import annotations

import random
from dataclasses import dataclass

from quantum_towers.quantum import ACTIONS, State, states_equal, zero_state
from quantum_towers.search import minimum_steps
from quantum_towers.targets import generate_target


@dataclass(frozen=True)
class PlayerState:
    floor: int
    state: State
    current_target: State
    next_target: State
    press_count: int
    minimum_steps_for_floor: int
    charges: int


def _required_minimum_steps(start: State, target: State) -> int:
    """minimum_steps, but fails loudly instead of silently defaulting to 0.

    Targets are generated via a short walk (targets.MAX_WALK_LENGTH, well
    under search.py's depth cap), so this should always find a path -- a
    None here means that invariant broke (e.g. the walk/search depths were
    detuned relative to each other), which should never quietly turn into
    an unearnable charge for a floor.
    """
    steps = minimum_steps(start, target)
    if steps is None:
        raise ValueError(
            f"target unreachable within the search depth cap from {start} to {target} "
            "-- targets.MAX_WALK_LENGTH and search's max_depth are out of sync"
        )
    return steps


def new_player(target_sequence: list[State]) -> PlayerState:
    """`target_sequence` is shared between both players (see
    targets.generate_target_sequence) so neither gets a randomly easier or
    harder set of floors than the other."""
    start = zero_state()
    current_target = target_sequence[0]
    next_target = target_sequence[1]
    return PlayerState(
        floor=0,
        state=start,
        current_target=current_target,
        next_target=next_target,
        press_count=0,
        minimum_steps_for_floor=_required_minimum_steps(start, current_target),
        charges=0,
    )


def apply_action(player: PlayerState, action_name: str) -> PlayerState:
    """Apply one gate/reset press. This only ever updates the qubit state
    and the press count -- even landing exactly on current_target does NOT
    advance the floor by itself. The player must separately confirm it (see
    `confirm_climb`, triggered by pushing up), so that matching the target
    is something you notice and act on, not something that happens for you.
    """
    new_state = ACTIONS[action_name](player.state)
    return PlayerState(
        floor=player.floor,
        state=new_state,
        current_target=player.current_target,
        next_target=player.next_target,
        press_count=player.press_count + 1,
        minimum_steps_for_floor=player.minimum_steps_for_floor,
        charges=player.charges,
    )


def confirm_climb(player: PlayerState, target_sequence: list[State]) -> tuple[PlayerState, bool]:
    """Attempt to climb a floor by confirming the current state against
    current_target (the player pushes up to do this). Returns
    (possibly-advanced player, whether it succeeded).

    On success, advances the floor, pulls the next target from the shared
    `target_sequence`, resets press_count, and awards a charge if the floor
    was solved in exactly minimum_steps_for_floor presses. On failure, the
    player is returned unchanged -- punishing a wrong confirm (e.g. a brief
    stun) is the caller's job, since that's timing/presentation, not pure
    game state.
    """
    if not states_equal(player.state, player.current_target):
        return player, False

    gained_charge = player.press_count == player.minimum_steps_for_floor
    new_floor = player.floor + 1
    new_current_target = player.next_target
    new_next_target = target_sequence[new_floor + 1]
    return (
        PlayerState(
            floor=new_floor,
            state=player.state,
            current_target=new_current_target,
            next_target=new_next_target,
            press_count=0,
            minimum_steps_for_floor=_required_minimum_steps(player.state, new_current_target),
            charges=player.charges + (1 if gained_charge else 0),
        ),
        True,
    )


def knockback(player: PlayerState, floors: int, rng: random.Random) -> PlayerState:
    """Drop `player` down `floors` (never below 0) after being attacked.

    Their qubit state is untouched -- only position and targets reset: a
    fresh current/next target pair is generated from wherever their state
    already is, so the lost floors must be genuinely re-solved. Charges are
    left as-is; resetting the attacker's charges is the caller's job (they
    fired the attack, this function only handles the victim's side).
    """
    new_floor = max(0, player.floor - floors)
    new_current_target = generate_target(rng, player.state)
    new_next_target = generate_target(rng, new_current_target)
    return PlayerState(
        floor=new_floor,
        state=player.state,
        current_target=new_current_target,
        next_target=new_next_target,
        press_count=0,
        minimum_steps_for_floor=_required_minimum_steps(player.state, new_current_target),
        charges=player.charges,
    )
