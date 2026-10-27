import inspect
import random
import re

import numpy as np
import pytest

from qarrera import config, match, race, sound
from qarrera.race import Cue, Race
from qarrera.track import Track, TrackDef


def test_sweep_samples_have_the_right_length_and_range():
    s = sound.sweep_samples(300, 900, 0.1, 22050, 0.5)
    assert len(s) == 2205
    assert max(abs(v) for v in s) <= 32767
    assert any(s)


def test_sweeps_start_and_end_silent():
    s = sound.sweep_samples(300, 900, 0.1, 22050, 0.5, noise=0.5)
    assert s[0] == 0 and s[-1] == 0


def test_a_multi_step_effect_plays_its_steps_in_a_row():
    steps = sound.EFFECTS["match_won"]
    assert len(sound.effect_samples("match_won", 22050)) == sum(round(22050 * d) for _, _, d, _ in steps)


def test_one_sound_each_per_frame_and_warnings_only_for_people():
    events = [Cue("bump", "cpu1"), Cue("bump", "p1"), Cue("warn", "cpu2"), Cue("warn", "p1"),
              Cue("boost", "cpu3"), Cue("copy", "cpu1"), Cue("zeno_armed", "p1")]
    assert sound.event_sounds(events, ("p1",)) == ["bump", "warn", "copy", "zeno_armed"]
    assert sound.event_sounds([Cue("warn", "cpu1"), Cue("boost", "cpu1")], ("p1",)) == []


def test_a_swap_is_silent_and_drifting_is_no_one_shot():
    assert sound.event_sounds([Cue("swap", "p1"), Cue("drift", "p1")], ("p1",)) == []


def test_every_cue_the_game_makes_has_a_sound_or_is_silent_on_purpose():
    made = set()
    for module in (race, match):
        made |= set(re.findall(r'_?[cC]ue\("([a-z_]+)"', inspect.getsource(module)))
    assert {"reset", "lead", "tick", "copy", "go", "match_won", "swap", "drift"} <= made
    assert made - set(sound.EFFECTS) - set(sound._ALIASES) - sound.SILENT == set()


def peak(samples) -> int:
    return max(abs(v) for v in samples)


def test_pickups_are_soft_low_and_well_under_the_loud_effects():
    loud = peak(sound.effect_samples("boost", 22050))
    for name in sound.SOFT:
        samples = sound.effect_samples(name, 22050)
        assert peak(samples) < 0.4 * loud, name
        assert max(max(f0, f1) for f0, f1, _, _ in sound.EFFECTS[name]) < 1000, name  # nothing bright
        assert all(noise == 0 for *_, noise in sound.EFFECTS[name]), name
        assert peak(samples[:len(samples) // 10]) < 0.3 * peak(samples), name  # it swells in


# --- the drift loop -------------------------------------------------------------------------------

def drifting_race() -> Race:
    track = Track(TrackDef("OVAL", (120.0, 80.0), 0.0,
                           (("S", 400.0), ("A", 100.0, 180), ("S", 400.0), ("A", 100.0, 180)), 0.0))
    return Race(track, ("p1", "cpu1"), random.Random(0), humans=("p1",))


def test_only_a_persons_drift_squeals_louder_the_harder_it_slides():
    r = drifting_race()
    me, bot = r.bodies_of("p1")[0], r.bodies_of("cpu1")[0]
    bot.load = config.WARN_LOAD
    assert sound.drift_target(r, ("p1",)) == 0  # a bot sliding: nothing
    me.load = config.DRIFT_LOAD * 0.99
    assert sound.drift_target(r, ("p1",)) == 0  # under the limit: nothing
    me.load = config.DRIFT_LOAD + 0.05
    light = sound.drift_target(r, ("p1",))
    me.load = config.WARN_LOAD + 0.5
    hard = sound.drift_target(r, ("p1",))
    assert sound.DRIFT_QUIET <= light < hard == 1.0
    me.air = True
    assert sound.drift_target(r, ("p1",)) == 0  # flying: no tyres on the track
    me.air, me.spin = False, 0.3
    assert sound.drift_target(r, ("p1",)) == 0  # spun out: the spin's own sound


def test_a_real_drift_in_a_race_squeals_for_people_and_not_for_bots():
    r = drifting_race()
    for b, lane in zip(r.bodies, (1, 2)):
        b.p = b.reach = 340.0
        b.lane, b.u, b.v, b.cruise = lane, float(lane), 220.0, 1.0
    heard = {"p1": 0.0, "cpu1": 0.0}
    for _ in range(40):
        r.update(1 / 60, {})
        heard["p1"] = max(heard["p1"], sound.drift_target(r, ("p1",)))
        heard["cpu1"] = max(heard["cpu1"], sound.drift_target(r, ("cpu1",)))
    assert heard["p1"] > 0 and heard["cpu1"] > 0  # both slide: the squeal follows whoever is a person
    assert sound.drift_target(r, ()) == 0


def test_the_squeal_fades_in_and_out_rather_than_switching():
    voice = sound.DriftVoice()
    dt = 1 / 60
    assert 0 < voice.step(1.0, dt) < 0.5
    for _ in range(round(sound.DRIFT_IN / dt) + 1):
        voice.step(1.0, dt)
    assert voice.level == 1.0
    assert 0.5 < voice.step(0.0, dt) < 1.0
    for _ in range(round(sound.DRIFT_OUT / dt) + 1):
        voice.step(0.0, dt)
    assert voice.level == 0.0
    assert sound.DRIFT_OUT > sound.DRIFT_IN  # it dies away more slowly than it comes


def test_the_drift_loop_is_seamless_soft_and_not_bright():
    s = sound.drift_loop_samples(22050).astype(float)
    assert len(s) == round(22050 * sound.DRIFT_LOOP)
    assert np.abs(s).max() == pytest.approx(sound.DRIFT_VOLUME * 32767, rel=0.01)
    assert abs(s[0] - s[-1]) <= np.abs(np.diff(s)).max()  # the wrap is no bigger a step than any other
    spectrum = np.abs(np.fft.rfft(s)) ** 2
    f = np.fft.rfftfreq(len(s), 1 / 22050)
    assert (spectrum * f).sum() / spectrum.sum() < 2000  # its centre of mass well under the old 4 kHz hiss
    loud = max(peak(sound.effect_samples(n, 22050)) for n in ("boost", "zeno"))
    assert np.abs(s).max() < 0.5 * loud  # even at its loudest, well under the loud effects


def test_loading_never_raises_even_without_a_sound_card():
    sounds = sound.load_sounds()
    sounds.play_events([Cue("beep")], ())
    r = drifting_race()
    r.bodies[0].load = config.WARN_LOAD
    for _ in range(3):
        sounds.update_drift(r, ("p1",), 1 / 60)
    sounds.update_drift(None, ("p1",), 1 / 60)
