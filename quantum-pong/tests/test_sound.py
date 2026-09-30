from quantum_pong.sound import generate_tone_samples


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
