"""Simple procedurally-generated beep sounds. No audio assets, no numpy.

`generate_tone_samples` is pure and unit tested. Turning samples into a
pygame.mixer.Sound (and initializing the mixer) needs a real audio backend,
so that part is integration code, verified by running the game -- if the
mixer or audio device isn't available (e.g. a cabinet with no sound card),
loading falls back to silent no-op sounds rather than crashing.
"""

from __future__ import annotations

import array
import math
from typing import NamedTuple

import pygame

SAMPLE_RATE = 22050


def generate_tone_samples(
    frequency: float, duration: float, sample_rate: int, volume: float
) -> list[int]:
    """Mono 16-bit signed samples for a sine tone with a short linear fade in/out
    (avoids clicks at the start/end)."""
    n_samples = max(1, round(sample_rate * duration))
    amplitude = round(max(0.0, min(1.0, volume)) * 32767)
    fade_samples = max(1, min(200, n_samples // 4))

    samples = []
    for i in range(n_samples):
        edge_distance = min(i, n_samples - 1 - i)
        fade = min(1.0, edge_distance / fade_samples)
        value = round(amplitude * fade * math.sin(2 * math.pi * frequency * i / sample_rate))
        samples.append(value)
    return samples


def _make_sound(
    frequency: float, duration: float, sample_rate: int, channels: int, volume: float = 0.55
) -> pygame.mixer.Sound:
    samples = generate_tone_samples(frequency, duration, sample_rate, volume)
    buf = array.array("h")
    for value in samples:
        for _ in range(channels):
            buf.append(value)
    return pygame.mixer.Sound(buffer=buf.tobytes())


class _NullSound:
    """Stand-in for when the mixer/audio device isn't available."""

    def play(self) -> None:
        pass


class Sounds(NamedTuple):
    bounce: object
    score: object
    gate: object
    win: object


def load_sounds() -> Sounds:
    """Init the mixer and build tones to match whatever it actually negotiates
    (a real device may not grant the exact frequency/channels requested) --
    falls back to silent no-op sounds if audio isn't available at all, so a
    missing sound card never crashes a cabinet running unattended."""
    try:
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)
        init_info = pygame.mixer.get_init()
        if not init_info:
            raise pygame.error("mixer did not initialize")
        actual_freq, _format, actual_channels = init_info
        channels = max(1, actual_channels)
        return Sounds(
            bounce=_make_sound(440.0, 0.08, actual_freq, channels),
            score=_make_sound(180.0, 0.22, actual_freq, channels),
            gate=_make_sound(880.0, 0.10, actual_freq, channels),
            win=_make_sound(660.0, 0.45, actual_freq, channels),
        )
    except (pygame.error, ValueError):
        null = _NullSound()
        return Sounds(bounce=null, score=null, gate=null, win=null)
