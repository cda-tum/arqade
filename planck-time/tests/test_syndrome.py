"""SYNDROME!'s monster, DECOHERENCE: its attack must never give away which
qubit it hit (the parity checks are the only clue: that is the point of
syndrome measurement), and its face must never touch the rules."""

import pygame
import pytest

from planck_time import config
from planck_time.microgames import PlayerInput
from planck_time.microgames import syndrome as syn
from planck_time.microgames.syndrome import DIE, N, ROW_Y, SPACING, Syndrome, qubit_x

DT = 1 / 60
IDLE = PlayerInput()


def _checks_mask() -> list[pygame.Rect]:
    """Where the hit is allowed to show: the checks with their glow and red
    half-wires, and the ancilla readout lines down from them."""
    rects = []
    for i in range(N - 1):
        cx = (qubit_x(i) + qubit_x(i + 1)) // 2
        rects.append(pygame.Rect(cx - SPACING // 2, ROW_Y - 13, SPACING, 27))
        rects.append(pygame.Rect(cx - 2, ROW_Y, 5, DIE.bottom - ROW_Y))
    return rects


def _forced(target: int) -> Syndrome:
    """A fight whose first error is forced onto `target`, everything else equal."""
    game = Syndrome(4, 0, Syndrome.duration_for(0))
    game._fresh = lambda phase, k: [target]
    return game


def test_the_attack_does_not_reveal_the_hit_qubit():
    pygame.init()
    a, b = _forced(0), _forced(4)
    sa, sb = (pygame.Surface((config.SCREEN_W, config.SCREEN_H)) for _ in range(2))
    mask = _checks_mask()
    compared = 0
    landed = None
    # from before the wind-up, through the landing, the bolt and the splash
    for _ in range(round(1.4 / DT)):
        a.update(DT, IDLE)
        b.update(DT, IDLE)
        assert a.landed_at == b.landed_at and a.next_at == b.next_at
        a.draw(sa)
        b.draw(sb)
        if a.flips:
            landed = landed or a.t
            assert a.flips == {0} and b.flips == {4}
        for r in mask:
            sa.fill((0, 0, 0), r)
            sb.fill((0, 0, 0), r)
        assert pygame.image.tobytes(sa, "RGB") == pygame.image.tobytes(sb, "RGB"), f"t={a.t:.3f}"
        compared += 1
    assert landed is not None and compared > 60
    # and the checks themselves do differ, so the comparison was not vacuous
    a.draw(sa)
    b.draw(sb)
    assert pygame.image.tobytes(sa, "RGB") != pygame.image.tobytes(sb, "RGB")


def test_the_monster_winds_up_half_a_second_before_each_error():
    game = Syndrome(1, 0, Syndrome.duration_for(0))
    seen = []
    while not game.flips:
        seen.append((game.t, game.windup()))
        game.update(DT, IDLE)
    landing = game.landed_at
    started = min(t for t, k in seen if k > 0)
    assert landing - started == pytest.approx(syn.WINDUP, abs=2 * DT)
    assert max(k for _, k in seen) > 0.95


def test_no_wind_up_for_an_error_that_would_land_after_the_end():
    game = Syndrome(1, 0, Syndrome.duration_for(0))
    game.next_at = game.duration + 0.1
    game.t = game.duration - 0.2
    assert game.windup() == 0.0


def test_the_monster_reacts_to_presses():
    game = Syndrome(2, 0, Syndrome.duration_for(0))
    while not game.flips:
        game.update(DT, IDLE)
    q = next(iter(game.flips))
    game.cursor = (q + 1) % N if (q + 1) % N not in game.flips else (q - 1) % N
    game.update(DT, PlayerInput(a=True, a_held=True))  # a wrong press
    assert game.wrong_at >= 0 and game.fixed_at < 0
    game.cursor = q
    game.update(DT, PlayerInput(a=True, a_held=True))  # the right one
    assert game.fixed_at > game.wrong_at


@pytest.mark.parametrize("level", (0, 3, 6))
def test_drawing_never_touches_the_rules(level):
    """The same fight, drawn every frame or never, plays out the same."""
    pygame.init()
    surf = pygame.Surface((config.SCREEN_W, config.SCREEN_H))
    results = []
    for draw in (False, True):
        game = Syndrome(9, level, Syndrome.duration_for(level))
        trace = []
        for _ in range(round(game.duration / DT)):
            game.update(DT, game.bot())
            if draw:
                game.draw(surf)
            trace.append((tuple(sorted(game.flips)), game.cursor, game.next_at))
        results.append((trace, game.rng.getstate()))
    assert results[0] == results[1]


def test_every_mood_and_the_finale_draw():
    pygame.init()
    surf = pygame.Surface((config.SCREEN_W, config.SCREEN_H))
    game = Syndrome(0, 0, Syndrome.duration_for(0))
    for _ in range(round(game.duration / DT)):
        game.update(DT, game.bot())
        game.draw(surf)
    game.timeout()
    for _ in range(90):  # the dissolve
        game.update(DT, IDLE)
        game.draw(surf)
    Syndrome.portrait(surf, (120, 60), 0.5)
