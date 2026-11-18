from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.signal import correlate, butter, sosfiltfilt

from .media import TraceError, digest, read_mono, run_ffmpeg, save_json


def ncc(reference: np.ndarray, query: np.ndarray) -> np.ndarray:
    """Sliding zero-mean normalized cross-correlation, independent of gain/DC."""
    reference = np.asarray(reference, dtype=np.float64)
    query = np.asarray(query, dtype=np.float64)
    if len(query) > len(reference) or len(query) < 2:
        raise ValueError("Reference must be at least as long as the query window.")
    query = query - query.mean()
    norm = np.linalg.norm(query)
    if norm < 1e-10:
        return np.zeros(len(reference) - len(query) + 1)
    dot = correlate(reference, query, mode="valid", method="fft")
    size = len(query)
    sums = np.r_[0., np.cumsum(reference)]
    squares = np.r_[0., np.cumsum(reference * reference)]
    variance = np.maximum(squares[size:] - squares[:-size] - (sums[size:] - sums[:-size]) ** 2 / size, 0.)
    denominator = norm * np.sqrt(variance)
    values = np.divide(dot, denominator, out=np.zeros_like(dot), where=denominator > 1e-10)
    return np.clip(values, -1., 1.)


def _score_rate(query: np.ndarray, reference: np.ndarray, rate: int, speed: float, starts: list[float], window: float) -> dict:
    sped = np.interp(np.arange(0., len(reference), speed), np.arange(len(reference)), reference)
    length = round(window * rate)
    if len(sped) < length:
        return {"speed": speed, "quality": 0., "search_strength": 0., "windows": [], "offset_spread_seconds": 1e9, "median_correlation": 0.}
    curves = []
    for start in starts:
        clip = query[round(start * rate):round(start * rate) + length]
        if len(clip) != length or np.std(clip) < 1e-7:
            continue
        scores = np.abs(ncc(sped, clip))
        percentile = float(np.quantile(scores[::max(1, len(scores) // 10000)], .99))
        curves.append((start, scores, percentile))
    # Search one common placement across all windows. An independent global peak
    # can land on an earlier repeated motif, even when the full excerpt aligns.
    common_length = min((len(scores) - round(start * rate) for start, scores, _ in curves), default=0)
    matches = []
    ambiguous = False
    if common_length > 0:
        joint = np.mean([np.log(np.maximum(scores[round(start * rate):round(start * rate) + common_length], 1e-8)) for start, scores, _ in curves], axis=0)
        common = int(np.argmax(joint))
        best_joint = float(np.exp(joint[common]))
        distant = np.ones(common_length, dtype=bool)
        distant[max(0, common - rate):min(common_length, common + rate + 1)] = False
        second_joint = float(np.exp(np.max(joint[distant]))) if distant.any() else 0.
        ambiguous = best_joint > 0 and second_joint >= .95 * best_joint
        for start, scores, percentile in curves:
            expected = common + round(start * rate)
            lower, upper = max(0, expected - round(.25 * rate)), min(len(scores), expected + round(.25 * rate) + 1)
            index = lower + int(np.argmax(scores[lower:upper]))
            matches.append({"query_start_seconds": start, "reference_start_seconds": index / rate * speed, "reference_base_seconds": (index / rate - start) * speed, "absolute_ncc": float(scores[index]), "peak_to_p99_ratio": float(scores[index]) / max(percentile, 1e-10), "unconstrained_reference_start_seconds": int(np.argmax(scores)) / rate * speed})
    bases = [item["reference_base_seconds"] for item in matches]
    strength = float(np.median([m["absolute_ncc"] for m in matches])) if matches else 0.
    spread = float(np.ptp(bases)) if bases else 1e9
    search_strength = float(np.median([np.max(scores) for _, scores, _ in curves])) if curves else 0.
    return {"speed": speed, "quality": strength / (1 + spread), "search_strength": search_strength, "windows": matches, "offset_spread_seconds": spread, "median_correlation": strength, "timing_ambiguous": ambiguous}


def align_arrays(query: np.ndarray, reference: np.ndarray, sample_rate: int = 4000, speed_min: float = .94, speed_max: float = 1.06, speed_step: float = .01, window_seconds: float = 6) -> dict:
    if not all(np.isfinite([speed_min, speed_max, speed_step, window_seconds])) or not .5 <= speed_min <= speed_max <= 2 or not .001 <= speed_step <= .1 or not 2 <= window_seconds <= 20:
        raise ValueError("Invalid speed range/step or alignment window.")
    if not np.isfinite(query).all() or not np.isfinite(reference).all():
        raise ValueError("Non-finite audio is not supported.")
    seconds = len(query) / sample_rate
    if seconds < 4 or len(reference) / sample_rate < 4:
        raise ValueError("Alignment requires at least four seconds of audio.")
    window = min(window_seconds, seconds / 2)
    available = seconds - window
    possible = [float(x) for x in np.linspace(min(1., available / 4), max(min(1., available / 4), available - min(1., available / 4)), 3)]
    starts = []
    for start in possible:
        if not starts or start >= starts[-1] + window:
            starts.append(start)
    if len(starts) < 2:
        starts = [0., seconds - window]
    # A bounded band emphasizes musical detail and suppresses rumble/DC.
    sos = butter(4, [120, min(1700, sample_rate * .45)], btype="bandpass", fs=sample_rate, output="sos")
    query = sosfiltfilt(sos, query)
    reference = sosfiltfilt(sos, reference)
    grid = np.arange(speed_min, speed_max + speed_step * .1, speed_step)
    if speed_min <= 1. <= speed_max:
        grid = np.unique(np.r_[grid, 1.])
    # Short windows tolerate the initial coarse speed error. Refinement increases
    # duration before the final full-window evidence decision.
    coarse_window = min(window, 1.) if speed_max > speed_min else window
    evaluations = [_score_rate(query, reference, sample_rate, float(speed), starts, coarse_window) for speed in grid]
    best = max(evaluations, key=lambda row: row["search_strength"])
    if speed_max > speed_min:
        radius = speed_step
        for stage in range(3):
            refined = np.linspace(max(speed_min, best["speed"] - radius), min(speed_max, best["speed"] + radius), 9)
            search_window = window if stage == 2 else min(window, 1.5 * (stage + 1))
            evaluations = [_score_rate(query, reference, sample_rate, float(speed), starts, search_window) for speed in refined]
            best = max(evaluations, key=lambda row: row["search_strength"])
            radius /= 4
    best = max(evaluations, key=lambda row: row["quality"])
    hits = best["windows"]
    strong = [hit for hit in hits if hit["absolute_ncc"] >= .12 and hit["peak_to_p99_ratio"] >= 1.5]
    passed = len(hits) >= 2 and len(strong) == len(hits) and best["median_correlation"] >= .20 and best["offset_spread_seconds"] <= .15 and not best.get("timing_ambiguous", False)
    estimated_speed, offset = best["speed"], float(np.median([m["reference_base_seconds"] for m in hits])) if hits else 0.
    if passed:
        fitted_speed, fitted_offset = np.polyfit([m["query_start_seconds"] for m in hits], [m["reference_start_seconds"] for m in hits], 1)
        if speed_min - .001 <= fitted_speed <= speed_max + .001:
            estimated_speed, offset = float(fitted_speed), float(fitted_offset)
    if abs(offset) < 1 / sample_rate:
        offset = 0.
    return {"evidence_passed": bool(passed), "speed_factor": float(estimated_speed), "reference_start_seconds": float(offset), "query_duration_seconds": seconds, "reference_duration_seconds": len(reference) / sample_rate, "sample_rate": sample_rate, "window_seconds": window, "median_absolute_ncc": best["median_correlation"], "offset_spread_seconds": best["offset_spread_seconds"], "timing_ambiguous": best.get("timing_ambiguous", False), "windows": hits, "searched_speed_range": [speed_min, speed_max], "method": "Joint multi-window waveform NCC over resampled reference speeds", "interpretation": "Heuristic same-recording evidence, not an identification probability. Pitch-only changes, key-locked stretching, covers, repeated motifs and edits need additional review."}


def verify(query: Path, reference: Path, *, query_start: float = 0., query_duration: float = 600., **options) -> dict:
    if not np.isfinite([query_start, query_duration]).all() or query_start < 0 or not 4 <= query_duration <= 600:
        raise TraceError("Verification needs a nonnegative query start and a duration of 4-600 seconds.")
    result = align_arrays(read_mono(query, start=query_start, maximum=query_duration), read_mono(reference), **options)
    result.update(query={"file": query.name, "sha256": digest(query)}, reference={"file": reference.name, "sha256": digest(reference)}, analysis_limit_seconds=600)
    result["query_selection"] = {"start_seconds": query_start, "max_duration_seconds": query_duration}
    for window in result["windows"]:
        window["source_query_start_seconds"] = query_start + window["query_start_seconds"]
    return result


def export_reference(reference: Path, alignment: dict, output: Path) -> dict:
    if not alignment.get("evidence_passed"):
        raise TraceError("Reference export requires a passing alignment report.")
    if digest(reference) != alignment.get("reference", {}).get("sha256"):
        raise TraceError("Reference hash differs from the file used in the alignment report.")
    speed = float(alignment["speed_factor"])
    start = float(alignment["reference_start_seconds"])
    duration = float(alignment["query_duration_seconds"])
    end = start + speed * duration
    if not np.isfinite([speed, start, duration]).all() or not .5 <= speed <= 2 or start < 0 or not 0 < duration <= 600 or end > alignment["reference_duration_seconds"] + .01:
        raise TraceError("The reference does not cover the complete requested interval.")
    if output.exists() or output.with_suffix(output.suffix + ".json").exists():
        raise TraceError("Reference export target already exists.")
    if output.suffix.lower() not in {".mp3", ".flac", ".wav"}:
        raise TraceError("Choose an MP3, FLAC or WAV output filename.")
    output.parent.mkdir(parents=True, exist_ok=True)
    encoder = {".mp3": ["-c:a", "libmp3lame", "-b:a", "320k"], ".flac": ["-c:a", "flac"], ".wav": ["-c:a", "pcm_s24le"]}[output.suffix.lower()]
    # Resample to a known input rate before changing playback speed.
    run_ffmpeg(["-n", "-ss", f"{start:.8f}", "-i", str(reference), "-af", f"aresample=44100,asetrate={44100 * speed:.8f},aresample=44100:filter_size=64", "-t", f"{duration:.8f}", *encoder, str(output)])
    note = {"file": output.name, "role": "reference_derived_excerpt", "not_a_separated_stem": True, "reference_file": reference.name, "reference_sha256": digest(reference), "speed_factor": speed, "reference_start_seconds": start, "seconds": duration, "sha256": digest(output)}
    save_json(output.with_suffix(output.suffix + ".json"), note)
    return note
