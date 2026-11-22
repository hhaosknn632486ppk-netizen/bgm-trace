import numpy as np
import pytest
from scipy.signal import butter, sosfiltfilt

from bgm_trace.alignment import align_arrays, ncc


def recording(seed=17, seconds=48, rate=4000):
    rng = np.random.default_rng(seed)
    noise = rng.normal(size=seconds * rate)
    return sosfiltfilt(butter(3, [150, 1400], fs=rate, btype="bandpass", output="sos"), noise)


@pytest.mark.parametrize("speed", [1., 1.03, 1.0273])
def test_speed_changed_recording_with_noise(speed):
    rate, start, duration = 4000, 7.25, 28
    reference = recording()
    query = np.interp(start * rate + np.arange(duration * rate) * speed, np.arange(len(reference)), reference)
    query = query * .4 + np.random.default_rng(2).normal(scale=.04, size=len(query)) + .2
    result = align_arrays(query, reference)
    assert result["evidence_passed"], result
    assert result["speed_factor"] == pytest.approx(speed, abs=.001)
    assert result["reference_start_seconds"] == pytest.approx(start, abs=.05)
    assert len(result["windows"]) >= 2


def test_unrelated_audio_is_not_verified():
    result = align_arrays(recording(2, 28), recording(3))
    assert not result["evidence_passed"]


def test_silence_is_not_verified():
    result = align_arrays(np.zeros(8 * 4000), recording())
    assert not result["evidence_passed"]


def test_repeated_whole_passage_has_ambiguous_timing():
    passage = recording(19, 16)
    reference = np.r_[passage, passage, passage]
    result = align_arrays(passage[4000:13 * 4000], reference, speed_min=1., speed_max=1.)
    assert result["timing_ambiguous"]
    assert not result["evidence_passed"]


def test_ncc_ignores_gain_and_dc():
    reference = np.random.default_rng(12).normal(size=3000)
    result = ncc(reference, reference[715:1215] * 2.4 + 7)
    assert np.argmax(result) == 715
    assert result[715] == pytest.approx(1)
    assert not ncc(reference, np.ones(200)).any()


@pytest.mark.parametrize("options", [{"speed_min": 0}, {"speed_step": 0}, {"window_seconds": float("nan")}])
def test_invalid_search_is_rejected(options):
    with pytest.raises(ValueError):
        align_arrays(np.ones(20000), np.ones(40000), **options)


def test_missing_duration_and_nan_are_rejected():
    with pytest.raises(ValueError):
        align_arrays(np.ones(100), np.ones(40000))
    with pytest.raises(ValueError):
        align_arrays(np.full(20000, np.nan), np.ones(40000))


def test_grid_midpoint_speed_with_high_frequency_signal():
    rate, start, duration, speed = 4000, 6.5, 28, 1.025
    rng = np.random.default_rng(23)
    t = np.arange(48 * rate) / rate
    envelope = .4 + .6 * np.maximum(0., np.sin(2 * np.pi * 1.7 * t) + .5 * np.cos(2 * np.pi * 2.9 * t))
    reference = sosfiltfilt(butter(4, [600, 1500], fs=rate, btype="bandpass", output="sos"), rng.normal(size=len(t)) * envelope)
    query = np.interp(start * rate + np.arange(duration * rate) * speed, np.arange(len(reference)), reference)
    result = align_arrays(query, reference, speed_min=.94, speed_max=1.06, speed_step=.01)
    assert result["evidence_passed"], result
    assert result["speed_factor"] == pytest.approx(speed, abs=.001)
    assert result["reference_start_seconds"] == pytest.approx(start, abs=.05)


def test_high_speed_alignment_avoids_aliasing():
    rate, start, duration, speed = 4000, 5.0, 24, 1.5
    rng = np.random.default_rng(31)
    reference = rng.normal(size=54 * rate)
    # Build ground truth from an anti-aliased high-rate representation.
    from scipy.signal import resample_poly
    ref_hi = resample_poly(reference, 2, 1)
    anti = butter(6, .45 * rate / speed, btype="lowpass", fs=2 * rate, output="sos")
    ref_clean = sosfiltfilt(anti, ref_hi)
    query = np.interp((start * rate + np.arange(duration * rate) * speed) * 2., np.arange(len(ref_clean)), ref_clean)
    result = align_arrays(query, reference, speed_min=1.35, speed_max=1.65, speed_step=.05)
    assert result["evidence_passed"], result
    assert result["speed_factor"] == pytest.approx(speed, abs=.002)
    assert result["reference_start_seconds"] == pytest.approx(start, abs=.05)


def test_bgm_entering_after_query_start_aligns_with_negative_offset():
    rate, intro = 4000, 4.0
    reference = recording(41, 40, rate)
    unrelated = recording(42, int(intro), rate)
    query = np.r_[unrelated, reference[:26 * rate]]
    result = align_arrays(query, reference, speed_min=1., speed_max=1.)
    assert result["evidence_passed"], result
    assert result["reference_start_seconds"] == pytest.approx(-intro, abs=.05)
    assert len(result["windows"]) >= 2
