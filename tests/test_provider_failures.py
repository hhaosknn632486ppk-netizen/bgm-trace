import asyncio
import json

import numpy as np
import soundfile as sf

from bgm_trace.cli import main
from bgm_trace.recognition import recognize_file, summarize


def test_rate_limit_stops_remaining_windows_and_closes_client(tmp_path, monkeypatch):
    import shazamio

    calls = []
    closed = []

    class RateLimited(Exception):
        pass

    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            closed.append(True)

    class Recognizer:
        def __init__(self, **kwargs):
            pass
        async def recognize(self, path):
            calls.append(path)
            raise RateLimited()

    monkeypatch.setattr(shazamio, "HTTPClient", Client)
    monkeypatch.setattr(shazamio, "Shazam", Recognizer)
    source = tmp_path / "source.wav"
    sf.write(source, np.full((40 * 16000, 2), .1), 16000)
    attempts = asyncio.run(recognize_file(source, "music", tmp_path))
    assert len(calls) == 1
    assert closed == [True]
    assert summarize(attempts)["availability"] == "rate_limited"
    assert not list(tmp_path.glob("clip_*.wav"))


def test_always_separates_before_recognition(tmp_path, monkeypatch):
    from bgm_trace import cli, separation

    order = []
    source = tmp_path / "input.wav"
    sf.write(source, np.random.default_rng(8).normal(scale=.1, size=8 * 16000), 16000)

    def separate(prepared, output, *args):
        order.append("separate")
        data, rate = sf.read(prepared)
        sf.write(output, data, rate)
        return {"file": output.name, "role": "model_separated_music"}

    async def recognize(path, layer, *args):
        order.append("recognize_" + layer)
        return [{"status": "error", "error": "RateLimited", "layer": layer}]

    monkeypatch.setattr(separation, "separate", separate)
    monkeypatch.setattr(cli, "recognize_file", recognize)
    output = tmp_path / "job"
    assert main(["identify", str(source), "--online", "--separate", "always", "--out", str(output)]) == 0
    assert order == ["separate", "recognize_music"]
    report = json.loads((output / "report.json").read_text())
    assert report["recognition"]["availability"] == "rate_limited"
    assert any("rate-limited" in warning for warning in report["warnings"])
