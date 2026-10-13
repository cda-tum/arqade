"""Short procedurally generated sound effects. No audio assets, no numpy.

The same little synth as Qurves: every effect is a sine sweep, some with
noise, some with a second step (a two-note chime). sweep_samples is pure and
unit tested. Building pygame Sounds needs a real mixer; without one (no
sound card), every effect is a silent no-op, so a cabinet running unattended
never crashes over audio.

Bots make the same sounds as people for what happens to them (a bump, a
swap, a spin-out), but drifting, the red warning, boosts, jumps, being put
back in and taking the lead sound only for people: with eight racers, the
bots' would be noise. The last seconds before anyone wins tick for
everyone. There is deliberately no engine hum: it would grate on a public
cabinet.
"""

from __future__ import annotations

import array
import math
import random

import pygame

SAMPLE_RATE = 22050

# name: steps of (start Hz, end Hz, seconds, noise mix 0..1), played in a row
EFFECTS = {
    "beep": ((660, 660, 0.09, 0.0),),
    "go": ((990, 990, 0.25, 0.0),),
    "blip": ((880, 880, 0.05, 0.0),),
    "confirm": ((700, 1400, 0.09, 0.0),),
    "lock": ((660, 660, 0.06, 0.0), (990, 990, 0.12, 0.0)),
    "drift": ((2600, 2200, 0.16, 0.6),),
    "warn": ((1500, 1500, 0.04, 0.0), (1500, 1500, 0.04, 0.0)),
    "spin": ((600, 90, 0.45, 0.5),),
    "bump": ((170, 90, 0.08, 0.6),),
    "push": ((240, 110, 0.13, 0.5),),
    "swap": ((500, 1500, 0.07, 0.0), (1500, 500, 0.07, 0.0)),
    "copy": ((300, 900, 0.18, 0.0),),
    "copy_lost": ((700, 300, 0.15, 0.2),),
    "decohered": ((900, 250, 0.25, 0.1),),
    "err_armed": ((400, 800, 0.10, 0.1),),
    "launch": ((900, 1700, 0.08, 0.1),),
    "bitflip": ((1700, 400, 0.15, 0.25),),
    "phaseflip": ((320, 120, 0.28, 0.35),),
    "zeno_armed": ((1200, 1200, 0.05, 0.0),),
    "zeno": ((2400, 2400, 0.08, 0.0), (1800, 1800, 0.25, 0.0)),
    "boost": ((300, 1400, 0.22, 0.25),),
    "jump": ((500, 1100, 0.12, 0.1),),
    "land": ((160, 70, 0.10, 0.6),),
    "reset": ((200, 1200, 0.22, 0.3),),
    "lead": ((784, 784, 0.07, 0.0), (1175, 1175, 0.12, 0.0)),
    "tick": ((1400, 1400, 0.03, 0.0),),
    "match_won": ((523, 523, 0.10, 0.0), (659, 659, 0.10, 0.0), (784, 784, 0.10, 0.0), (1046, 1046, 0.35, 0.0)),
}
VOLUME = {"drift": 0.25, "warn": 0.35, "bump": 0.5, "zeno_armed": 0.3, "err_armed": 0.4, "land": 0.5,
          "jump": 0.6, "lead": 0.6, "tick": 0.5}
PEOPLE_ONLY = {"drift", "warn", "boost", "jump", "land", "reset", "lead"}
_ALIASES = {"pause": "beep"}


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


def effect_samples(name: str, sample_rate: int, volume: float = 0.45) -> list[int]:
    out: list[int] = []
    for f0, f1, duration, noise in EFFECTS[name]:
        out += sweep_samples(f0, f1, duration, sample_rate, volume * VOLUME.get(name, 1.0), noise)
    return out


def event_sounds(events: list, people: tuple[str, ...] | set[str]) -> list[str]:
    """The sounds a frame's events ask for, each at most once."""
    names = []
    for e in events:
        name = _ALIASES.get(e.kind, e.kind)
        if name not in EFFECTS:
            continue
        if name in PEOPLE_ONLY and e.player not in people:
            continue
        names.append(name)
    return list(dict.fromkeys(names))


class Sounds:
    def __init__(self, sounds: dict) -> None:
        self._sounds = sounds

    def play_events(self, events: list, people: tuple[str, ...] | set[str] = ()) -> None:
        for name in event_sounds(events, people):
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
        pygame.mixer.set_num_channels(16)
        return Sounds({name: _make_sound(effect_samples(name, freq), max(1, channels)) for name in EFFECTS})
    except (pygame.error, ValueError):
        return Sounds({})
