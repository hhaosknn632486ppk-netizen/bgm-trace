import json
from pathlib import Path
import urllib.request

import numpy as np
import pytest
import soundfile as sf

from bgm_trace.alignment import export_reference, verify
from bgm_trace.cli import main
from bgm_trace.media import TraceError, _download, safe_url


@pytest.fixture
def local_audio(tmp_path):
    rate = 16000
    samples = np.random.default_rng(11).normal(scale=.1, size=12 * rate)
    source = tmp_path / "example.wav"
    sf.write(source, samples, rate)
    return source


def test_offline_extract_and_preserve_previous_job(tmp_path, local_audio, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline workflow attempted a network request")
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    output = tmp_path / "job"
    argv = ["identify", str(local_audio), "--out", str(output), "--offline", "--separate", "never"]
    assert main(argv) == 0
    before = (output / "report.json").read_bytes()
    report = json.loads(before)
    assert report["recognition"]["status"] == "offline_prepared"
    assert report["artifacts"][0]["role"] == "source_extraction"
    assert report["artifacts"][0]["seconds"] == pytest.approx(12, abs=.01)
    assert str(tmp_path) not in before.decode()
    assert main(argv) == 2
    assert (output / "report.json").read_bytes() == before


def test_offline_rejects_url_and_uncached_separation(tmp_path, local_audio):
    assert main(["identify", "https://example.com/video", "--offline", "--out", str(tmp_path / "url")]) == 2
    assert main(["identify", str(local_audio), "--offline", "--separate", "always", "--out", str(tmp_path / "model")]) == 2
    assert not (tmp_path / "url").exists()
    assert not (tmp_path / "model").exists()


def test_verified_export_labels_role_and_checks_hash(tmp_path, local_audio):
    report = verify(local_audio, local_audio, speed_min=1., speed_max=1.)
    assert report["evidence_passed"]
    output = tmp_path / "excerpt.flac"
    note = export_reference(local_audio, report, output)
    assert note["role"] == "reference_derived_excerpt"
    assert note["not_a_separated_stem"] is True
    assert sf.info(output).duration == pytest.approx(12, abs=.01)
    assert json.loads(output.with_suffix(".flac.json").read_text())["sha256"] == note["sha256"]
    with pytest.raises(TraceError, match="already exists"):
        export_reference(local_audio, report, output)
    different = tmp_path / "different.wav"
    sf.write(different, np.zeros(16000 * 12), 16000)
    with pytest.raises(TraceError, match="hash differs"):
        export_reference(different, report, tmp_path / "wrong.mp3")


def test_unverified_or_uncovered_reference_cannot_be_exported(tmp_path, local_audio):
    with pytest.raises(TraceError, match="passing alignment"):
        export_reference(local_audio, {"evidence_passed": False}, tmp_path / "bad.mp3")
    report = verify(local_audio, local_audio, speed_min=1., speed_max=1.)
    report["reference_start_seconds"] = 2.
    with pytest.raises(TraceError, match="cover"):
        export_reference(local_audio, report, tmp_path / "uncovered.mp3")


def test_public_url_metadata_omits_credentials_and_tokens():
    url = "https://user:password@example.com/watch?v=video&token=secret&p=2#private"
    assert safe_url(url) == "https://example.com/watch?v=video&p=2"


def test_download_does_not_remove_existing_file(tmp_path):
    target = tmp_path / "existing.m4a"
    target.write_bytes(b"preserve")
    with pytest.raises(TraceError, match="already exists"):
        _download("https://example.com/file", target, 1000, "https://example.com/")
    assert target.read_bytes() == b"preserve"
