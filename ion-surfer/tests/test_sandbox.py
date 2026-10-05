"""The sandbox's ANHARMONIC warning, driven through the real game and its
quantum simulation."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from ion_surfer import game as game_mod  # noqa: E402
from ion_surfer import sandbox as sandbox_mod  # noqa: E402


@pytest.fixture
def game(tmp_path, monkeypatch):
    monkeypatch.setattr(game_mod, "SCORE_FILE", tmp_path / "scores.json")
    pygame.init()
    yield game_mod.Game(pygame.Surface((game_mod.W, game_mod.H)), sandbox_only=True)
    pygame.quit()


def run(sb, seconds):
    """Like the game's sandbox_frame + measure, without electrode input."""
    for _ in range(round(seconds * 60)):
        for _ in range(4):
            sb.step(game_mod.STEP, False, False)
        sb.measure()


def test_kicks_in_the_harmonic_start_trap_never_warn(game):
    sb = game.sandbox
    for _ in range(4):
        sb.kick(0)
        run(sb, 1 / 60)
    run(sb, 6)
    assert sb.views[0].ps.area() == pytest.approx(1.0, abs=0.05)
    assert not sb.anharmonic


def test_a_barrier_under_the_packet_splits_it_and_warns(game):
    sb = game.sandbox
    v = game.curves[0].v
    v[5] = v[6] = 140  # a hump in the middle of the start bowl
    sb.sync_potential()
    run(sb, 3)
    assert sb.views[0].ps.area() > 2
    assert sb.anharmonic


def test_warning_waits_a_second_then_holds(game, monkeypatch):
    sb = game.sandbox
    monkeypatch.setattr(sandbox_mod, "ANHARMONIC_AREA", 0.5)  # everything counts as past it
    run(sb, 0.9)
    assert not sb.anharmonic
    run(sb, 0.2)
    assert sb.anharmonic
    monkeypatch.setattr(sandbox_mod, "ANHARMONIC_AREA", 100.0)  # and now nothing does
    run(sb, 0.9)
    assert sb.anharmonic
    run(sb, 0.2)
    assert not sb.anharmonic


def test_cooling_to_the_ground_state_clears_the_warning(game, monkeypatch):
    sb = game.sandbox
    monkeypatch.setattr(sandbox_mod, "ANHARMONIC_AREA", 0.5)
    run(sb, 1.2)
    assert sb.anharmonic
    sb.cool_to_ground()
    assert not sb.anharmonic


def test_a_crystal_mode_settled_in_another_well_counts_as_outside(game):
    from ion_surfer.quantum import WavePacket

    sb = game.sandbox
    wp = WavePacket(256, 800, 3800.0, x_start=200)
    # two wells along the mode, at 400 and 750
    wp.set_potential([min(0.001 * (x - 400) ** 2, 30 + 0.001 * (x - 750) ** 2) for x in wp.xs])
    wp.set_gaussian(750, 15)
    assert sb._view("COM", (0, 0, 0), wp, True, None, q_eq=400).stray
    assert not sb._view("COM", (0, 0, 0), wp, True, None, q_eq=750).stray
