import math

import pytest

from qurves import rules, sound
from qurves.match import Cue


@pytest.fixture(scope="module")
def rendered():
    return {name: sound.render(name, 22050) for name in sound.EFFECTS}


def test_every_effect_renders_in_range_and_starts_and_ends_silent(rendered):
    for name, s in rendered.items():
        assert len(s) > 0.04 * 22050, name
        assert max(abs(v) for v in s) <= round(sound.PEAK * 32767) + 1, name
        assert s[0] == 0 and s[-1] == 0, name


def test_effects_are_as_loud_as_their_level_unless_the_peak_cap_stops_them(rendered):
    for name, s in rendered.items():
        level = sound.EFFECTS[name][1]
        got = sound.loudness([v / 32767 for v in s], 22050)
        peak = max(abs(v) for v in s) / 32767
        assert got <= level * 1.05, name
        assert got >= level * 0.95 or peak >= sound.PEAK - 0.01, name


def test_rendering_is_deterministic():
    assert sound.render("crash", 22050) == sound.render("crash", 22050)


def test_rendering_at_the_mixer_rate_resamples():
    a, b = sound.render("blip", 22050), sound.render("blip", 44100)
    assert abs(len(b) - 2 * len(a)) <= 1
    assert b[0] == 0 and b[-1] == 0


def test_a_saw_voice_plays_its_pitch():
    s = sound.voice(0.5, 441, 1.0, 9000, detune=(0,))
    rising = sum(1 for a, b in zip(s, s[1:]) if a < 0 <= b)
    assert abs(rising - 0.5 * 441) <= 3
    assert all(math.isfinite(v) for v in s)


def test_a_resonant_sweep_stays_stable():
    s = sound.voice(0.3, 110, 1.0, sound.sweep(50, 10000, 0.3), q=8.0)
    assert max(abs(v) for v in s) < 20


def test_crush_quantizes_and_holds():
    out = sound.crush([0.1, 0.3, 0.6, 0.9, -0.4, -0.8], bits=2, hold=2)
    assert out == [0.0, 0.0, 0.5, 0.5, -0.5, -0.5]


def test_sweep_and_arp_hit_their_ends():
    f = sound.sweep(400, 1600, 0.2)
    assert f(0) == 400 and f(0.1) == pytest.approx(800) and f(1.0) == pytest.approx(1600)
    a = sound.arp((69, 81), 0.05)
    assert a(0.0) == pytest.approx(440) and a(0.06) == pytest.approx(880) and a(9) == pytest.approx(880)


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
        Cue("beep"), Cue("go"), Cue("blip"), Cue("start"), Cue("ready"), Cue("pause"),
        Cue("round_won", "p1"), Cue("draw"), Cue("match_won", "p1"),
    ]
    for name in sound.event_sounds(events):
        assert name in sound.EFFECTS


def test_loading_never_raises_even_without_a_sound_card():
    sounds = sound.load_sounds()
    sounds.play_events([Cue("beep")])


def test_starting_from_the_title_and_dismissing_how_to_play_both_confirm():
    assert sound.event_sounds([Cue("start")]) == ["confirm"]
    assert sound.event_sounds([Cue("ready"), Cue("beep")]) == ["confirm", "beep"]
