import dataclasses
import random

import pytest

from qarrera import config, racers, tracks, voxels
from qarrera.ai import Driver
from qarrera.race import Race
from qarrera.track import Track


def test_every_racer_spends_the_same_budget_within_the_scale():
    for r in racers.ROSTER:
        assert sum(r.ratings) == racers.BUDGET, r.key
        assert all(1 <= v <= 5 for v in r.ratings), r.key


def test_ratings_turn_into_physics_the_right_way_round():
    by = racers.BY_KEY
    assert by["chandelier"].stats().max_speed > by["chef"].stats().max_speed
    assert by["ion"].stats().accel > by["chandelier"].stats().accel
    assert by["paddle"].stats().grip > by["cycle"].stats().grip
    assert by["rook"].stats().mass > by["photon"].stats().mass
    assert by["jelly"].stats().switch_rate > by["chandelier"].stats().switch_rate
    middle = racers.Racer("m", "M", "G", 3, 3, 3, 3, 3).stats()
    assert middle == dataclasses.replace(config.CAR, mass=1.0)


def test_every_racer_has_a_voxel_model_of_a_sensible_size():
    assert set(voxels.RACERS) == set(racers.BY_KEY)
    for key, build in voxels.RACERS.items():
        model = build()
        assert len(model) > 50, key
        assert all(-20 <= x <= 20 and -10 <= y <= 10 and 0 <= z <= 13 for x, y, z in model), key
        assert all(len(c) == 3 and all(0 <= v <= 255 for v in c) for c in model.values()), key


def test_robert_is_fast_and_light_and_grinds_the_wire_side_on():
    """Brawl-Ket's ROBERT: FAST AND LIGHT, as Brawl-Ket calls him, and in
    his own colours, standing on the wire with no car: feet apart along it,
    one ahead and one behind, arms out for balance, and his head on top."""
    robert = racers.BY_KEY["robert"]
    assert (robert.name, robert.game) == ("ROBERT", "BRAWL-KET")
    assert robert.speed == max(r.speed for r in racers.ROSTER)
    assert robert.weight == min(r.weight for r in racers.ROSTER)
    model = voxels.robert()
    assert "robert" in voxels.RIDERS and voxels.RIDERS <= set(voxels.RACERS)
    colors = set(model.values())
    assert voxels.ROBERT_BODY in colors and voxels.ROBERT_ACCENT in colors
    body = {k for k, c in model.items() if c in (voxels.ROBERT_BODY, voxels.shade(voxels.ROBERT_BODY, 0.65))}
    feet = {x for x, y, z in body if z == 0 and abs(y) <= 1}
    assert max(feet) >= 5 and min(feet) <= -5  # one foot ahead, one behind, both on the wire
    assert not any(z == 0 and -2 <= x <= 2 for x, y, z in body)  # and apart: the legs make an A
    cream = (voxels.ROBERT_ACCENT, voxels.shade(voxels.ROBERT_ACCENT, 0.8))
    fists = [x for (x, y, z), c in model.items() if z >= 7 and c in cream]
    assert max(fists) >= 9 and min(fists) <= -7  # arms out, fore and aft
    top = max(z for x, y, z in model)
    assert any(c == voxels.ROBERT_ACCENT for (x, y, z), c in model.items() if z >= top - 3)  # the visor


@pytest.mark.parametrize("track_def", tracks.ALL, ids=lambda d: d.name)
def test_alone_every_racer_laps_within_a_few_percent_of_the_others(track_def):
    """Balance: the ratings trade off, so no racer is simply faster (weight
    and handling pay off in traffic, not alone). tools/balance.py checks
    full races too."""
    track = Track(dataclasses.replace(track_def, dynamic_gates=0, items=0))
    times = {}
    for r in racers.ROSTER:
        race = Race(track, ("cpu1",), random.Random(0), stats={"cpu1": r.stats()})
        driver = Driver("cpu1", "BRUTAL", random.Random(1))
        body = race.bodies[0]
        while body.p < track.length and race.time < 120:
            race.update(1 / 30, {"cpu1": driver.controls(race, 1 / 30)})
        times[r.key] = race.time
    mean = sum(times.values()) / len(times)
    assert all(abs(t / mean - 1) < 0.03 for t in times.values()), times
