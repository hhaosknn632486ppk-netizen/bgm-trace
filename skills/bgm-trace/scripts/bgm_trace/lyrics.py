"""Local ASR drafts with visible uncertainty; never a song-identification result."""
from __future__ import annotations

from copy import deepcopy
from difflib import SequenceMatcher
import gc
import math
from pathlib import Path
import re

import numpy as np

from . import __version__
from .media import TraceError, digest, read_mono, save_json


def parse_windows(values: list[str]) -> list[tuple[float, float]]:
    if not 1 <= len(values) <= 8:
        raise TraceError("Choose 1-8 lyric windows, each 4-45 seconds long.")
    result = []
    for value in values:
        try:
            start, end = map(float, value.split(":"))
        except ValueError as exc:
            raise TraceError("Lyric windows use START:END in seconds.") from exc
        if not all(map(math.isfinite, [start, end])) or start < 0 or not 4 <= end - start <= 45:
            raise TraceError("Lyric windows need a nonnegative start and a duration of 4-45 seconds.")
        if (start, end) not in result:
            result.append((start, end))
    return result


def _number(value) -> float | None:
    if value is None:
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _token(text: str) -> str:
    return "".join(re.findall(r"\w+", text.casefold()))


def _repetitive(text: str) -> bool:
    tokens = [_token(word) for word in text.split() if _token(word)]
    # A caution flag, not a deletion rule: actual refrains may repeat too.
    return len(tokens) >= 8 and len(set(tokens)) / len(tokens) < .4


def _serialize(segments, offset: float, duration: float) -> list[dict]:
    output = []
    for segment in segments:
        start, end = _number(segment.start), _number(segment.end)
        timing_bad = start is None or end is None or not 0 <= start < end <= duration + .1
        start = min(duration, max(0., start or 0.))
        end = min(duration, max(start, end or start))
        logprob = _number(segment.avg_logprob)
        silence = _number(segment.no_speech_prob)
        compression = _number(segment.compression_ratio)
        reasons = []
        if timing_bad:
            reasons.append("invalid_timing")
        if silence is not None and silence > .6:
            reasons.append("possible_no_speech")
        if logprob is None or logprob < -1.:
            reasons.append("weak_segment_score")
        if (compression is not None and compression > 2.4) or _repetitive(segment.text):
            reasons.append("possible_repetition_hallucination")
        words = []
        for word in segment.words or []:
            left, right, probability = _number(word.start), _number(word.end), _number(word.probability)
            flags = list(reasons)
            if left is None or right is None or not 0 <= left < right <= duration + .1:
                flags.append("invalid_timing")
            left = min(duration, max(0., start if left is None else left))
            right = min(duration, max(left, left if right is None else right))
            if probability is None or probability < .65 or probability > 1.:
                flags.append("weak_word_score")
            words.append({"text": word.word, "segment_index": len(output), "start_seconds": offset + left,
                          "end_seconds": offset + right, "asr_probability": probability,
                          "uncertainty_reasons": sorted(set(flags))})
        if not words and segment.text.strip():
            words.append({"text": segment.text, "segment_index": len(output), "start_seconds": offset + start,
                          "end_seconds": offset + end, "asr_probability": None,
                          "uncertainty_reasons": sorted(set(reasons + ["missing_word_evidence"]))})
        output.append({"text": segment.text, "start_seconds": offset + start, "end_seconds": offset + end,
                       "avg_logprob": logprob, "no_speech_prob": silence, "compression_ratio": compression,
                       "words": words})
    return output


def _words(run: dict) -> list[dict]:
    return [word for segment in run["segments"] for word in segment["words"] if word["text"].strip()]


def assemble(runs: list[dict], windows: list[tuple[float, float]]) -> tuple[list[dict], list[dict]]:
    """Retain a primary original-audio draft and all alternate readings, not majority-vote truth."""
    drafts, queries = [], []
    seen_queries = set()
    for index, (start, end) in enumerate(windows):
        peers = [run for run in runs if run["window_index"] == index and run["status"] == "completed"]
        originals = [run for run in peers if run["layer"] == "original"]
        if not originals:
            drafts.append({"window_index": index, "start_seconds": start, "end_seconds": end,
                           "text": "[unclear: original-audio transcription unavailable]", "words": [], "variants": []})
            continue
        primary = originals[0]
        words = deepcopy(_words(primary))
        # Matching across layers/models is stability evidence, not independent votes or calibrated confidence.
        others = [peer for peer in peers if peer is not primary]
        for word in words:
            if not others:
                word["uncertainty_reasons"].append("single_pass_unreviewed")
        for peer in others:
            alternate = _words(peer)
            matched = set()
            matcher = SequenceMatcher(a=[_token(word["text"]) for word in words],
                                      b=[_token(word["text"]) for word in alternate], autojunk=False)
            blocks = matcher.get_matching_blocks()
            for block in blocks:
                for shift in range(block.size):
                    left, right = words[block.a + shift], alternate[block.b + shift]
                    if abs(left["start_seconds"] - right["start_seconds"]) <= 2.:
                        matched.add(block.a + shift)
                        if right["uncertainty_reasons"]:
                            left["uncertainty_reasons"].append("weak_alternate_evidence")
            for tag, left, right, _, _ in matcher.get_opcodes():
                if tag == "insert":
                    # A word missing from the primary reading must not create a false exact phrase.
                    for position in {left - 1, right}:
                        if 0 <= position < len(words):
                            words[position]["uncertainty_reasons"].append("possible_missing_word")
            for position, word in enumerate(words):
                if position not in matched:
                    word["uncertainty_reasons"].append("transcription_disagreement")
        for word in words:
            word["uncertainty_reasons"] = sorted(set(word["uncertainty_reasons"]))
            word["uncertain"] = bool(word["uncertainty_reasons"])
        marked = " ".join(f"[? {word['text'].strip()}]" if word["uncertain"] else word["text"].strip() for word in words)
        drafts.append({"window_index": index, "start_seconds": start, "end_seconds": end,
                       "text": marked or "[unclear: no reliable transcription]", "words": words,
                       "variants": [{"model_index": run["model_index"], "layer": run["layer"],
                                     "text": " ".join(seg["text"].strip() for seg in run["segments"])} for run in peers]})
        # Never bridge an uncertain word, a long silence, or an ASR segment boundary.
        spans, current = [], []
        for word in words:
            if word["uncertain"] or (current and (word["segment_index"] != current[-1]["segment_index"] or
                                                      word["start_seconds"] - current[-1]["end_seconds"] > 1.5)):
                if current:
                    spans.append(current)
                current = []
            if not word["uncertain"]:
                current.append(word)
        if current:
            spans.append(current)
        for span in spans:
            chosen = span[:8]
            if len(chosen) < 3:
                continue
            phrase = " ".join(word["text"].strip().strip('"') for word in chosen)
            if phrase.casefold() in seen_queries:
                continue
            seen_queries.add(phrase.casefold())
            queries.append({"query": f'"{phrase}" lyrics', "window_index": index,
                            "start_seconds": chosen[0]["start_seconds"], "end_seconds": chosen[-1]["end_seconds"],
                            "scope": "unrestricted_artist", "basis": "ASR-stable, unverified; review against original before searching"})
    return drafts, queries[:8]


def _write(report: dict, out: Path) -> None:
    save_json(out / "lyrics.json", report)
    lines = ["BGM Trace lyric draft — NOT verified lyrics or song identification",
             "[? word] = uncertain; [unclear] = unavailable. Unmarked words are ASR-stable, not confirmed.",
             "All variants are machine hypotheses; scores/agreement do not prove correctness.",
             "Timestamps refer to the supplied input file, not automatically to the source video's timeline.", ""]
    for draft in report["drafts"]:
        lines += [f"{draft['start_seconds']:.2f}–{draft['end_seconds']:.2f}s: {draft['text']}"]
        for word in draft["words"]:
            if word["uncertain"]:
                lines.append(f"  {word['start_seconds']:.2f}–{word['end_seconds']:.2f}s [? {word['text'].strip()}]: " + ", ".join(word["uncertainty_reasons"]))
        for variant in draft["variants"]:
            lines.append(f"  UNREVIEWED variant, model {variant['model_index']}, {variant['layer']}: {variant['text'] or '[unclear]'}")
        lines.append("")
    lines += ["Suggested queries (no web searches were executed):"]
    lines += [item["query"] for item in report["search_queries"]] or ["No stable phrase selected; review audio/variants manually."]
    lines += ["", *report["warnings"]]
    (out / "lyrics.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def transcribe(source: Path, out: Path, model: Path, window_values: list[str], *,
               comparison_model: Path | None = None, analysis_audio: Path | None = None,
               language: str | None = None, device: str = "cpu", compute_type: str = "int8") -> dict:
    windows = parse_windows(window_values)
    if not source.is_file() or (analysis_audio is not None and not analysis_audio.is_file()):
        raise TraceError("Lyrics require existing local audio/video files; URLs are not fetched.")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise TraceError("Lyric output must be a new or empty directory; earlier evidence is preserved.")
    models = list(dict.fromkeys(path.expanduser().resolve() for path in [model, comparison_model] if path is not None))
    for path in models:
        if not all((path / name).is_file() for name in ["model.bin", "config.json", "tokenizer.json"]):
            raise TraceError("Use a trusted, complete local faster-whisper model directory (model.bin, config.json, tokenizer.json). No automatic model download.")
    report = {"schema_version": 1, "tool_version": __version__, "status": "draft_unverified",
              "source": {"file": source.name, "sha256": digest(source)}, "models": [], "runs": [],
              "windows": [{"start_seconds": start, "end_seconds": end} for start, end in windows],
              "time_origin": "supplied_input_file", "drafts": [], "search_queries": [],
              "warnings": ["ASR is fallible on music, reverb, screaming and instrumental passages. Repetition/silence flags are heuristics.",
                           "Singing, rap and musical spoken samples belong to the song. ASR speech detection does not classify voice origin.",
                           "Model/layer agreement is not independent song-identification evidence. Review the original, then search without artist restrictions and verify candidate audio."]}
    layers = [("original", source)]
    if analysis_audio is not None:
        identity = {"file": analysis_audio.name, "sha256": digest(analysis_audio), "role": "analysis_only_vocal_estimate"}
        report["analysis_audio"] = identity
        if identity["sha256"] != report["source"]["sha256"]:
            layers.append(("analysis_vocals", analysis_audio))
        else:
            report["warnings"].append("Identical analysis audio skipped; duplicates do not add evidence.")
        report["warnings"].append("Analysis audio alignment is supplied by the caller. Selected lengths are checked; equal lengths do not prove alignment or origin.")
    inputs = {}
    for index, (start, end) in enumerate(windows):
        for layer, path in layers:
            audio = read_mono(path, rate=16000, maximum=end - start, start=start).astype(np.float32)
            if abs(len(audio) / 16000 - (end - start)) > .1:
                raise TraceError("A requested lyric window is not fully covered by every input; check timestamps and aligned analysis audio.")
            inputs[index, layer] = audio
    out.mkdir(parents=True, exist_ok=True)
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        report["status"] = "asr_unavailable"
        report["warnings"].append("Install bgm-trace[lyrics] or the skill's requirements-lyrics.txt in the chosen environment.")
        _write(report, out)
        return report
    seen_models = set()
    for path in models:
        identity = {"name": path.name, "model_sha256": digest(path / "model.bin"),
                    "tokenizer_sha256": digest(path / "tokenizer.json"), "config_sha256": digest(path / "config.json")}
        key = tuple(identity[name] for name in ["model_sha256", "tokenizer_sha256", "config_sha256"])
        if key in seen_models:
            report["warnings"].append("Identical model copy skipped; duplicate weights do not add evidence.")
            continue
        seen_models.add(key)
        model_index = len(report["models"])
        report["models"].append(identity)
        engine = None
        try:
            engine = WhisperModel(str(path), device=device, compute_type=compute_type,
                                  cpu_threads=6, local_files_only=True)
            for index, (start, end) in enumerate(windows):
                for layer, _ in layers:
                    run = {"model_index": model_index, "window_index": index, "layer": layer, "segments": []}
                    try:
                        segments, info = engine.transcribe(inputs[index, layer], language=language, task="transcribe",
                                                          beam_size=5, temperature=0, condition_on_previous_text=False,
                                                          vad_filter=False, word_timestamps=True)
                        run["segments"] = _serialize(segments, start, end - start)
                        run.update(status="completed", language=info.language)
                    except Exception as exc:
                        run.update(status="error", error=type(exc).__name__)
                    report["runs"].append(run)
        except Exception as exc:
            report["warnings"].append(f"Model {model_index} could not load ({type(exc).__name__}); no download/retry performed.")
            report["runs"].append({"model_index": model_index, "window_index": -1, "layer": "original", "status": "error", "segments": []})
        finally:
            del engine
            gc.collect()
    report["settings"] = {"engine": "faster-whisper", "device": device, "compute_type": compute_type,
                          "word_score_caution_threshold": .65, "condition_on_previous_text": False,
                          "vad_filter": False, "artist_or_lyric_prompt": None, "network": "none"}
    completed = sum(run["status"] == "completed" for run in report["runs"])
    if completed != len(report["runs"]):
        report["status"] = "partial_draft" if completed else "asr_unavailable"
    report["drafts"], report["search_queries"] = assemble(report["runs"], windows)
    if report["status"] == "draft_unverified" and not any(draft["words"] for draft in report["drafts"]):
        report["status"] = "no_transcript"
    _write(report, out)
    return report
