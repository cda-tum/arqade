"""The synthesized sound effects: pure sample builders, and silence without a mixer."""

import os

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from ion_surfer import sound  # noqa: E402


def test_pluck_rings_at_its_pitch_and_dies_away():
    sr = 22050
    s = sound.pluck(441.0, 1.0, sr)
    assert len(s) == sr
    period = round(sr / 441.0)
    late = s[sr // 2: sr // 2 + 4 * period]
    # periodic: one period later looks almost the same
    assert max(abs(a - b) for a, b in zip(late, late[period:])) < 0.1
    assert max(map(abs, s[-500:])) < max(map(abs, s[:500]))


def test_to_pcm_scales_the_peak_and_fades_the_ends():
    pcm = sound.to_pcm([0.5] * 1000, 0.5)
    assert max(pcm) == round(0.5 * 32767)
    assert pcm[0] == 0 and pcm[-1] == 0


def test_echo_appends_fading_repeats():
    out = sound.echo([1.0] + [0.0] * 9, 100, delay=0.05, feedback=0.5, taps=2)
    assert len(out) == 20
    assert out[5] == 0.5 and out[10] == 0.25


def test_every_effect_builds_and_stays_short():
    for name, (build, volume) in sound.EFFECTS.items():
        samples = build(8000)
        assert 0 < len(samples) <= 2 * 8000, name
        assert 0 < volume <= 0.5, name


def test_silent_sounds_never_fail():
    sound.Sounds().play("photon")
    sound.Sounds().play("no such sound")


def test_load_sounds_works_on_the_dummy_driver_or_falls_back(monkeypatch):
    pygame.init()
    try:
        s = sound.load_sounds()
        s.play("confirm")
        s.play("bounce")
    finally:
        pygame.quit()

    def broken(*args, **kwargs):
        raise pygame.error("no audio device")

    monkeypatch.setattr(pygame.mixer, "get_init", lambda: None)
    monkeypatch.setattr(pygame.mixer, "init", broken)
    assert sound.load_sounds()._sounds == {}


def test_bounce_is_rate_limited(monkeypatch):
    plays = []

    class Fx:
        def play(self):
            plays.append(1)

    now = [1000]
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: now[0])
    s = sound.Sounds({"bounce": Fx()})
    s.play("bounce")
    s.play("bounce")
    now[0] += 200
    s.play("bounce")
    assert len(plays) == 2
