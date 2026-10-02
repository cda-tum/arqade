"""The contract every microgame and boss must keep (see microgames/base.py).
Each registered one is checked the same way, at level 0 and level 3."""

import hashlib
import random

import pygame
import pytest

from planck_time import config
from planck_time.microgames import BOSSES, REGISTRY, PlayerInput
from planck_time.microgames.base import INPUTS
from planck_time.pixel import font

LEVELS = (0, 3)
SEEDS = range(20)
DT = 1 / 60


def simulate(game, policy):
    """Run a microgame the way the session does: up to its duration, stopping
    early on a failure, then timeout() if it's still unresolved."""
    frames = round(game.duration / DT)
    for _ in range(frames):
        game.update(DT, policy(game))
        if game.result is False:
            break
    if game.result is None:
        game.timeout()
    return game.result


ALL = REGISTRY + BOSSES


def ids(cls):
    return cls.__name__


def test_there_are_microgames_and_a_boss():
    assert len(REGISTRY) >= 2
    assert BOSSES and all(b.BOSS for b in BOSSES) and not any(m.BOSS for m in REGISTRY)


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("cls", ALL, ids=ids)
def test_the_bot_always_wins(cls, level):
    for seed in SEEDS:
        game = cls(seed, level, cls.duration_for(level))
        assert simulate(game, lambda g: g.bot()) is True, f"seed {seed}"


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("cls", ALL, ids=ids)
def test_doing_nothing_always_loses(cls, level):
    for seed in SEEDS:
        game = cls(seed, level, cls.duration_for(level))
        assert simulate(game, lambda g: PlayerInput()) is False, f"seed {seed}"


def random_policy(seed):
    rng = random.Random(seed)

    def policy(_game):
        return PlayerInput(stick=(rng.uniform(-1, 1), rng.uniform(-1, 1)),
                           step=(rng.choice((-1, 0, 0, 1)), rng.choice((-1, 0, 0, 1))),
                           a=rng.random() < 0.1, a_held=rng.random() < 0.3)
    return policy


@pytest.mark.parametrize("cls", ALL, ids=ids)
def test_the_same_seed_gives_the_same_game(cls):
    for seed in range(5):
        a, b = cls(seed, 2, cls.duration_for(2)), cls(seed, 2, cls.duration_for(2))
        simulate(a, random_policy(seed))
        simulate(b, random_policy(seed))
        assert (a.result, a.won_at, a.ended_at) == (b.result, b.won_at, b.ended_at)


@pytest.mark.parametrize("cls", ALL, ids=ids)
def test_drawing_works_throughout_a_game(cls):
    pygame.init()
    surf = pygame.Surface((config.SCREEN_W, config.SCREEN_H))
    for seed, policy in ((0, lambda g: g.bot()), (1, lambda g: PlayerInput())):
        game = cls(seed, 1, cls.duration_for(1))
        for frame in range(round(game.duration / DT) + 60):
            game.update(DT, policy(game))
            if frame % 15 == 0:
                game.draw(surf)
        if game.result is None:
            game.timeout()
        game.draw(surf)


def _glyph_hash(ch):
    img = font(8).render(ch, False, (255, 255, 255), (0, 0, 0))
    return hashlib.md5(pygame.image.tobytes(img, "RGB")).hexdigest()


@pytest.mark.parametrize("cls", ALL, ids=ids)
def test_the_metadata(cls):
    pygame.init()
    assert cls.VERB.endswith("!") and cls.VERB.isupper()
    assert cls.INPUT in INPUTS
    assert 0 < len(cls.CAPTION) <= 64
    missing = _glyph_hash("⟩")  # known missing from Press Start 2P
    names = (cls.BOSS_NAME + cls.BOSS_TITLE) if cls.BOSS else ""
    assert names.isupper() or not names
    for ch in set(cls.VERB + cls.CAPTION + names) - {" "}:
        assert _glyph_hash(ch) != missing, f"{ch!r} isn't in the font"
