"""Breadth-first search for the true minimum number of actions to reach a
target state -- not "however many gates it took to generate it" (a target
built by H,X,H happens to equal a 1-step Z target; the game must credit the
real minimum, not the generating walk's length).
"""

from __future__ import annotations

from quantum_towers.quantum import ACTIONS, State, states_equal


def minimum_steps(start: State, target: State, max_depth: int = 6) -> int | None:
    """Shortest number of ACTIONS to turn start into target, up to max_depth.
    Returns None if not found within that depth. Uses exact state equality
    (global phase included) -- see quantum.py's module docstring for why."""
    if states_equal(start, target):
        return 0

    visited = [start]
    frontier = [start]
    depth = 0
    while frontier and depth < max_depth:
        depth += 1
        next_frontier = []
        for state in frontier:
            for action in ACTIONS.values():
                new_state = action(state)
                if states_equal(new_state, target):
                    return depth
                if not any(states_equal(new_state, v) for v in visited):
                    visited.append(new_state)
                    next_frontier.append(new_state)
        frontier = next_frontier

    return None
