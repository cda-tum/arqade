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


class FakeSound:
    def __init__(self, log=None, name=""):
        self.log, self.name, self.volume = log if log is not None else [], name, 1.0

    def set_volume(self, v):
        self.volume = v

    def play(self, loops=0):
        self.log.append((self.name, self.volume))


class FakeChannel:
    def __init__(self):
        self.sound, self.loops, self.volume, self.log = None, None, (1.0, 1.0), []

    def play(self, snd, loops=0):
        self.sound, self.loops = snd, loops
        self.log.append(("play", snd, loops))

    def stop(self):
        self.sound = None
        self.log.append(("stop",))

    def set_volume(self, left, right=None):
        self.volume = (left, left if right is None else right)


# ---------- landing on the wave ----------

def test_impact_gain_is_silent_below_the_threshold_and_faint_just_above():
    assert sound.impact_gain(0) == 0
    assert sound.impact_gain(sound.IMPACT_MIN - 1) == 0
    assert 0 < sound.impact_gain(sound.IMPACT_MIN) <= 0.1
    # the old fixed sound played from 320 px/s at 0.28 peak; now that is
    # more than 12 dB quieter
    assert sound.impact_gain(320) * sound.IMPACT_PEAK < 0.28 / 4


def test_impact_gain_rises_monotonically_and_is_capped():
    speeds = range(int(sound.IMPACT_MIN), 3000, 10)
    gains = [sound.impact_gain(v) for v in speeds]
    assert all(b >= a for a, b in zip(gains, gains[1:]))
    assert gains[-1] == sound.impact_gain(sound.IMPACT_FULL) == 1.0
    assert sound.impact_gain(1e9) == 1.0
    # small bumps barely audible, a mid-sized landing in between
    assert sound.impact_gain(300) < 0.15 < sound.impact_gain(650) < 0.6


def test_harder_landings_sound_brighter():
    order = ["bounce_soft", "bounce", "bounce_hard"]
    picks = [order.index(sound.impact_effect(v)) for v in range(200, 2000, 25)]
    assert picks == sorted(picks) and picks[0] == 0 and picks[-1] == 2
    assert all(sound.EFFECTS[name][1] == sound.IMPACT_PEAK for name in order)


def impact_sounds(monkeypatch):
    log = []
    now = [1000]
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: now[0])
    fx = {n: FakeSound(log, n) for n in ("bounce_soft", "bounce", "bounce_hard")}
    return sound.Sounds(fx), log, now


def test_impact_sets_the_volume_on_the_sound_itself(monkeypatch):
    # the attract capture logs a play with Sound.get_volume()
    s, log, now = impact_sounds(monkeypatch)
    s.impact(250)
    now[0] += 1000
    s.impact(1500)
    assert log == [("bounce_soft", sound.impact_gain(250)), ("bounce_hard", 1.0)]
    s.impact(100)  # rolling: silent
    assert len(log) == 2


def test_soft_contact_does_not_machine_gun(monkeypatch):
    s, log, now = impact_sounds(monkeypatch)
    # a curve pushed up under the ion: an "impact" every 240 Hz physics step
    for _ in range(240):
        s.impact(420)
        now[0] += 4
    assert len(log) <= 1000 / sound.IMPACT_GAP_MS + 1


def test_a_much_harder_landing_cuts_through_the_gap(monkeypatch):
    s, log, now = impact_sounds(monkeypatch)
    s.impact(300)
    now[0] += 20
    s.impact(320)            # about as soft: suppressed
    assert len(log) == 1
    s.impact(1000)           # a real crash right after: plays
    assert len(log) == 2 and log[-1][0] == "bounce_hard"


def test_silent_sounds_have_impact_and_ambience_too():
    sound.Sounds().impact(900)
    sound.Sounds().ambient([("beam_up", 1, 100.0, 1.0)], 1 / 60)


def test_electrode_is_still_rate_limited(monkeypatch):
    plays = []

    class Fx:
        def play(self):
            plays.append(1)

    now = [1000]
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: now[0])
    s = sound.Sounds({"electrode": Fx()})
    s.play("electrode")
    s.play("electrode")
    now[0] += 50
    s.play("electrode")
    assert len(plays) == 2


# ---------- ambience ----------

def test_stereo_is_equal_power_and_pans_the_right_way():
    left, right = sound.stereo(-1)
    assert left == 1 and abs(right) < 1e-9
    left, right = sound.stereo(1)
    assert abs(left) < 1e-9 and right == 1
    for p in (-1, -0.5, 0, 0.3, 1):
        left, right = sound.stereo(p)
        assert abs(left * left + right * right - 1) < 1e-9
    pans = [sound.stereo(p / 10) for p in range(-10, 11)]
    assert all(b[0] <= a[0] and b[1] >= a[1] for a, b in zip(pans, pans[1:]))


def test_pan_follows_the_screen_x_and_never_goes_fully_to_one_side():
    w = 1200
    assert sound.pan(w / 2, w) == 0
    assert sound.pan(0, w) == -sound.AMBIENT_WIDTH
    assert sound.pan(w, w) == sound.AMBIENT_WIDTH
    assert sound.pan(-500, w) == -sound.AMBIENT_WIDTH
    assert sound.pan(300, w) < 0 < sound.pan(900, w)
    left, right = sound.stereo(sound.pan(0, w))
    assert left > right > 0.1


def test_sources_fade_out_off_screen():
    w = 1200
    assert sound.presence(0, w) == sound.presence(w, w) == sound.presence(w / 2, w) == 1
    assert sound.presence(-sound.AMBIENT_MARGIN, w) == 0
    assert sound.presence(w + sound.AMBIENT_MARGIN + 50, w) == 0
    assert 0 < sound.presence(w + sound.AMBIENT_MARGIN / 2, w) < 1


def test_nearer_is_louder_but_far_is_not_silent():
    assert sound.nearness(0, 300) == 1 and sound.nearness(300, 300) == 0
    assert sound.nearness(float("inf"), 300) == 0
    levels = [sound.ambient_level(sound.nearness(d, 300)) for d in range(0, 400, 20)]
    assert all(b <= a for a, b in zip(levels, levels[1:]))
    assert levels[0] == 1 and levels[-1] == sound.AMBIENT_BASE > 0


def test_loop_targets_pan_and_cap():
    w = 1200
    t = sound.loop_targets([("beam_up", 1, 100.0, 0.0)], w)
    left, right = t["beam_up"]
    assert left > right > 0
    assert t["beam_down"] == (0.0, 0.0)
    t = sound.loop_targets([("beam_down", 1, 1100.0, 1.0)], w)
    assert t["beam_down"][1] > t["beam_down"][0]
    many = [("beam_up", k, 1200.0, 1.0) for k in range(10)]
    assert max(sound.loop_targets(many, w)["beam_up"]) == 1.0


def test_ambient_peaks_stay_under_every_effect():
    quietest = min(v for _, v in sound.EFFECTS.values())
    for name, (build, peak) in sound.AMBIENT_SOUNDS.items():
        assert peak < quietest, name
        assert 0 < len(build(8000)) <= 2 * 8000, name


def test_hum_loops_are_seamless():
    sr = 8000
    for name in sound.AMBIENT_LOOPS:
        s = sound.AMBIENT_SOUNDS[name][0](sr)
        steps = [abs(b - a) for a, b in zip(s, s[1:])]
        # the jump from the last sample back to the first is no bigger
        # than an ordinary step
        assert abs(s[0] - s[-1]) <= 1.05 * max(steps), name


def make_ambience():
    chans = {k: FakeChannel() for k in sound.AMBIENT_LOOPS + sound.AMBIENT_TICKS}
    snds = {k: FakeSound(name=k) for k in chans}
    return sound.Ambience(snds, chans, 1200), chans


def test_a_hum_swells_in_softly_and_stops_once_faded_out():
    amb, chans = make_ambience()
    up = chans["beam_up"]
    src = [("beam_up", 1, 200.0, 1.0)]
    amb.update(src, 1 / 60)
    assert up.loops == -1 and max(up.volume) < 0.05      # soft attack
    for _ in range(120):
        amb.update(src, 1 / 60)
    left, right = up.volume
    assert left > right                                   # panned to the beam, left of centre
    assert abs(max(up.volume) - max(sound.loop_targets(src, 1200)["beam_up"])) < 1e-9
    assert chans["beam_down"].sound is None               # nothing played on the other hum
    for _ in range(60):
        amb.update([], 1 / 60)
    assert up.sound is None and up.log[-1] == ("stop",)


def test_strays_ping_now_and_then_panned_and_faster_when_near():
    def pings(near, x=1000.0, seconds=6.0):
        amb, chans = make_ambience()
        for _ in range(int(seconds * 60)):
            amb.update([("stray", 7, x, near)], 1 / 60)
        return chans["stray"]

    far, close = pings(0.0), pings(1.0)
    assert 3 <= len(far.log) < len(close.log) <= 6.0 / sound.STRAY_EVERY[1] + 1
    assert all(entry[2] == 0 for entry in close.log)      # one-shots, never looped
    left, right = close.volume
    assert right > left                                   # x=1000: right of centre
    assert max(far.volume) < max(close.volume)


def test_ambience_survives_a_capture_style_sound_log(monkeypatch):
    """batocera/attract/capture.py swaps pygame.mixer.Sound for a subclass
    that logs Sound.play(loops=0) with the Sound's own volume. Landings must
    log their volume, and the hums (Channel.play, looping) must not be
    logged or break anything."""
    pygame.init()
    try:
        if not pygame.mixer.get_init():
            return  # no mixer at all here: the silent fallback is tested above
        events = []

        class LoggedSound(pygame.mixer.Sound):
            def play(self, loops=0, *args, **kwargs):
                if loops == 0:
                    events.append(self.get_volume())
                return super().play(loops, *args, **kwargs)

        monkeypatch.setattr(pygame.mixer, "Sound", LoggedSound)
        s = sound.load_sounds()
        assert s._ambience is not None
        assert pygame.mixer.get_num_channels() >= sound.TOTAL_CHANNELS
        src = [("beam_up", 1, 300.0, 1.0), ("beam_down", 2, 900.0, 0.2), ("stray", 3, 600.0, 0.5)]
        for _ in range(90):
            s.ambient(src, 1 / 60)
        assert events == []
        now = [10_000]
        monkeypatch.setattr(pygame.time, "get_ticks", lambda: now[0])
        s.impact(300)
        now[0] += 500
        s.impact(1200)
        assert len(events) == 2 and events[0] < 0.2 and events[1] == 1.0
        s.ambient([], 1.0)
    finally:
        pygame.quit()
