import pytest

from quantum_towers.sound import (
    generate_sequence_samples,
    generate_sweep_samples,
    generate_tone_samples,
)


def test_generate_tone_samples_has_expected_sample_count():
    samples = generate_tone_samples(frequency=440.0, duration=0.1, sample_rate=1000, volume=0.5)
    assert len(samples) == 100


def test_generate_tone_samples_fades_in_from_zero():
    samples = generate_tone_samples(frequency=440.0, duration=0.1, sample_rate=1000, volume=0.5)
    assert samples[0] == 0


def test_generate_tone_samples_fades_out_to_zero():
    samples = generate_tone_samples(frequency=440.0, duration=0.1, sample_rate=1000, volume=0.5)
    assert samples[-1] == 0


def test_generate_tone_samples_stays_within_16_bit_signed_range():
    samples = generate_tone_samples(frequency=440.0, duration=0.2, sample_rate=8000, volume=1.0)
    assert all(-32768 <= s <= 32767 for s in samples)


def test_generate_tone_samples_zero_volume_is_silent():
    samples = generate_tone_samples(frequency=440.0, duration=0.05, sample_rate=1000, volume=0.0)
    assert all(s == 0 for s in samples)


def test_generate_tone_samples_square_wave_is_flat_top_and_bottom():
    # Away from the fade edges, a square wave only ever takes its two
    # extreme values -- that flat-top harmonic content is what makes it
    # sound buzzy/chiptune rather than a soft sine "boop".
    samples = generate_tone_samples(
        frequency=100.0, duration=0.5, sample_rate=2000, volume=1.0, waveform="square"
    )
    sustained = samples[300:-300]  # well clear of the fade-in/fade-out region
    assert all(abs(abs(s) - 32767) <= 1 for s in sustained)


def test_generate_tone_samples_sawtooth_wave_spans_full_range():
    samples = generate_tone_samples(
        frequency=50.0, duration=0.5, sample_rate=2000, volume=1.0, waveform="sawtooth"
    )
    sustained = samples[300:-300]
    assert min(sustained) < -32000
    assert max(sustained) > 30000


def test_generate_tone_samples_unknown_waveform_raises():
    with pytest.raises(ValueError):
        generate_tone_samples(frequency=440.0, duration=0.01, sample_rate=1000, volume=1.0, waveform="hum")


def test_generate_sweep_samples_has_expected_sample_count():
    samples = generate_sweep_samples(
        start_frequency=800.0, end_frequency=200.0, duration=0.1, sample_rate=1000, volume=0.5
    )
    assert len(samples) == 100


def test_generate_sweep_samples_stays_within_16_bit_signed_range():
    samples = generate_sweep_samples(
        start_frequency=800.0, end_frequency=100.0, duration=0.2, sample_rate=8000, volume=1.0
    )
    assert all(-32768 <= s <= 32767 for s in samples)


def test_generate_sweep_samples_pitch_actually_changes():
    # A falling sweep should have a higher instantaneous frequency (more
    # zero-crossings per unit time) in its first half than its second half
    # -- otherwise it's just a fixed tone with a fancier name.
    samples = generate_sweep_samples(
        start_frequency=2000.0, end_frequency=100.0, duration=0.2, sample_rate=20000, volume=1.0,
        waveform="sine",
    )
    midpoint = len(samples) // 2
    first_half, second_half = samples[:midpoint], samples[midpoint:]

    def zero_crossings(chunk):
        return sum(1 for a, b in zip(chunk, chunk[1:]) if (a >= 0) != (b >= 0))

    assert zero_crossings(first_half) > zero_crossings(second_half)


def test_generate_sequence_samples_concatenates_note_lengths():
    notes = [(440.0, 0.05), (880.0, 0.1)]
    samples = generate_sequence_samples(notes, sample_rate=1000, volume=0.5)
    assert len(samples) == 50 + 100


def test_generate_sequence_samples_empty_list_is_empty():
    assert generate_sequence_samples([], sample_rate=1000, volume=0.5) == []


def test_generate_sequence_samples_matches_playing_each_note_separately():
    notes = [(440.0, 0.05), (880.0, 0.05)]
    sequence = generate_sequence_samples(notes, sample_rate=1000, volume=0.5, waveform="square")
    expected = generate_tone_samples(440.0, 0.05, 1000, 0.5, "square") + generate_tone_samples(
        880.0, 0.05, 1000, 0.5, "square"
    )
    assert sequence == expected
