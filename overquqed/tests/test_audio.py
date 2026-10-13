import pytest

from overquqed import audio
from overquqed.audio import AMP, SAMPLE_RATE, TRACKS, build_sfx, drums, mix, note_freq, render_track, tone, voice


def test_note_frequencies():
    assert note_freq("A4") == pytest.approx(440.0)
    assert note_freq("A5") == pytest.approx(880.0)
    assert note_freq("C4") == pytest.approx(261.63, abs=0.01)
    assert note_freq("A4", transpose=12) == pytest.approx(880.0)
    assert note_freq("-") == 0.0


def test_tone_length_range_and_soft_edges():
    s = tone(440, 0.1, 1.0, "square")
    assert len(s) == int(SAMPLE_RATE * 0.1)
    assert all(-AMP <= v <= AMP for v in s)
    assert abs(s[0]) < 1000 and abs(s[-1]) < 1000  # faded: no clicks


def test_zero_volume_is_silent():
    assert not any(tone(440, 0.05, 0.0))


def test_mix_pads_and_clips():
    out = mix([AMP, AMP], [AMP])
    assert out == [AMP, AMP]


def test_voice_length_matches_the_beats():
    v = voice([("C4", 1.0), ("-", 1.0)], 120, "square", 0.5)
    assert len(v) == 2 * int(SAMPLE_RATE * 0.5)


def test_drum_loop_length():
    d = drums("k.hsk.hs", 120, 2, 0.3)
    assert len(d) == 2 * 8 * int(SAMPLE_RATE * 0.25)


def test_every_track_renders_a_whole_number_of_bars_without_clipping():
    for bpm, tr, lead, _fast in TRACKS.values():
        t = render_track(bpm, tr, lead)
        seconds = len(t) / SAMPLE_RATE
        assert seconds == pytest.approx(8 * 4 * 60 / bpm, rel=0.01)
        assert max(abs(v) for v in t) <= AMP


def test_all_sfx_the_game_asks_for_exist():
    names = set(build_sfx())
    wanted = {"blip", "confirm", "nope", "pick", "put", "fridge", "flip", "stir", "whirr", "blend_done",
              "cnot", "cnot_sparkle", "sink", "bin", "serve", "refuse", "leave", "order", "siren",
              "cosmic", "swap", "timeup", "results", "back"}
    assert wanted <= names


def test_audio_falls_back_to_silence_without_a_device(monkeypatch):
    def broken():
        raise audio.pygame.error("no audio")

    monkeypatch.setattr(audio, "Audio", broken)
    a = audio.make_audio()
    a.play("serve")
    a.music("title")
    a.tempo(True)
    a.update()
