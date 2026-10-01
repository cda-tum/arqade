from qurves import rules, sound
from qurves.match import Cue


def test_sweep_samples_have_the_right_length_and_range():
    s = sound.sweep_samples(300, 900, 0.1, 22050, 0.5)
    assert len(s) == 2205
    assert max(abs(v) for v in s) <= 32767
    assert any(s)


def test_sweeps_start_and_end_silent():
    s = sound.sweep_samples(300, 900, 0.1, 22050, 0.5, noise=0.5)
    assert s[0] == 0 and s[-1] == 0


def test_noise_is_deterministic():
    a = sound.sweep_samples(200, 50, 0.05, 22050, 0.6, noise=0.8)
    b = sound.sweep_samples(200, 50, 0.05, 22050, 0.6, noise=0.8)
    assert a == b


def test_events_map_to_one_sound_each_per_frame():
    events = [
        rules.Split("p1", (1, 1)),
        rules.Crash("p2", (2, 2), None),
        rules.Crash("p1", (3, 3), 0),
        rules.Collapse("p1", "crash", ((4, 4),), (), ()),
        rules.Moved("p1", None, (1, 1), (2, 1)),
        Cue("go"),
    ]
    assert sound.event_sounds(events) == ["split", "crash", "go"]


def test_every_sound_an_event_can_ask_for_exists():
    events = [
        rules.Split("p1", (1, 1)), rules.Crash("p1", (1, 1), None),
        rules.Collapse("p1", "decoherence", ((1, 1),), (), ()),
        rules.Measured("p1", "p2", (1, 1)), rules.PickedUp("p1", "H", (1, 1)),
        rules.PickedUp("p1", "Z", (1, 1)), rules.Teleported("p1", (1, 1), (9, 1)),
        Cue("beep"), Cue("go"), Cue("blip"), Cue("round_won", "p1"), Cue("draw"), Cue("match_won", "p1"),
    ]
    for name in sound.event_sounds(events):
        assert name in sound.EFFECTS


def test_loading_never_raises_even_without_a_sound_card():
    sounds = sound.load_sounds()
    sounds.play_events([Cue("beep")])
