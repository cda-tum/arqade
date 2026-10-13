"""Short synthesized sound effects, built in code at start-up. No audio files,
no numpy.

The game is a surf poster, so the sounds are surf guitar: plucked strings
(Karplus-Strong) in E minor pentatonic through a spring-reverb-like echo,
tremolo-picked for the fanfare. The lab gear in the sandbox (laser kick,
cooling) gets plain sine sweeps instead. There is deliberately no sound for
holding a voltage: it would drone for the whole match.

The sample builders are pure and unit tested. Building pygame Sounds needs a
real mixer; without one (no sound card, a broken driver) every effect is a
silent no-op, so the cabinet never crashes over audio.
"""

from __future__ import annotations

import array
import math
import random

import pygame

SAMPLE_RATE = 22050

NOTES = {"E3": 164.81, "A3": 220.0, "B3": 246.94, "D4": 293.66, "E4": 329.63, "G4": 392.0,
         "A4": 440.0, "B4": 493.88, "D5": 587.33, "E5": 659.26, "G5": 783.99, "B5": 987.77}


def pluck(freq: float, duration: float, sr: int, seed: int = 1, decay: float = 0.996) -> list[float]:
    """A plucked string (Karplus-Strong): a burst of noise in a delay line one
    period long, averaged as it goes round, so it rings at freq and dies away."""
    period = max(2, round(sr / freq))
    rng = random.Random(seed)
    line = [rng.uniform(-1.0, 1.0) for _ in range(period)]
    out = []
    prev = 0.0
    for i in range(max(1, round(sr * duration))):
        k = i % period
        cur = line[k]
        line[k] = decay * 0.5 * (cur + prev)
        prev = cur
        out.append(cur)
    return out


def sweep(f0: float, f1: float, duration: float, sr: int, noise: float = 0.0,
          seed: int = 1) -> list[float]:
    """A sine sweeping linearly from f0 to f1, mixed with some white noise and
    decaying a little."""
    n = max(1, round(sr * duration))
    rng = random.Random(seed)
    phase = 0.0
    out = []
    for i in range(n):
        phase += 2 * math.pi * (f0 + (f1 - f0) * i / n) / sr
        value = (1 - noise) * math.sin(phase) + noise * rng.uniform(-1.0, 1.0)
        out.append(value * (1 - 0.6 * i / n))
    return out


def riff(notes: list[str], step: float, sr: int, ring: float = 0.35) -> list[float]:
    """Plucked notes, one every `step` seconds, each left to ring for `ring`
    seconds over the next. A repeated note is surf tremolo picking."""
    start = round(step * sr)
    out = [0.0] * (start * (len(notes) - 1) + round(ring * sr))
    for i, name in enumerate(notes):
        for j, v in enumerate(pluck(NOTES[name], ring, sr, seed=i + 1)):
            out[i * start + j] += v
    return out


def echo(samples: list[float], sr: int, delay: float = 0.09, feedback: float = 0.35,
         taps: int = 3) -> list[float]:
    """The spring reverb, roughly: a few fading repeats close behind."""
    d = round(delay * sr)
    out = samples + [0.0] * (d * taps)
    for t in range(1, taps + 1):
        g = feedback ** t
        for i, v in enumerate(samples):
            out[i + t * d] += g * v
    return out


def to_pcm(samples: list[float], volume: float) -> list[int]:
    """16-bit samples, the peak scaled to `volume` and the ends faded, so
    nothing clicks."""
    n = len(samples)
    peak = max((abs(v) for v in samples), default=0.0) or 1.0
    gain = max(0.0, min(1.0, volume)) * 32767 / peak
    fade = max(1, min(120, n // 4))
    return [round(v * gain * min(1.0, i / fade, (n - 1 - i) / fade)) for i, v in enumerate(samples)]


# name: (builder(sample_rate) -> float samples, volume)
EFFECTS = {
    # menus
    "move": (lambda sr: pluck(NOTES["E5"], 0.12, sr), 0.22),
    "confirm": (lambda sr: echo(riff(["B4", "E5"], 0.06, sr, 0.25), sr), 0.32),
    "back": (lambda sr: riff(["E5", "B4"], 0.06, sr, 0.22), 0.28),
    "pause": (lambda sr: echo(pluck(NOTES["B4"], 0.2, sr), sr), 0.3),
    "start": (lambda sr: echo(riff(["E4", "E4", "E4", "G4", "B4", "E5"], 0.055, sr, 0.3), sr), 0.4),
    # surfing
    "electrode": (lambda sr: sweep(1500, 1500, 0.025, sr), 0.1),
    "photon": (lambda sr: echo(sweep(1300, 2600, 0.08, sr), sr, 0.06, 0.4), 0.3),
    "bounce": (lambda sr: sweep(260, 70, 0.12, sr, noise=0.6), 0.28),
    "lost": (lambda sr: echo(sweep(700, 110, 0.45, sr, noise=0.25), sr, 0.12, 0.3, 2), 0.42),
    "over": (lambda sr: echo(riff(["E4", "D4", "B3", "A3", "E3"], 0.14, sr, 0.5), sr, 0.12), 0.42),
    "win": (lambda sr: echo(riff(["E4", "E4", "E4", "G4", "A4", "B4", "B4", "D5", "E5", "E5"],
                                 0.07, sr, 0.4), sr, 0.11), 0.42),
    # sandbox
    "kick": (lambda sr: sweep(250, 1800, 0.12, sr, noise=0.1), 0.32),
    "ion_add": (lambda sr: riff(["A4", "E5"], 0.05, sr, 0.2), 0.3),
    "ion_remove": (lambda sr: riff(["E5", "A4"], 0.05, sr, 0.2), 0.3),
    "cool": (lambda sr: sweep(1800, 300, 0.35, sr), 0.2),
    "toggle_on": (lambda sr: riff(["E5", "B5"], 0.05, sr, 0.18), 0.26),
    "toggle_off": (lambda sr: riff(["B5", "E5"], 0.05, sr, 0.18), 0.26),
    "warn": (lambda sr: sweep(190, 170, 0.09, sr, noise=0.3) + [0.0] * round(0.05 * sr)
             + sweep(190, 170, 0.09, sr, noise=0.3), 0.26),
}

# Shortest gap (ms) between two plays of one effect. A ball bouncing along a
# bumpy curve can land hard several times a second.
MIN_GAP_MS = {"bounce": 150, "electrode": 40}


class Sounds:
    """Plays effects by name. Built empty, it is silent (no mixer, tests)."""

    def __init__(self, sounds: dict | None = None) -> None:
        self._sounds = sounds or {}
        self._last: dict[str, int] = {}

    def play(self, name: str) -> None:
        effect = self._sounds.get(name)
        if effect is None:
            return
        gap = MIN_GAP_MS.get(name)
        if gap:
            now = pygame.time.get_ticks()
            if now - self._last.get(name, -gap) < gap:
                return
            self._last[name] = now
        effect.play()


def pre_init() -> None:
    """Ask for the rate the effects are built at, before pygame.init() opens
    the mixer with its own defaults. A small buffer keeps them snappy."""
    pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 512)


def _make_sound(samples: list[int], channels: int) -> pygame.mixer.Sound:
    buf = array.array("h")
    for value in samples:
        buf.extend([value] * channels)
    # Looked up at call time, not imported: the attract capture swaps
    # pygame.mixer.Sound for a subclass that logs every play.
    return pygame.mixer.Sound(buffer=buf.tobytes())


def load_sounds() -> Sounds:
    """Build every effect for whatever the mixer negotiated, or fall back to
    silence if there is no audio at all."""
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(SAMPLE_RATE, -16, 2, 512)
        init_info = pygame.mixer.get_init()
        if not init_info:
            raise pygame.error("mixer did not initialize")
        freq, size, channels = init_info
        if abs(size) != 16:
            raise pygame.error(f"{size}-bit mixer")
        return Sounds({
            name: _make_sound(to_pcm(build(freq), volume), max(1, channels))
            for name, (build, volume) in EFFECTS.items()
        })
    except (pygame.error, ValueError):
        return Sounds()
