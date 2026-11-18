import json
import urllib.error

import numpy as np
import pytest
import soundfile as sf

from bgm_trace import cli, clues


@pytest.mark.parametrize("online,mode,matched,expected", [
    (True, "auto", False, True), (True, "auto", True, False),
    (True, "always", True, True), (True, "never", False, False),
    (False, "always", False, False),
])
def test_fallback_respects_result_and_network_mode(tmp_path, monkeypatch, online, mode, matched, expected):
    source = tmp_path / "input.wav"
    sf.write(source, np.random.default_rng(3).normal(scale=.1, size=8 * 16000), 16000)
    calls = []

    async def recognize(*args):
        if not matched:
            return [{"status": "no_match"}]
        return [{"status": "match", "layer": "source", "start_seconds": start, "duration_seconds": 4,
                 "track": {"id": "song", "title": "Example", "artist": "Example"}} for start in [0, 4]]

    original_collect = clues.collect
    def collect(url):
        calls.append(url)
        return original_collect("https://www.douyin.com/video/123")

    monkeypatch.setattr(cli, "recognize_file", recognize)
    monkeypatch.setattr(clues, "collect", collect)
    job = tmp_path / "job"
    assert cli.main(["identify", str(source), "--out", str(job), "--online" if online else "--offline",
                     "--separate", "never", "--clues", mode, "--source-url", "https://www.douyin.com/video/123"]) == 0
    assert bool(calls) is expected
    report = json.loads((job / "report.json").read_text())
    assert bool(report.get("source_investigations")) is expected
    assert (job / "clues.json").exists() is expected


def test_access_block_stops_public_service_requests(monkeypatch):
    calls = []
    def blocked(request, **kwargs):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, 429, "limited", {}, None)
    monkeypatch.setattr(clues.urllib.request, "urlopen", blocked)
    client = clues.PublicBilibili()
    with pytest.raises(clues.SourceUnavailable, match="http_429"):
        client.get("/first")
    with pytest.raises(clues.SourceUnavailable, match="service_stopped"):
        client.get("/second")
    assert len(calls) == 1
