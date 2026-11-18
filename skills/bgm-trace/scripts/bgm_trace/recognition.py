from __future__ import annotations

import asyncio
from collections import defaultdict
import math
from pathlib import Path

import numpy as np
import soundfile as sf


def windows(seconds: float, count: int = 3, length: float = 12) -> list[tuple[float, float]]:
    if not math.isfinite(seconds) or seconds < 1:
        return []
    if not 1 <= count <= 8 or not 4 <= length <= 30:
        raise ValueError("Use 1-8 windows, each 4-30 seconds long.")
    length = min(length, seconds)
    available = seconds - length
    margin = min(4., available / 4)
    starts = np.linspace(margin, max(margin, available - margin), count)
    return [(float(start), float(length)) for start in sorted(set(np.round(starts, 4)))]


def summarize(attempts: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for attempt in attempts:
        if attempt.get("status") == "match":
            grouped[attempt["track"]["id"]].append(attempt)
    candidates = []
    for track_id, hits in grouped.items():
        unique = {}
        for hit in hits:
            unique.setdefault(round(hit["start_seconds"], 3), hit)
        # Repeated transforms/services at one timestamp are still one observation.
        independent = []
        last_end = -1.
        for start, hit in sorted(unique.items()):
            if start >= last_end - .01:
                independent.append(start)
                last_end = start + hit["duration_seconds"]
        rates = [1 + hit["track"]["timeskew"] for hit in hits if hit["track"].get("timeskew") is not None]
        candidates.append({**hits[0]["track"], "distinct_positions": len(unique), "independent_windows": len(independent), "positions_seconds": sorted(unique), "layers": sorted({h["layer"] for h in hits}), "separated_positions": len({h["start_seconds"] for h in hits if h["layer"] == "music"}), "suggested_speed": float(np.median(rates)) if rates else None})
    candidates.sort(key=lambda item: (item["independent_windows"], item["separated_positions"], item["distinct_positions"]), reverse=True)
    supported = [c for c in candidates if c["independent_windows"] >= 2]
    status = "unrecognized" if not candidates else "single_candidate"
    if len(supported) == 1:
        status = "candidate_consensus"
    elif len(supported) > 1:
        status = "multiple_candidates"
    errors = [a for a in attempts if a.get("status") == "error"]
    availability = "rate_limited" if any(a.get("error") == "RateLimited" for a in errors) else "partial_error" if errors else "completed" if attempts else "not_requested"
    return {"status": status, "availability": availability, "candidates": candidates, "note": "Repeated matches are candidate evidence, not a calibrated probability or proof of the requested sound layer."}


async def recognize_file(path: Path, layer: str, job: Path, count: int = 3, length: float = 12, timeout: float = 30) -> list[dict]:
    from aiohttp_retry import ExponentialRetry
    from shazamio import HTTPClient, Shazam

    data, rate = sf.read(path, dtype="float32", always_2d=True)
    attempts = []
    retry = ExponentialRetry(attempts=2, statuses={500, 502, 503, 504}, max_timeout=2)
    async with HTTPClient(retry_options=retry) as client:
        recognizer = Shazam(http_client=client)
        for index, (start, duration) in enumerate(windows(len(data) / rate, count, length)):
            samples = data[round(start * rate):round((start + duration) * rate)]
            attempt = {"layer": layer, "start_seconds": start, "duration_seconds": duration, "provider": "shazam"}
            if not len(samples) or float(np.sqrt(np.mean(samples ** 2))) < 1e-5:
                attempts.append({**attempt, "status": "skipped_silence"})
                continue
            clip = job / f"clip_{layer}_{index}.wav"
            sf.write(clip, samples, rate)
            try:
                result = await asyncio.wait_for(recognizer.recognize(str(clip)), timeout=timeout)
                track = result.get("track") or {}
                if not track.get("key") or not track.get("title"):
                    attempt["status"] = "no_match"
                else:
                    matches = result.get("matches") or []
                    matched = next((m for m in matches if str(m.get("id")) == str(track["key"])), {})
                    attempt.update(status="match", track={"id": str(track["key"]), "title": track["title"], "artist": track.get("subtitle", ""), "url": track.get("url"), "reference_offset_seconds": matched.get("offset"), "timeskew": matched.get("timeskew")})
            except Exception as exc:
                attempt.update(status="error", error=type(exc).__name__)
            finally:
                clip.unlink(missing_ok=True)
            attempts.append(attempt)
            if attempt.get("error") == "RateLimited":
                break
            if index + 1 < count:
                await asyncio.sleep(2.)
    return attempts
