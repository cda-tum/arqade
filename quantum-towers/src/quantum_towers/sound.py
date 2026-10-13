"""Procedurally-generated sound effects. No audio assets, no numpy.

Started as single-frequency sine beeps (same approach as Quantum Pong's
sibling module), but a plain sine beep reads as a dull "boop" no matter what
frequency you pick -- the actual variety comes from three things layered on
top, all pure and unit tested:

  - `waveform`: "sine" (soft/dull), "square" and "sawtooth" (buzzy, harmonic-
    rich, classic 8-bit-chiptune character), "triangle" (between the two).
  - `generate_sweep_samples`: frequency change *within* a single sound (a
    "pew" laser needs a falling pitch, not a fixed tone).
  - `generate_sequence_samples`: multiple notes back-to-back, i.e. an actual
    short jingle instead of one beep.

Turning samples into a pygame.mixer.Sound (and initializing the mixer) needs
a real audio backend, so that part is integration code, verified by running
the game -- if the mixer or audio device isn't available (e.g. a cabinet
with no sound card), loading falls back to silent no-op sounds rather than
crashing.
"""

from __future__ import annotations

import array
import math
from typing import NamedTuple

import pygame

SAMPLE_RATE = 22050

Waveform = str  # "sine" | "square" | "triangle" | "sawtooth"


def _waveform_value(waveform: Waveform, phase: float) -> float:
    """One sample of `waveform` at `phase` radians, in [-1, 1]."""
    if waveform == "sine":
        return math.sin(phase)
    if waveform == "square":
        return 1.0 if math.sin(phase) >= 0 else -1.0
    if waveform == "triangle":
        return (2.0 / math.pi) * math.asin(math.sin(phase))
    if waveform == "sawtooth":
        fraction = (phase / (2 * math.pi)) % 1.0
        return 2.0 * fraction - 1.0
    raise ValueError(f"unknown waveform: {waveform!r}")


def _fade(i: int, n_samples: int) -> float:
    """Linear fade in/out over the first/last few samples, to avoid clicks."""
    fade_samples = max(1, min(200, n_samples // 4))
    edge_distance = min(i, n_samples - 1 - i)
    return min(1.0, edge_distance / fade_samples)


def generate_tone_samples(
    frequency: float, duration: float, sample_rate: int, volume: float, waveform: Waveform = "sine"
) -> list[int]:
    """Mono 16-bit signed samples for a fixed-frequency tone with a short
    linear fade in/out (avoids clicks at the start/end)."""
    n_samples = max(1, round(sample_rate * duration))
    amplitude = round(max(0.0, min(1.0, volume)) * 32767)

    samples = []
    for i in range(n_samples):
        phase = 2 * math.pi * frequency * i / sample_rate
        value = round(amplitude * _fade(i, n_samples) * _waveform_value(waveform, phase))
        samples.append(value)
    return samples


def generate_sweep_samples(
    start_frequency: float,
    end_frequency: float,
    duration: float,
    sample_rate: int,
    volume: float,
    waveform: Waveform = "sine",
) -> list[int]:
    """Like `generate_tone_samples`, but the frequency glides linearly from
    `start_frequency` to `end_frequency` over the sound's duration -- a
    falling sweep is what actually makes a "pew" read as a shot fired,
    rather than just another fixed-pitch beep. Phase is accumulated
    (integrated frequency) rather than recomputed from the instantaneous
    frequency each sample, which would click/pop at every step."""
    n_samples = max(1, round(sample_rate * duration))
    amplitude = round(max(0.0, min(1.0, volume)) * 32767)

    samples = []
    phase = 0.0
    for i in range(n_samples):
        progress = i / max(1, n_samples - 1)
        frequency = start_frequency + (end_frequency - start_frequency) * progress
        phase += 2 * math.pi * frequency / sample_rate
        value = round(amplitude * _fade(i, n_samples) * _waveform_value(waveform, phase))
        samples.append(value)
    return samples


def generate_sequence_samples(
    notes: list[tuple[float, float]], sample_rate: int, volume: float, waveform: Waveform = "sine"
) -> list[int]:
    """A short jingle: `notes` is a list of (frequency, duration) played
    back-to-back. Each note gets its own tone (and its own fade in/out),
    which gives each note a clear, separated, staccato attack rather than
    one long blurred tone -- the same reason a chiptune melody is played as
    distinct notes, not a single pitch-bent sound."""
    samples: list[int] = []
    for frequency, duration in notes:
        samples.extend(generate_tone_samples(frequency, duration, sample_rate, volume, waveform))
    return samples


def _samples_to_sound(samples: list[int], channels: int) -> pygame.mixer.Sound:
    buf = array.array("h")
    for value in samples:
        for _ in range(channels):
            buf.append(value)
    return pygame.mixer.Sound(buffer=buf.tobytes())


class _NullSound:
    """Stand-in for when the mixer/audio device isn't available."""

    def play(self) -> None:
        pass


_NULL = _NullSound()


class Sounds(NamedTuple):
    climb: object
    perfect: object
    shot: object
    # The rest default to silence, so a Sounds(climb, perfect, shot) built by
    # a test still works.
    gate: object = _NULL  # any gate press
    stun: object = _NULL  # a wrong confirm
    move: object = _NULL  # a menu's selection moves
    select: object = _NULL  # a menu item picked, the tutorial dismissed
    tick: object = _NULL  # 3, 2, 1 before a time trial
    go: object = _NULL  # ...and GO!
    win: object = _NULL  # the top reached


def silent() -> Sounds:
    """Every sound a no-op: the default for screens a test drives."""
    return Sounds(_NULL, _NULL, _NULL)


def load_sounds() -> Sounds:
    """Init the mixer and build sounds to match whatever it actually
    negotiates (a real device may not grant the exact frequency/channels
    requested) -- falls back to silent no-op sounds if audio isn't available
    at all, so a missing sound card never crashes a cabinet running
    unattended."""
    try:
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)
        init_info = pygame.mixer.get_init()
        if not init_info:
            raise pygame.error("mixer did not initialize")
        actual_freq, _format, actual_channels = init_info
        channels = max(1, actual_channels)

        # Climb: a quick 2-note "step up" (a rising fourth) -- short and
        # unobtrusive since it plays on every successful confirm.
        climb_samples = generate_sequence_samples(
            [(392.00, 0.045), (523.25, 0.065)], actual_freq, 0.55, waveform="square"
        )
        # Perfect: a brighter 4-note major arpeggio with a held final note --
        # a proper little "ta-da!" since this one's rarer and worth savoring.
        perfect_samples = generate_sequence_samples(
            [(523.25, 0.07), (659.25, 0.07), (783.99, 0.07), (1046.50, 0.18)],
            actual_freq, 0.6, waveform="square",
        )
        # Shot: a falling pitch sweep on a buzzier sawtooth wave -- reads as
        # a laser/blaster, not a beep, and is texturally distinct from the
        # melodic square-wave jingles above.
        shot_samples = generate_sweep_samples(
            820.0, 160.0, 0.14, actual_freq, 0.6, waveform="sawtooth"
        )

        # Gate: the softest, shortest blip of the set -- it plays on every
        # press, from two players at once, so it must stay out of the way.
        gate_samples = generate_tone_samples(660.0, 0.03, actual_freq, 0.25, waveform="triangle")
        # Stun: a low falling buzz, the "wrong!" to the climb's "step up".
        stun_samples = generate_sweep_samples(220.0, 90.0, 0.25, actual_freq, 0.5, waveform="square")
        # Menus: a tick for moving, a rising pair for picking.
        move_samples = generate_tone_samples(880.0, 0.03, actual_freq, 0.3, waveform="square")
        select_samples = generate_sequence_samples(
            [(659.25, 0.05), (987.77, 0.08)], actual_freq, 0.45, waveform="square"
        )
        # Countdown: three short beeps, then a higher, longer GO.
        tick_samples = generate_tone_samples(440.0, 0.09, actual_freq, 0.45, waveform="square")
        go_samples = generate_tone_samples(880.0, 0.25, actual_freq, 0.45, waveform="square")
        # Win: a longer fanfare than PERFECT's, ending on a held high C.
        win_samples = generate_sequence_samples(
            [(523.25, 0.1), (659.25, 0.1), (783.99, 0.1), (659.25, 0.1), (783.99, 0.1),
             (1046.50, 0.4)],
            actual_freq, 0.55, waveform="square",
        )

        def make(samples: list[int]) -> pygame.mixer.Sound:
            return _samples_to_sound(samples, channels)

        return Sounds(
            climb=make(climb_samples),
            perfect=make(perfect_samples),
            shot=make(shot_samples),
            gate=make(gate_samples),
            stun=make(stun_samples),
            move=make(move_samples),
            select=make(select_samples),
            tick=make(tick_samples),
            go=make(go_samples),
            win=make(win_samples),
        )
    except (pygame.error, ValueError):
        return silent()
