"""Headless playthroughs: bots play whole rounds on the real rules.

This checks the levels are completable end to end (every station, belts,
the two-chef press, the limited fridge and cosmic rays) and gives a rough
upper bound on scores for tuning the star thresholds.
"""

import dataclasses
import random
from collections import Counter

import pytest

from overquqed import levels
from overquqed.bot import Bot
from overquqed.world import World


def play(level, seed=1, solo=False, seconds=None):
    w = World(level, random.Random(seed), solo=solo)
    bot = Bot(w, (0,) if solo else (0, 1))
    served = Counter()
    for _ in range(int((seconds or level.duration) * 60)):
        w.update(1 / 60, bot.update(1 / 60))
        for ev in w.events:
            if ev[0] == "serve":
                served[ev[2].order.recipe.key] += 1
        w.events.clear()
    return w, served


@pytest.mark.parametrize("level", [levels.SNACK_BAR, levels.TRATTORIA, levels.COSMIC_CAFE], ids=lambda lv: lv.key)
def test_bots_complete_a_full_round_and_earn_three_stars(level):
    w, served = play(level)
    assert w.stats.delivered >= 6
    assert w.stats.left <= 2
    assert w.score >= level.stars[2], (w.score, level.stars)


def test_single_qubit_dishes_all_get_made():
    _, served = play(levels.SNACK_BAR)
    assert {"0", "1", "+", "-"} <= set(served)


def test_bell_pairs_cross_the_trattoria_belts_and_the_fridge_is_recycled():
    w, served = play(dataclasses.replace(levels.TRATTORIA, recipes=("Phi+",), guests=("alicebob",)))
    assert served["Phi+"] >= 4  # more than the 4-qubit fridge holds without the Reset Sink


@pytest.mark.parametrize("key", ["Phi+", "Phi-", "Psi+", "Psi-", "GHZ"])
def test_every_entangled_dish_is_served_in_the_cosmic_cafe(key):
    guest = "shor" if key == "GHZ" else "knill"
    lv = dataclasses.replace(levels.COSMIC_CAFE, recipes=(key,), guests=(guest,), cosmic_rays=False)
    w, served = play(lv, seconds=70)
    assert served[key] >= 2
    assert w.stats.refused == 0


def test_a_solo_bot_can_run_the_two_chef_press_at_half_speed():
    lv = dataclasses.replace(levels.COSMIC_CAFE, recipes=("Phi+",), guests=("alicebob",), cosmic_rays=False)
    _, served = play(lv, solo=True, seconds=70)
    assert served["Phi+"] >= 2
