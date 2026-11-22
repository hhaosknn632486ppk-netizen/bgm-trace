import json
from pathlib import Path
import shutil
import urllib.error

import numpy as np
import pytest
import soundfile as sf

from bgm_trace import alignment, cli, media


VIDEO = "https://www.bilibili.com/video/BV1VuCwBTEkV/"


@pytest.fixture
def recording(tmp_path, monkeypatch):
    source = tmp_path / "synthetic.wav"
    sf.write(source, np.random.default_rng(8).normal(scale=.1, size=8 * 16000), 16000)
    def forbidden(*args, **kwargs):
        pytest.fail("Controlled acquisition tests must not access the network")
    monkeypatch.setattr(media.urllib.request, "urlopen", forbidden)
    return source


def metadata_api(monkeypatch, tracks):
    def get(url):
        if "/view?" in url:
            return {"code": 0, "data": {"title": "Synthetic video", "pages": [{"cid": 123}]}}
        return {"code": 0, "data": {"dash": {"audio": tracks}}}
    monkeypatch.setattr(media, "_get_json", get)


@pytest.mark.parametrize("first_failure", ["invalid_media", "connection_error"])
def test_public_backup_stream_is_tried_and_decoded(tmp_path, monkeypatch, recording, first_failure):
    metadata_api(monkeypatch, [{"id": 1, "bandwidth": 100, "baseUrl": "https://cdn.example/bad?token=secret",
                               "backup_url": ["https://cdn.example/good?token=secret"]}])
    calls = []
    def download(url, target, limit, referer):
        calls.append(url)
        if "/bad?" in url:
            if first_failure == "connection_error":
                raise OSError("private-network-detail")
            target.write_bytes(b"<html>not audio</html>" * 100)
        else:
            shutil.copyfile(recording, target)
    monkeypatch.setattr(media, "_download", download)
    def general(*args):
        pytest.fail("A valid native backup should avoid the general extractor")
    monkeypatch.setattr(media, "_acquire_ytdlp", general)
    source, info = media.acquire(VIDEO, tmp_path / "job")
    assert len(calls) == 2 and media.digest(source) == media.digest(recording)
    assert [row["status"] for row in info["stream_attempts"]] == ["failed", "ready"]
    assert info["acquisition_attempts"][-1]["method"] == "bilibili_public_audio"
    assert "secret" not in json.dumps(info) and "private-network-detail" not in json.dumps(info)


def test_another_audio_format_is_used_when_top_stream_fails(tmp_path, monkeypatch, recording):
    metadata_api(monkeypatch, [{"id": 1, "bandwidth": 100, "baseUrl": "https://cdn.example/top"},
                               {"id": 2, "bandwidth": 50, "base_url": "https://cdn.example/other"}])
    def download(url, target, *args):
        if url.endswith("top"):
            raise OSError("unavailable")
        shutil.copyfile(recording, target)
    monkeypatch.setattr(media, "_download", download)
    source, info = media.acquire(VIDEO, tmp_path / "job")
    assert info["audio_id"] == 2 and media.digest(source) == media.digest(recording)


def test_missing_standalone_audio_falls_back_to_a_combined_video(tmp_path, monkeypatch, recording):
    import yt_dlp
    combined = tmp_path / "combined.mp4"
    media.run_ffmpeg(["-n", "-f", "lavfi", "-i", "color=c=black:s=16x16:r=1", "-i", str(recording),
                      "-t", "2", "-c:v", "mpeg4", "-c:a", "aac", str(combined)])
    metadata_api(monkeypatch, [])
    requests = []
    class Downloader:
        def __init__(self, options):
            self.options = options
            self.target = Path(options["outtmpl"].replace("%(ext)s", "mp4"))
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def extract_info(self, url, download):
            requests.append(url)
            shutil.copyfile(combined, self.target)
            return {"title": "Synthetic combined video", "webpage_url": VIDEO}
        def prepare_filename(self, info):
            return str(self.target)
    monkeypatch.setattr(yt_dlp, "YoutubeDL", Downloader)
    source, info = media.acquire(VIDEO, tmp_path / "job")
    assert requests == [VIDEO]
    assert [row["status"] for row in info["acquisition_attempts"]] == ["failed", "ready"]
    assert info["kind"] == "yt-dlp"
    output = tmp_path / "decoded.wav"
    assert media.extract(source, output)["seconds"] == pytest.approx(2, abs=.1)


@pytest.mark.parametrize("failure", ["rate_limit", "access_limit", "size_limit", "invalid_page"])
def test_acquisition_limits_do_not_trigger_another_same_source_route(tmp_path, monkeypatch, recording, failure):
    def stopped(*args):
        if failure == "rate_limit":
            raise urllib.error.HTTPError(VIDEO, 429, "private", {}, None)
        raise media.AcquisitionStop(failure)
    def general(*args):
        pytest.fail("A stop condition must not fall through to another extractor")
    monkeypatch.setattr(media, "_acquire_bilibili", stopped)
    monkeypatch.setattr(media, "_acquire_ytdlp", general)
    with pytest.raises(media.AcquisitionError) as error:
        media.acquire(VIDEO, tmp_path / "job")
    assert len(error.value.attempts) == 1 and error.value.attempts[0]["status"] == "failed"
    assert "private" not in str(error.value)


def test_alternate_recording_is_analyzed_without_claiming_original_identity(tmp_path, monkeypatch, recording):
    acquire = cli.acquire
    def first_fails(value, *args):
        if value == VIDEO:
            raise media.AcquisitionError("primary unavailable", [{"method": "fixture", "status": "failed"}])
        return acquire(value, *args)
    async def recognize(*args):
        return [{"status": "match", "layer": "source", "start_seconds": start, "duration_seconds": 4,
                 "track": {"id": "demo", "title": "Synthetic song", "artist": "Demo"}} for start in [0, 4]]
    monkeypatch.setattr(cli, "acquire", first_fails)
    monkeypatch.setattr(cli, "recognize_file", recognize)
    monkeypatch.setattr(alignment, "verify", lambda *args: {"evidence_passed": True, "speed_factor": 1., "reference_start_seconds": 0.})
    job = tmp_path / "job"
    assert cli.main(["identify", VIDEO, "--alternate-input", str(recording), "--online", "--separate", "never",
                     "--clues", "never", "--out", str(job), "--reference", str(recording)]) == 0
    report = json.loads((job / "report.json").read_text(encoding="utf-8"))
    assert report["requested_source"]["url"] == VIDEO
    assert [row["status"] for row in report["input_attempts"]] == ["failed", "ready"]
    assert report["recognition"]["status"] == "candidate_consensus"
    assert report["audio_preparation"]["relationship_to_requested_source"] == "unverified_alternative"
    assert report["verification"]["input_relationship"] == "unverified_alternative"
    assert "alternate" in (job / "report.txt").read_text(encoding="utf-8")


def test_decode_failure_uses_local_alternate_without_overwriting_evidence(tmp_path, recording):
    broken = tmp_path / "broken.mp4"
    broken.write_text("not media", encoding="utf-8")
    job = tmp_path / "job"
    assert cli.main(["identify", str(broken), "--alternate-input", str(recording), "--offline",
                     "--separate", "never", "--out", str(job)]) == 0
    report = json.loads((job / "report.json").read_text(encoding="utf-8"))
    assert report["input_attempts"][0]["failed_stage"] == "extract"
    assert report["audio_preparation"]["selected_input_index"] == 1
    assert sf.info(job / "source.wav").duration == pytest.approx(8, abs=.01)
    assert broken.read_text() == "not media"


def test_offline_rejects_network_alternatives_before_starting(tmp_path, recording):
    job = tmp_path / "job"
    assert cli.main(["identify", str(recording), "--offline", "--out", str(job), "--alternate-input", VIDEO]) == 2
    assert not job.exists()


def test_successful_primary_input_skips_all_alternatives(tmp_path, monkeypatch, recording):
    acquire = cli.acquire
    calls = []
    def observed(value, *args):
        calls.append(value)
        return acquire(value, *args)
    monkeypatch.setattr(cli, "acquire", observed)
    broken = tmp_path / "unused.mp4"
    broken.write_text("not media")
    assert cli.main(["identify", str(recording), "--alternate-input", str(broken), "--offline",
                     "--separate", "never", "--out", str(tmp_path / "job")]) == 0
    assert calls == [str(recording)]


def test_ytdlp_guards_none_progress_playlists_and_prefers_requested_filepath(tmp_path, monkeypatch, recording):
    import yt_dlp

    captured = {}
    actual_file = tmp_path / "job" / "acquire-yt-dlp" / "download.wav"

    class Downloader:
        def __init__(self, options):
            captured["options"] = options
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def extract_info(self, url, download):
            # Progress dict may contain downloaded_bytes=None; guard must not crash.
            captured["options"]["progress_hooks"][0]({"downloaded_bytes": None})
            shutil.copyfile(recording, actual_file)
            return {
                "title": "Synthetic track",
                "webpage_url": "https://example.com/watch?v=abc",
                "requested_downloads": [{"filepath": str(actual_file)}],
            }
        def prepare_filename(self, info):
            return str(actual_file.with_suffix(".webm"))

    monkeypatch.setattr(yt_dlp, "YoutubeDL", Downloader)
    source, info = media.acquire("https://example.com/watch?v=abc", tmp_path / "job")
    assert source == actual_file and info["kind"] == "yt-dlp"
    # Playlist entry triggers AcquisitionStop inside match_filter before downloading.
    with pytest.raises(media.AcquisitionStop, match="Playlists"):
        captured["options"]["match_filter"]({"playlist_autonumber": 1}, incomplete=False)
