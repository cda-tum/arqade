"""Error layouts: where each round's Pauli errors sit. Pure and seeded, so
both boards get exactly the same layout."""

from __future__ import annotations

import random

from gate_drop import config


def errors_for_level(level: int) -> int:
    """Level n has 2n + 2 errors: 4 on level 1, up to 22 on level 10."""
    return 2 * max(config.LEVEL_MIN, min(config.LEVEL_MAX, level)) + 2


def error_layout(rng: random.Random, count: int) -> list:
    """`count` errors on distinct cells in the bottom ERROR_ROWS rows. Two
    identical errors are never next to each other on a wire (gaps skipped),
    so none cancels out on its own."""
    top = config.ROWS - config.ERROR_ROWS
    cells = rng.sample([(x, y) for x in range(config.COLS) for y in range(top, config.ROWS)], count)
    layout = []
    for x in range(config.COLS):
        below = None
        for pos in sorted((c for c in cells if c[0] == x), key=lambda c: -c[1]):
            kind = rng.choice([k for k in config.PAULIS if k != below])
            layout.append((pos, kind))
            below = kind
    return sorted(layout)
