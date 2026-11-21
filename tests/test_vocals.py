import json

import numpy as np
import pytest
import soundfile as sf

from bgm_trace import cli, separation
from bgm_trace.media import TraceError


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "input.wav"
    sf.write(path, np.random.default_rng(80).normal(scale=.1, size=8 * 16000), 16000)
    return path


@pytest.mark.parametrize("role", ["song", "mixed", "unknown", "none"])
def test_no_match_does_not_remove_musical_or_uncertain_vocals(source, tmp_path, monkeypatch, role):
    calls = []
    async def recognize(path, layer, *args):
        calls.append(layer)
        return [{"status": "no_match", "layer": layer}]
    def forbidden(*args):
        pytest.fail("No-match must not trigger removal of musical/uncertain vocals")
    monkeypatch.setattr(cli, "recognize_file", recognize)
    monkeypatch.setattr(separation, "separate", forbidden)
    out = tmp_path / "job"
    assert cli.main(["identify", str(source), "--out", str(out), "--online", "--voice-role", role, "--clues", "never"]) == 0
    report = json.loads((out / "report.json").read_text())
    assert calls == ["source"]
    assert report["vocal_assessment"]["recognition_input"] == "source.wav"
    assert not (out / "music.wav").exists()


def test_reviewed_speech_is_separated_before_any_fingerprint(source, tmp_path, monkeypatch):
    order = []
    def separate(path, target, *args):
        order.append("separate")
        data, rate = sf.read(path)
        sf.write(target, data, rate)
        return {"file": target.name, "role": "model_separated_music"}
    async def recognize(path, layer, *args):
        order.append(layer)
        return [{"status": "no_match", "layer": layer}]
    monkeypatch.setattr(separation, "separate", separate)
    monkeypatch.setattr(cli, "recognize_file", recognize)
    out = tmp_path / "job"
    assert cli.main(["identify", str(source), "--out", str(out), "--online", "--voice-role", "speech",
                     "--voice-evidence", "Narration interrupts the continuous instrumental", "--clues", "never"]) == 0
    assert order == ["separate", "music"]
    report = json.loads((out / "report.json").read_text())
    assert report["vocal_assessment"]["evidence"].startswith("Narration")
    assert (out / "source.wav").exists()


def test_failed_speech_separation_falls_back_with_warning(source, tmp_path, monkeypatch):
    def unavailable(*args):
        raise TraceError("No cached checkpoint.")
    layers = []
    async def recognize(path, layer, *args):
        layers.append(layer)
        return [{"status": "no_match", "layer": layer}]
    monkeypatch.setattr(separation, "separate", unavailable)
    monkeypatch.setattr(cli, "recognize_file", recognize)
    out = tmp_path / "job"
    assert cli.main(["identify", str(source), "--out", str(out), "--online", "--voice-role", "speech", "--clues", "never"]) == 0
    report = json.loads((out / "report.json").read_text())
    assert layers == ["source"]
    assert any("still contains" in warning for warning in report["warnings"])


def test_listening_export_failure_does_not_skip_music_recognition(source, tmp_path, monkeypatch):
    def separate(path, target, *args):
        data, rate = sf.read(path)
        sf.write(target, data, rate)
        return {"file": target.name, "role": "model_separated_music"}
    def broken_export(path, target):
        target.write_bytes(b"partial")
        raise TraceError("Export unavailable")
    layers = []
    async def recognize(path, layer, *args):
        layers.append(layer)
        return [{"status": "no_match", "layer": layer}]
    monkeypatch.setattr(separation, "separate", separate)
    monkeypatch.setattr(cli, "listening_copy", broken_export)
    monkeypatch.setattr(cli, "recognize_file", recognize)
    out = tmp_path / "job"
    assert cli.main(["identify", str(source), "--out", str(out), "--online", "--voice-role", "speech", "--clues", "never"]) == 0
    assert layers == ["music"] and (out / "music.wav").exists()
    assert not (out / "music.mp3").exists()


@pytest.mark.parametrize("role", ["song", "mixed"])
def test_conflicting_forced_removal_rejected_before_work(source, tmp_path, role):
    out = tmp_path / "job"
    assert cli.main(["identify", str(source), "--out", str(out), "--online", "--voice-role", role, "--separate", "always"]) == 2
    assert not out.exists()


def test_offline_speech_does_not_fetch_weights(source, tmp_path):
    out = tmp_path / "job"
    assert cli.main(["identify", str(source), "--out", str(out), "--offline", "--voice-role", "speech"]) == 2
    assert not out.exists()


def test_alternate_media_does_not_inherit_narration_assessment(source, tmp_path, monkeypatch):
    def prepare(args, report, job):
        cli.extract(source, job / "source.wav")
        report["audio_preparation"] = {"status": "ready", "relationship_to_requested_source": "unverified_alternative"}
        return True
    def forbidden(*args):
        pytest.fail("Alternate needs its own assessment")
    monkeypatch.setattr(cli, "_prepare_audio", prepare)
    monkeypatch.setattr(separation, "separate", forbidden)
    out = tmp_path / "job"
    assert cli.main(["identify", str(source), "--out", str(out), "--offline", "--voice-role", "speech", "--model-repo", str(tmp_path)]) == 0
    report = json.loads((out / "report.json").read_text())
    assert report["vocal_assessment"]["role"] == "unknown"
    assert report["requested_vocal_assessment"]["role"] == "speech"
