from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import urllib.request

import numpy as np
import pytest
import soundfile as sf

from bgm_trace.cli import main
from bgm_trace.lyrics import _serialize, assemble, parse_windows
from bgm_trace.media import TraceError


def segment(text="violet pebbles greet the paper moon", *, weak=None, silence=0., start=0.):
    words = [NS(word=word, start=start + i * .4, end=start + i * .4 + .3,
                probability=.3 if i == weak else .95) for i, word in enumerate(text.split())]
    return NS(text=text, start=start, end=words[-1].end, words=words,
              avg_logprob=-.1, no_speech_prob=silence, compression_ratio=1.)


def run(text="violet pebbles greet the paper moon", **kwargs):
    return {"model_index": 0, "window_index": 0, "layer": "original", "status": "completed",
            "segments": _serialize([segment(text, **kwargs)], 12., 8.)}


def test_disagreement_and_low_score_visible_without_correcting_lyrics():
    first = run(weak=4)
    second = run("violet pebbles cross the paper moon")
    second["model_index"] = 1
    drafts, queries = assemble([first, second], [(12., 20.)])
    assert "[? greet]" in drafts[0]["text"]
    assert "[? paper]" in drafts[0]["text"]
    assert len(drafts[0]["variants"]) == 2
    assert drafts[0]["words"][2]["start_seconds"] == pytest.approx(12.8)
    assert not queries  # No exact phrase may bridge the uncertain words.
    assert "[?" not in first["segments"][0]["text"]  # Raw evidence remains unchanged.


def test_stable_queries_have_no_artist_restriction_but_are_unverified():
    first, second = run(), run()
    second["model_index"] = 1
    drafts, queries = assemble([first, second], [(12., 20.)])
    assert "[?" not in drafts[0]["text"]
    assert len(queries) == 1
    assert queries[0]["scope"] == "unrestricted_artist"
    assert "unverified" in queries[0]["basis"]


def test_single_pass_silence_and_repetition_do_not_become_certain_lyrics():
    drafts, queries = assemble([run()], [(12., 20.)])
    assert all(word["uncertain"] for word in drafts[0]["words"])
    assert not queries
    suspected = run("echo echo echo echo echo echo echo echo", silence=.9)
    drafts, queries = assemble([suspected, deepcopy(suspected)], [(12., 20.)])
    assert all("possible_repetition_hallucination" in word["uncertainty_reasons"] for word in drafts[0]["words"])
    assert all("possible_no_speech" in word["uncertainty_reasons"] for word in drafts[0]["words"])
    assert not queries


def test_missing_word_and_time_mismatch_do_not_create_false_exact_phrase():
    first, second = run(), run("violet tiny pebbles greet the paper moon")
    drafts, _ = assemble([first, second], [(12., 20.)])
    assert "possible_missing_word" in drafts[0]["words"][0]["uncertainty_reasons"]
    assert "possible_missing_word" in drafts[0]["words"][1]["uncertainty_reasons"]
    late = run(start=3.)
    drafts, queries = assemble([first, late], [(12., 20.)])
    assert all(word["uncertain"] for word in drafts[0]["words"])
    assert not queries


def test_query_does_not_bridge_asr_segments_with_offset_word_starts():
    first = run()
    one, two = segment("violet pebbles"), segment("paper moon", start=1.)
    two.start = .9  # Segment boundary and first-word start need not coincide.
    first["segments"] = _serialize([one, two], 12., 8.)
    second = deepcopy(first)
    second["model_index"] = 1
    drafts, queries = assemble([first, second], [(12., 20.)])
    assert not any(word["uncertain"] for word in drafts[0]["words"])
    assert not queries  # Two 2-word phrases are not one 4-word quotation.


@pytest.mark.parametrize("value", ["nan:12", "0:inf", "-1:10", "0:46", "2:3", "0:10:20", "bad"])
def test_invalid_window_rejected(value):
    with pytest.raises(TraceError):
        parse_windows([value])


@pytest.fixture
def assets(tmp_path, monkeypatch):
    source = tmp_path / "private-input.wav"
    sf.write(source, np.random.default_rng(4).normal(scale=.1, size=24 * 16000), 16000)
    models = []
    for index in range(2):
        folder = tmp_path / f"model-{index}"
        folder.mkdir()
        for name in ["model.bin", "config.json", "tokenizer.json"]:
            (folder / name).write_text(f"synthetic fixture {index}")
        models.append(folder)
    calls = []
    class Engine:
        def __init__(self, path, **kwargs):
            assert kwargs["local_files_only"] is True
            assert Path(path).is_dir()
        def transcribe(self, audio, **kwargs):
            assert isinstance(audio, np.ndarray) and audio.dtype == np.float32
            assert kwargs["condition_on_previous_text"] is False
            assert "initial_prompt" not in kwargs
            calls.append(kwargs)
            return iter([segment()]), NS(language="en")
    monkeypatch.setitem(sys.modules, "faster_whisper", NS(WhisperModel=Engine))
    def forbidden(*args, **kwargs):
        pytest.fail("Local lyric workflow must not request network access")
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    return source, models, calls


def test_local_cli_preserves_inputs_reports_absolute_timing_and_no_overwrite(assets, tmp_path):
    source, models, calls = assets
    original = source.read_bytes()
    out = tmp_path / "lyrics"
    argv = ["lyrics", str(source), "--model", str(models[0]), "--comparison-model", str(models[1]),
            "--out", str(out), "--window", "12:20", "--language", "en"]
    assert main(argv) == 0
    report = json.loads((out / "lyrics.json").read_text())
    assert report["status"] == "draft_unverified"
    assert report["drafts"][0]["words"][0]["start_seconds"] == 12.
    assert report["search_queries"][0]["scope"] == "unrestricted_artist"
    assert str(tmp_path) not in (out / "lyrics.json").read_text()
    assert "NOT verified" in (out / "lyrics.txt").read_text(encoding="utf-8")
    assert len(calls) == 2 and source.read_bytes() == original
    before = (out / "lyrics.json").read_bytes()
    assert main(argv) == 2
    assert (out / "lyrics.json").read_bytes() == before


def test_duplicates_do_not_add_model_or_layer_evidence(assets, tmp_path):
    source, models, calls = assets
    for path in models[0].iterdir():
        (models[1] / path.name).write_bytes(path.read_bytes())
    out = tmp_path / "lyrics"
    assert main(["lyrics", str(source), "--model", str(models[0]), "--comparison-model", str(models[1]),
                 "--analysis-audio", str(source), "--out", str(out), "--window", "0:8"]) == 0
    report = json.loads((out / "lyrics.json").read_text())
    assert len(calls) == 1 and len(report["models"]) == 1
    assert not report["search_queries"]
    assert all(word["uncertain"] for word in report["drafts"][0]["words"])


def test_incomplete_models_and_uncovered_analysis_audio_do_not_run(assets, tmp_path):
    source, models, calls = assets
    out = tmp_path / "lyrics"
    assert main(["lyrics", str(source), "--model", str(tmp_path), "--out", str(out), "--window", "0:8"]) == 2
    short = tmp_path / "short.wav"
    sf.write(short, np.zeros(5 * 16000), 16000)
    assert main(["lyrics", str(source), "--model", str(models[0]), "--analysis-audio", str(short),
                 "--out", str(out), "--window", "0:8"]) == 2
    assert not calls and not out.exists()


def test_engine_failure_keeps_report_and_sanitizes_error(assets, tmp_path, monkeypatch):
    source, models, _ = assets
    class Broken:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("private-path-or-token")
    monkeypatch.setitem(sys.modules, "faster_whisper", NS(WhisperModel=Broken))
    out = tmp_path / "lyrics"
    assert main(["lyrics", str(source), "--model", str(models[0]), "--out", str(out), "--window", "0:8"]) == 2
    report = json.loads((out / "lyrics.json").read_text())
    assert report["status"] == "asr_unavailable"
    assert not report["search_queries"]
    assert "private-path-or-token" not in (out / "lyrics.json").read_text()
