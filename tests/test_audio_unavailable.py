import json
from pathlib import Path
import urllib.error
import urllib.request

import numpy as np
import pytest
import soundfile as sf

from bgm_trace import alignment, cli, clues
from bgm_trace.media import TraceError, input_identity, run_ffmpeg


VIDEO = "https://www.bilibili.com/video/BV1VuCwBTEkV/"


def test_link_identity_survives_a_filesystem_probe_error(monkeypatch):
    def invalid_path(*args):
        raise OSError("URL cannot be probed as a local path")

    monkeypatch.setattr(Path, "is_file", invalid_path)
    assert input_identity(VIDEO + "?token=private")["url"] == VIDEO
    assert input_identity("BV1VuCwBTEkV")["url"] == VIDEO


@pytest.fixture
def source_reader(monkeypatch):
    calls = []

    def collect(url):
        calls.append(url)
        return clues.analyze({
            "source_url": url,
            "documents": [{"id": "answer", "kind": "comment", "text": "曲名：Unlisted Lantern",
                           "url": url, "is_uploader": True}],
            "coverage": [{"area": "comments", "url": url, "status": "partial", "items_read": 1,
                          "stop_reason": "synthetic sample"}],
        })

    def unexpected(*args, **kwargs):
        pytest.fail("No audio is available; audio recognition/verification or real networking must not run")

    monkeypatch.setattr(clues, "collect", collect)
    monkeypatch.setattr(cli, "recognize_file", unexpected)
    monkeypatch.setattr(alignment, "verify", unexpected)
    monkeypatch.setattr(urllib.request, "urlopen", unexpected)
    return calls


@pytest.mark.parametrize("source,expected_url", [
    (VIDEO + "?token=private-test-token#private", VIDEO),
    ("BV1VuCwBTEkV", VIDEO),
    ("https://b23.tv/EXAMPLE", "https://b23.tv/EXAMPLE"),
])
def test_acquisition_failure_keeps_link_and_finds_text_leads(tmp_path, monkeypatch, source_reader, source, expected_url):
    def blocked(*args):
        raise urllib.error.HTTPError(source, 403, "private-test-token", {}, None)

    monkeypatch.setattr(cli, "acquire", blocked)
    job = tmp_path / "failed-download"
    assert cli.main(["identify", source, "--online", "--out", str(job), "--separate", "always",
                     "--reference", str(tmp_path / "unused-reference.wav")]) == 2
    raw = (job / "report.json").read_text(encoding="utf-8")
    report = json.loads(raw)
    assert source_reader == [expected_url]
    assert report["source"]["url"] == expected_url
    assert report["audio_preparation"]["failed_stage"] == "acquire"
    assert report["recognition"]["status"] == "audio_unavailable"
    assert report["recognition"]["availability"] == "not_requested"
    assert not report["attempts"] and not report["recognition"]["candidates"] and not report["artifacts"]
    assert report["source_investigations"][0]["status"] == "leads_found"
    lead_report = json.loads((job / "clues.json").read_text(encoding="utf-8"))
    assert all(lead["audio_verified"] is False for lead in lead_report["clues"])
    assert report["next_steps"] and (job / "report.txt").exists()
    assert "private-test-token" not in raw and str(tmp_path) not in raw
    assert not (job / "music.mp3").exists() and not (job / "alignment.json").exists()


@pytest.fixture
def video_without_audio(tmp_path):
    source = tmp_path / "video-without-audio.mp4"
    run_ffmpeg(["-n", "-f", "lavfi", "-i", "color=c=black:s=16x16:r=1", "-t", "2",
                "-an", "-c:v", "mpeg4", str(source)])
    return source


@pytest.mark.parametrize("online,mode,expected", [(True, "auto", True), (True, "never", False), (False, "always", False)])
def test_real_video_without_audio_preserves_network_choice(tmp_path, video_without_audio, source_reader, online, mode, expected):
    job = tmp_path / "no-audio"
    assert cli.main(["identify", str(video_without_audio), "--out", str(job),
                     "--online" if online else "--offline", "--separate", "never", "--clues", mode,
                     "--source-url", VIDEO]) == 2
    report = json.loads((job / "report.json").read_text(encoding="utf-8"))
    assert report["audio_preparation"]["status"] == "unavailable"
    assert report["audio_preparation"]["failed_stage"] == "extract"
    assert report["source"]["kind"] == "local" and report["source"]["sha256"]
    assert report["recognition"]["availability"] == "not_requested"
    assert bool(source_reader) is expected
    assert (job / "clues.json").exists() is expected
    assert not report["artifacts"]
    assert (job / "report.txt").exists()


def test_source_failure_does_not_hide_the_audio_failure(tmp_path, monkeypatch, source_reader):
    def no_audio(*args):
        raise TraceError("No public audio stream.")

    def failed_reader(*args):
        raise RuntimeError("remote-reader-private-detail")

    monkeypatch.setattr(cli, "acquire", no_audio)
    monkeypatch.setattr(clues, "collect", failed_reader)
    job = tmp_path / "both-unavailable"
    assert cli.main(["identify", VIDEO, "--online", "--out", str(job)]) == 2
    raw = (job / "report.json").read_text(encoding="utf-8")
    report = json.loads(raw)
    assert report["error"] == "No public audio stream."
    assert report["recognition"]["status"] == "audio_unavailable"
    assert report["warnings"] and report["next_steps"]
    assert "remote-reader-private-detail" not in raw
    assert (job / "report.txt").exists()


def test_local_followup_preserves_failed_job_and_original_source(tmp_path, monkeypatch, source_reader):
    acquire = cli.acquire

    def local_only(value, *args):
        if value == VIDEO:
            raise TraceError("No public audio stream.")
        return acquire(value, *args)

    monkeypatch.setattr(cli, "acquire", local_only)
    failed = tmp_path / "failed-link"
    assert cli.main(["identify", VIDEO, "--online", "--out", str(failed)]) == 2
    previous = (failed / "report.json").read_bytes()
    source_reader.clear()

    source = tmp_path / "user-supplied-recording.wav"
    sf.write(source, np.random.default_rng(5).normal(scale=.1, size=8 * 16000), 16000)

    async def recognize(*args):
        return [{"status": "no_match"}]

    monkeypatch.setattr(cli, "recognize_file", recognize)
    recovered = tmp_path / "local-followup"
    assert cli.main(["identify", str(source), "--online", "--separate", "never", "--out", str(recovered),
                     "--source-url", VIDEO]) == 0
    report = json.loads((recovered / "report.json").read_text(encoding="utf-8"))
    assert report["audio_preparation"]["status"] == "ready"
    assert report["recognition"]["status"] == "unrecognized"
    assert report["artifacts"][0]["role"] == "source_extraction"
    assert source_reader == [VIDEO]
    assert (failed / "report.json").read_bytes() == previous
