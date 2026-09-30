"""Target-state generation for tower floors.

Each new target is a short random walk of actions starting from the
*previous* target, so the newly-revealed target is always reachable from
wherever the player will be standing once they solve the current one.
"""

from __future__ import annotations

import random

from quantum_towers.quantum import ACTIONS, State, states_equal, zero_state

MIN_WALK_LENGTH = 2
MAX_WALK_LENGTH = 4


def generate_target(rng: random.Random, previous: State) -> State:
    """A new target reachable from `previous`, never a no-op (the exact same
    state -- global phase included, so a walk that only flips overall phase
    counts as a genuinely different, valid target now)."""
    action_names = list(ACTIONS.keys())
    while True:
        length = rng.randint(MIN_WALK_LENGTH, MAX_WALK_LENGTH)
        state = previous
        for _ in range(length):
            state = ACTIONS[rng.choice(action_names)](state)
        if not states_equal(state, previous):
            return state


def generate_target_sequence(rng: random.Random, count: int) -> list[State]:
    """A single chain of `count` targets, each reachable from the one before
    it (starting from |0>) -- generated once per match from one shared rng
    stream and handed to both players, so neither's normal climb is
    randomly easier or harder than the other's. `sequence[f]` is the target
    for reaching floor `f + 1` from floor `f`."""
    sequence = []
    previous = zero_state()
    for _ in range(count):
        previous = generate_target(rng, previous)
        sequence.append(previous)
    return sequence
