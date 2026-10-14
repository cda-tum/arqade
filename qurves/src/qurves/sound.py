"""Tron-style synthesized sound effects. No audio assets, no numpy.

Every effect is built at start-up by a tiny subtractive synth in pure Python:
sawtooth (band-limited with polyBLEP) or raw pulse oscillators in detuned
unison, through a resonant low-pass filter (a TPT state-variable filter)
whose cutoff sweeps, plus a bit crusher for the derez. Pitch, cutoff and
volume are functions of time, evaluated every _BLOCK samples (volume is
ramped per sample, so there are no clicks).

Effects are synthesized at SYNTH_RATE whatever the mixer runs at, then
resampled, which keeps start-up cheap on the Pi. Each is soft-saturated and
normalized to its EFFECTS level, matched to the older sine effects so the
loudness balance between sounds did not change.

render() is pure and unit tested. Building pygame Sounds needs a real mixer;
without one (no sound card), every effect is a silent no-op, so a cabinet
running unattended never crashes over audio. There is deliberately no
engine hum: a loop under every round would drone on a public cabinet, and
the resonant hum lives in the GO, round and match stabs instead.
"""

from __future__ import annotations

import array
import math
import random

import pygame

from qurves import rules
from qurves.match import Cue

SYNTH_RATE = 22050
_BLOCK = 32  # samples between pitch/cutoff/volume updates
PEAK = 0.55  # no effect peaks above this fraction of full scale
DRIVE = 1.8  # default tanh saturation on an effect's output (1 is barely any)


def hz(note: float) -> float:
    """The frequency of a MIDI note number (69 = A4 = 440 Hz)."""
    return 440.0 * 2 ** ((note - 69) / 12)


# --- envelopes and sweeps: functions of t in seconds ---------------------

def sweep(a: float, b: float, duration: float):
    """Exponential glide from a to b over duration, then holding b."""
    return lambda t: a * (b / a) ** min(1.0, t / duration)


def decay(tau: float, attack: float = 0.002):
    """A linear attack, then an exponential decay with time constant tau."""
    return lambda t: min(1.0, t / attack) * math.exp(-t / tau)


def arp(notes: tuple, step: float):
    """An arpeggio: each MIDI note for `step` seconds, holding the last."""
    freqs = [hz(n) for n in notes]
    return lambda t: freqs[min(len(freqs) - 1, int(t / step))]


def retrig(step: float, tau: float, count: int, tail: float | None = None):
    """A plucked envelope restarting every step for `count` notes; the last
    note decays with `tail` (default tau)."""
    last = (count - 1) * step
    tail = tail or tau

    def env(t: float) -> float:
        if t >= last:
            t, k = t - last, tail
        else:
            t, k = t % step, tau
        return min(1.0, t / 0.0015) * math.exp(-t / k)
    return env


# --- the synth -----------------------------------------------------------

def _fn(v):
    return v if callable(v) else (lambda t, v=v: v)


def voice(
    duration: float, pitch, amp, cutoff, *, shape: str = "saw", detune: tuple = (0.0,),
    width: float = 0.5, q: float = 0.7, sub: float = 0.0, noise: float = 0.0, seed: int = 1,
    sr: int = SYNTH_RATE,
) -> list[float]:
    """One synth voice as floats around -1..1: unison oscillators `detune`
    cents apart ("saw", or a raw "pulse" of `width`), an optional square sub
    an octave down and white noise, through a resonant low-pass (q is its
    resonance; 0.7 is flat). pitch, amp and cutoff are numbers or functions
    of t. No detune entries means noise only."""
    n = max(1, round(duration * sr))
    pitch, amp, cutoff = _fn(pitch), _fn(amp), _fn(cutoff)
    ratios = [2 ** (c / 1200) for c in detune]
    voices = range(len(ratios))
    norm = 1.0 / len(ratios) if ratios else 0.0
    rng = random.Random(seed)
    phases = [rng.random() for _ in ratios]  # free-running, like an analog unison
    saw = shape == "saw"
    sub_phase = 0.0
    k = 1.0 / q
    ic1 = ic2 = 0.0
    top = 0.45 * sr
    out = [0.0] * n
    a = amp(0.0)
    for start in range(0, n, _BLOCK):
        end = min(n, start + _BLOCK)
        f = min(top, pitch(start / sr))
        incs = [f * r / sr for r in ratios]
        sub_inc = f / (2 * sr)
        g = math.tan(math.pi * min(top, max(20.0, cutoff(start / sr))) / sr)
        a1 = 1.0 / (1.0 + g * (g + k))
        a2 = g * a1
        a3 = g * a2
        da = (amp(end / sr) - a) / (end - start)
        for i in range(start, end):
            x = 0.0
            for j in voices:
                dt = incs[j]
                p = phases[j] + dt
                if p >= 1.0:
                    p -= 1.0
                phases[j] = p
                if saw:
                    y = p + p - 1.0
                    if p < dt:  # polyBLEP: round off the reset, no aliasing hiss
                        u = p / dt
                        y -= u + u - u * u - 1.0
                    elif p > 1.0 - dt:
                        u = (p - 1.0) / dt
                        y -= u * u + u + u + 1.0
                    x += y
                else:
                    x += 1.0 if p < width else -1.0
            x *= norm
            if sub:
                sub_phase += sub_inc
                if sub_phase >= 1.0:
                    sub_phase -= 1.0
                x += sub if sub_phase < 0.5 else -sub
            if noise:
                x += noise * (rng.random() * 2.0 - 1.0)
            v3 = x - ic2
            v1 = a1 * ic1 + a2 * v3
            v2 = ic2 + a2 * ic1 + a3 * v3
            ic1 = v1 + v1 - ic1
            ic2 = v2 + v2 - ic2
            out[i] = v2 * a
            a += da
    return out


def crush(xs: list[float], bits, hold, sr: int = SYNTH_RATE) -> list[float]:
    """Bit crusher: quantize to `bits` and hold every sample for `hold`
    samples (a lower sample rate). Both may be functions of t."""
    bits, hold = _fn(bits), _fn(hold)
    out = [0.0] * len(xs)
    held = 0.0
    count = 0
    for start in range(0, len(xs), _BLOCK):
        step = 2.0 / 2 ** bits(start / sr)
        h = max(1, round(hold(start / sr)))
        for i in range(start, min(len(xs), start + _BLOCK)):
            if count <= 0:
                held = round(xs[i] / step) * step
                count = h
            count -= 1
            out[i] = held
    return out


def mix(dst: list[float], src: list[float], at: float = 0.0, gain: float = 1.0,
        sr: int = SYNTH_RATE) -> list[float]:
    """Add src into dst from `at` seconds on, growing dst as needed."""
    o = round(at * sr)
    if len(dst) < o + len(src):
        dst.extend([0.0] * (o + len(src) - len(dst)))
    for i, v in enumerate(src):
        dst[o + i] += gain * v
    return dst


# --- the effects (each returns floats at SYNTH_RATE) ----------------------

def _blip() -> list[float]:
    # menu move: a tiny pulse-wave tick, its filter snapping shut
    return voice(0.045, hz(81), decay(0.018, 0.001), sweep(7000, 1500, 0.045),
                 shape="pulse", width=0.25, q=1.2)


def _beep() -> list[float]:
    # countdown 3-2-1 (and pause): a plucked E stab, resonant filter chirping down
    return voice(0.13, hz(76), decay(0.05), sweep(5000, 450, 0.12), detune=(-8, 0, 8), q=2.5, sub=0.5)


def _go() -> list[float]:
    # GO: a B power-chord stab whose filter blooms open, over a resonant bass hum
    def cut(t: float) -> float:
        return 900 + 6500 * t / 0.025 if t < 0.025 else 1100 + 6300 * math.exp(-(t - 0.025) / 0.1)
    out: list[float] = []
    for note in (71, 78, 83):
        mix(out, voice(0.4, hz(note), decay(0.2, 0.003), cut, detune=(-9, 9), q=1.8, seed=note), gain=0.5)
    return mix(out, voice(0.4, hz(47), decay(0.22, 0.01), 380, detune=(-6, 6), q=5.0, seed=2), gain=0.25)


def _confirm() -> list[float]:
    # start / HOW TO PLAY dismissed: an octave-up two-note stab
    return voice(0.14, arp((76, 88), 0.055), retrig(0.055, 0.04, 2), sweep(6500, 1800, 0.14),
                 detune=(-7, 7), q=1.5)


def _pickup() -> list[float]:
    # any gate: a bright four-note arpeggio zap up to E7
    return voice(0.08, arp((88, 91, 95, 100), 0.016), retrig(0.016, 0.02, 4, 0.025), 9000,
                 detune=(-10, 10), q=0.9)


def _split() -> list[float]:
    # H: the bike forks, so one arpeggio climbs while its mirror falls
    step = 0.03
    cut = sweep(2500, 9000, 0.12)
    out = voice(0.2, arp((76, 83, 88, 95, 100), step), retrig(step, 0.03, 5, 0.06), cut,
                detune=(-8, 8), q=1.4, seed=3)
    return mix(out, voice(0.2, arp((76, 71, 64, 59, 52), step), retrig(step, 0.03, 5, 0.06), cut,
                          detune=(-8, 8), q=1.4, seed=4), gain=0.8)


def _teleport() -> list[float]:
    # X: a pulse laser zipping up through a resonant filter, with one digital echo
    zap = voice(0.14, sweep(400, 2200, 0.13), decay(0.08), sweep(1200, 7000, 0.13),
                shape="pulse", width=0.3, q=4.0)
    return mix(list(zap), zap, 0.055, 0.35)


def _shield() -> list[float]:
    # Z: an A power chord charging up, a high-resonance filter sweeping open
    out: list[float] = []
    for note in (69, 76):
        mix(out, voice(0.26, hz(note), decay(0.2, 0.01), sweep(250, 7000, 0.2),
                       detune=(-12, 0, 12), q=6.0, seed=note), gain=0.6)
    return out


def _collapse() -> list[float]:
    # superposition collapses: a wide, beating unison sliding down, slightly crushed
    body = voice(0.26, sweep(900, 200, 0.26), decay(0.12, 0.004), sweep(5000, 300, 0.26),
                 detune=(-25, 0, 25), q=3.0, seed=5)
    return crush(body, 7, 2)


def _measure() -> list[float]:
    # measured: a glitchy pulse zap down through a resonant filter, sample-held
    zap = voice(0.1, sweep(1800, 500, 0.1), decay(0.05), sweep(6000, 900, 0.1),
                shape="pulse", noise=0.35, q=3.0, seed=6)
    return crush(zap, 6, 3)


def _crash() -> list[float]:
    """Derez: a noise-and-thump impact, then a detuned saw diving to 30 Hz
    while its filter closes and a bit crusher eats it (8 down to 4 bits,
    the sample rate falling to 1/8), and bright pulse shards that scatter
    early, each lower than the last."""
    d = 0.5
    out = voice(0.25, 1, decay(0.04, 0.001), sweep(9000, 300, 0.2), detune=(), noise=1.0, seed=7)
    mix(out, voice(0.3, sweep(160, 40, 0.25), decay(0.08, 0.001), 900, shape="pulse", q=1.0), gain=0.7)
    body = voice(d, sweep(520, 30, 0.42), decay(0.18, 0.002), sweep(7000, 150, 0.4),
                 detune=(-15, 0, 15), q=3.0, seed=8)
    mix(out, crush(body, lambda t: 8 - 4 * min(1.0, t / d), lambda t: 1 + 7 * min(1.0, t / d)), gain=0.9)
    rng = random.Random(9)
    for k in range(10):
        at = 0.18 * rng.random() ** 1.5  # the shards fly early
        f = rng.uniform(2500, 6000) * (1 - 3 * at)
        length = rng.uniform(0.01, 0.03)
        shard = voice(length, sweep(f, f * 0.6, length), decay(length / 3, 0.0005), 9000,
                      shape="pulse", width=rng.choice((0.125, 0.25, 0.5)), seed=10 + k)
        mix(out, crush(shard, 5, rng.choice((2, 3, 4))), at, 0.3 * (1 - 3 * at))
    return out


def _round() -> list[float]:
    # round won / draw: a climbing E arpeggio opening up, over a resonant hum
    step = 0.065
    out = voice(0.34, arp((64, 71, 76, 83), step), retrig(step, 0.08, 4, 0.1), sweep(1200, 6000, 0.25),
                detune=(-8, 0, 8), q=2.0, seed=11)
    return mix(out, voice(0.34, hz(40), decay(0.2, 0.01), 330, detune=(-6, 6), q=5.0, seed=12), gain=0.5)


def _match() -> list[float]:
    # match won: a long E minor arpeggio, filter sweeping wide open, hum and sub below
    step = 0.065
    notes = (64, 67, 71, 76, 79, 83, 88)
    out = voice(0.7, arp(notes, step), retrig(step, 0.09, len(notes), 0.2), sweep(700, 7000, 0.5),
                detune=(-9, 0, 9), q=2.0, sub=0.3, seed=13)
    return mix(out, voice(0.7, hz(40), decay(0.35, 0.02), 330, detune=(-6, 6), q=5.0, seed=14), gain=0.5)


# name: (builder, level, drive). level is the RMS of the loudest 50 ms as a
# fraction of full scale, calibrated so that each effect is as loud, A-weighted,
# as the plain sine it replaced; PEAK caps the ones a sharp attack makes peaky
# (GO, about 1 dB short). drive is the tanh saturation on the output.
EFFECTS = {
    "beep": (_beep, 0.276, 1.8),
    "go": (_go, 0.388, 3.0),
    "pickup": (_pickup, 0.250, 1.8),
    "split": (_split, 0.189, 1.8),
    "collapse": (_collapse, 0.251, 1.8),
    "measure": (_measure, 0.195, 1.8),
    "crash": (_crash, 0.272, 1.8),
    "teleport": (_teleport, 0.263, 1.8),
    "shield": (_shield, 0.371, 1.8),
    "blip": (_blip, 0.233, 1.8),
    "confirm": (_confirm, 0.246, 2.5),
    "round": (_round, 0.279, 2.5),
    "match": (_match, 0.261, 1.8),
}

_CUE_SOUNDS = {"beep": "beep", "go": "go", "blip": "blip", "start": "confirm", "ready": "confirm", "pause": "beep",
               "round_won": "round", "draw": "round", "match_won": "match"}


def loudness(xs: list[float], sr: int, window: float = 0.05) -> float:
    """The RMS of the loudest `window` seconds of xs."""
    w = max(1, min(len(xs), round(window * sr)))
    sq = [v * v for v in xs]
    acc = sum(sq[:w])
    best = acc
    for i in range(w, len(sq)):
        acc += sq[i] - sq[i - w]
        if acc > best:
            best = acc
    return math.sqrt(max(0.0, best) / w)


def finish(xs: list[float], level: float, sample_rate: int, drive: float = DRIVE,
           src_rate: int = SYNTH_RATE) -> list[int]:
    """16-bit samples at sample_rate: xs faded in and out (so they start and
    end on 0), scaled to `level` loudness but never past PEAK, and
    resampled from src_rate by linear interpolation."""
    n = len(xs)
    fade_in = max(1, min(n // 4, round(0.0015 * src_rate)))
    fade_out = max(1, min(n // 4, round(0.006 * src_rate)))
    xs = list(xs)
    for i in range(fade_in):
        xs[i] *= i / fade_in
    for i in range(fade_out):
        xs[n - 1 - i] *= i / fade_out
    peak = max(abs(v) for v in xs)
    if peak == 0.0:
        return [0] * max(1, round(n * sample_rate / src_rate))
    tanh = math.tanh
    xs = [tanh(drive * v / peak) for v in xs]  # soft saturation: fatter, and tames the peaks
    peak = math.tanh(drive)
    gain = 32767 * min(level / loudness(xs, src_rate), PEAK / peak)
    m = max(1, round(n * sample_rate / src_rate))
    if m == n:
        return [round(v * gain) for v in xs]
    scale = (n - 1) / (m - 1) if m > 1 else 0.0
    out = []
    for i in range(m):
        pos = i * scale
        j = int(pos)
        frac = pos - j
        v = xs[j] if frac == 0.0 else xs[j] + (xs[j + 1] - xs[j]) * frac
        out.append(round(v * gain))
    return out


def render(name: str, sample_rate: int) -> list[int]:
    """One effect as mono 16-bit samples at sample_rate."""
    build, level, drive = EFFECTS[name]
    return finish(build(), level, sample_rate, drive)


def event_sounds(events: list) -> list[str]:
    """The sounds a frame's events ask for, each at most once."""
    names = []
    for e in events:
        if isinstance(e, rules.Split):
            names.append("split")
        elif isinstance(e, rules.Crash):
            names.append("crash")
        elif isinstance(e, rules.Collapse) and e.reason in ("measurement", "decoherence"):
            names.append("collapse")  # a crash already makes its own sound
        elif isinstance(e, rules.Measured):
            names.append("measure")
        elif isinstance(e, rules.PickedUp):
            names.append("shield" if e.kind == "Z" else "pickup")
        elif isinstance(e, rules.Teleported):
            names.append("teleport")
        elif isinstance(e, Cue):
            names.append(_CUE_SOUNDS[e.kind])
    return list(dict.fromkeys(names))


class Sounds:
    def __init__(self, sounds: dict) -> None:
        self._sounds = sounds

    def play_events(self, events: list) -> None:
        for name in event_sounds(events):
            effect = self._sounds.get(name)
            if effect is not None:
                effect.play()


def _make_sound(samples: list[int], channels: int) -> pygame.mixer.Sound:
    mono = array.array("h", samples)
    buf = array.array("h", bytes(2 * len(mono) * channels))
    for c in range(channels):
        buf[c::channels] = mono
    return pygame.mixer.Sound(buffer=buf.tobytes())


def load_sounds() -> Sounds:
    """Init the mixer and build every effect for whatever it negotiated, or
    fall back to silence if there is no audio at all."""
    try:
        pygame.mixer.init(frequency=SYNTH_RATE, size=-16, channels=2)
        init_info = pygame.mixer.get_init()
        if not init_info:
            raise pygame.error("mixer did not initialize")
        freq, _format, channels = init_info
        return Sounds({name: _make_sound(render(name, freq), max(1, channels)) for name in EFFECTS})
    except (pygame.error, ValueError):
        return Sounds({})
