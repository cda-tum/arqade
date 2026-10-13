import inspect
import re

from qircuit import match, race, sound
from qircuit.race import Cue


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


def test_one_sound_each_per_frame_and_drifting_only_for_people():
    events = [Cue("bump", "cpu1"), Cue("bump", "p1"), Cue("drift", "cpu2"), Cue("drift", "p1"),
              Cue("boost", "cpu3"), Cue("swap", "cpu1"), Cue("zeno_armed", "p1")]
    assert sound.event_sounds(events, ("p1",)) == ["bump", "drift", "swap", "zeno_armed"]
    assert sound.event_sounds([Cue("drift", "cpu1"), Cue("warn", "cpu1")], ("p1",)) == []


def test_every_cue_the_game_makes_has_a_sound():
    made = set()
    for module in (race, match):
        made |= set(re.findall(r'_?[cC]ue\("([a-z_]+)"', inspect.getsource(module)))
    assert {"reset", "lead", "tick", "copy", "go", "match_won"} <= made
    assert made - set(sound.EFFECTS) - set(sound._ALIASES) == set()


def test_loading_never_raises_even_without_a_sound_card():
    sounds = sound.load_sounds()
    sounds.play_events([Cue("beep")], ())
