"""Short procedurally generated sound effects. No audio assets, no numpy.

sweep_samples is pure and unit tested. Building pygame Sounds needs a real
mixer; without one (no sound card), every effect is a silent no-op, so a
cabinet running unattended never crashes over audio. There is deliberately
no engine hum: it would grate on a public cabinet.
"""

from __future__ import annotations

import array
import math
import random

import pygame

from qurves import rules
from qurves.match import Cue

SAMPLE_RATE = 22050

# name: (start Hz, end Hz, seconds, noise mix 0..1)
EFFECTS = {
    "beep": (660, 660, 0.09, 0.0),
    "go": (990, 990, 0.20, 0.0),
    "pickup": (1200, 1700, 0.07, 0.0),
    "split": (300, 900, 0.18, 0.0),
    "collapse": (900, 250, 0.25, 0.1),
    "measure": (1800, 500, 0.10, 0.35),
    "crash": (220, 50, 0.40, 0.8),
    "teleport": (400, 2200, 0.16, 0.15),
    "shield": (700, 1400, 0.22, 0.0),
    "blip": (880, 880, 0.05, 0.0),
    "confirm": (660, 1320, 0.12, 0.0),
    "round": (520, 780, 0.30, 0.0),
    "match": (520, 1040, 0.60, 0.0),
}

_CUE_SOUNDS = {"beep": "beep", "go": "go", "blip": "blip", "start": "confirm", "ready": "confirm", "pause": "beep",
               "round_won": "round", "draw": "round", "match_won": "match"}


def sweep_samples(
    f0: float, f1: float, duration: float, sample_rate: int, volume: float,
    noise: float = 0.0, seed: int = 1,
) -> list[int]:
    """Mono 16-bit samples: a sine sweeping linearly from f0 to f1, mixed with
    some white noise, faded in and out (no clicks) and decaying a little."""
    n = max(1, round(sample_rate * duration))
    amplitude = round(max(0.0, min(1.0, volume)) * 32767)
    fade = max(1, min(200, n // 4))
    rng = random.Random(seed)
    phase = 0.0
    out = []
    for i in range(n):
        phase += 2 * math.pi * (f0 + (f1 - f0) * i / n) / sample_rate
        value = (1 - noise) * math.sin(phase) + noise * rng.uniform(-1.0, 1.0)
        envelope = min(1.0, min(i, n - 1 - i) / fade) * (1 - 0.6 * i / n)
        out.append(round(amplitude * envelope * value))
    return out


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
    buf = array.array("h")
    for value in samples:
        for _ in range(channels):
            buf.append(value)
    return pygame.mixer.Sound(buffer=buf.tobytes())


def load_sounds() -> Sounds:
    """Init the mixer and build every effect for whatever it negotiated, or
    fall back to silence if there is no audio at all."""
    try:
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)
        init_info = pygame.mixer.get_init()
        if not init_info:
            raise pygame.error("mixer did not initialize")
        freq, _format, channels = init_info
        return Sounds({
            name: _make_sound(sweep_samples(f0, f1, dur, freq, 0.45, noise), max(1, channels))
            for name, (f0, f1, dur, noise) in EFFECTS.items()
        })
    except (pygame.error, ValueError):
        return Sounds({})
