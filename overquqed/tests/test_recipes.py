import pytest

from overquqed.recipes import RECIPES, TIER_POINTS, run_circuit


@pytest.mark.parametrize("key", list(RECIPES))
def test_every_hint_circuit_makes_its_target(key):
    recipe = RECIPES[key]
    state = run_circuit(recipe.hint, recipe.n)
    assert state.fidelity(recipe.target) == pytest.approx(1.0)


@pytest.mark.parametrize("key", list(RECIPES))
def test_every_target_is_labelled_by_its_own_name(key):
    recipe = RECIPES[key]
    assert run_circuit(recipe.hint, recipe.n).label() == ((key,), "")


def test_tiers_have_points():
    assert {r.tier for r in RECIPES.values()} <= set(TIER_POINTS)


def test_hint_circuits_only_use_v1_stations():
    for recipe in RECIPES.values():
        for op in recipe.hint:
            assert op[0] in {"X", "Z", "H", "CNOT"}
