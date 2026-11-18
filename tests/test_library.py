import json
import shutil

import numpy as np
import pytest
import soundfile as sf

from bgm_trace import library
from bgm_trace.alignment import export_reference, verify
from bgm_trace.cli import main
from bgm_trace.media import TraceError, digest, run_ffmpeg


@pytest.fixture
def sounds(tmp_path):
    rate = 16000
    target = np.random.default_rng(901).normal(0, .13, 22 * rate)
    unrelated = np.random.default_rng(17).normal(0, .13, 22 * rate)
    reference, other, query = [tmp_path / name for name in ("target.wav", "other.wav", "video.wav")]
    sf.write(reference, target, rate)
    sf.write(other, unrelated, rate)
    # Only the middle of this source contains the requested music.
    sf.write(query, np.r_[unrelated[:7 * rate], target[3 * rate:15 * rate], unrelated[7 * rate:]], rate)
    return reference, other, query


def test_native_aac_with_mp3_name_and_optional_listening_copy(tmp_path, sounds):
    reference, _, query = sounds
    wrong_name = tmp_path / "cached.mp3"
    run_ffmpeg(["-n", "-i", str(reference), "-c:a", "aac", "-b:a", "128k", "-f", "ipod", str(wrong_name)])
    result = library.import_file(wrong_name, tmp_path / "job", title="Catalog claim", query=query, start=7, duration=12, mp3=True)
    assert result["status"] == "verified"
    assert result["source_claim"]["basis"] == "caller_supplied_catalog_claim"
    media = result["candidates"][0]["media"]
    assert media["container"] == "M4A" and media["codec"] == "aac" and media["extension_corrected"]
    assert media["complete_audio_decoded"] and media["seconds"] == pytest.approx(22, abs=.1)
    assert digest(tmp_path / "job/reference.m4a") == digest(wrong_name)
    assert result["artifacts"][0]["byte_identical_copy"] and not result["artifacts"][0]["reencoded"]
    assert result["artifacts"][1]["role"] == "transcoded_listening_copy"
    assert library.inspect_audio(tmp_path / "job/reference-listening.mp3")["codec"] == "mp3"
    alignment = json.loads((tmp_path / "job/alignment.json").read_text())
    assert alignment["reference"]["file"] == "reference.m4a"
    assert alignment["query_selection"]["start_seconds"] == 7
    assert str(tmp_path) not in (tmp_path / "job/library-report.json").read_text()


def test_interval_positions_and_reference_excerpt(tmp_path, sounds):
    reference, _, query = sounds
    result = verify(query, reference, query_start=7, query_duration=12, speed_min=1, speed_max=1)
    assert result["evidence_passed"]
    assert result["reference_start_seconds"] == pytest.approx(3, abs=.01)
    assert all(w["source_query_start_seconds"] == w["query_start_seconds"] + 7 for w in result["windows"])
    output = tmp_path / "excerpt.flac"
    export_reference(reference, result, output)
    assert sf.info(output).duration == pytest.approx(12, abs=.01)
    assert verify(output, reference, speed_min=1, speed_max=1)["reference_start_seconds"] == pytest.approx(3, abs=.01)


def watch_setup(tmp_path):
    cache = tmp_path / "music"
    cache.mkdir()
    baseline = tmp_path / "before.json"
    library.snapshot(cache, baseline)
    return cache, baseline


def watch(cache, baseline, job, **kwargs):
    return library.collect(cache, baseline, job, settle=.1, poll=.05, timeout=1, **kwargs)


def test_changed_files_only_and_unique_waveform_selection(tmp_path, sounds):
    reference, other, query = sounds
    cache = tmp_path / "music"
    cache.mkdir()
    shutil.copy(reference, cache / "old.wav")
    (cache / "private-config.json").write_text("not music")
    (cache / "subdirectory").mkdir()
    shutil.copy(reference, cache / "subdirectory/hidden.wav")
    baseline = tmp_path / "before.json"
    library.snapshot(cache, baseline)
    shutil.copy(reference, cache / "download.wav")
    shutil.copy(other, cache / "unrelated.wav")
    (cache / "corrupt.mp3").write_bytes(b"not an audio file")
    result = watch(cache, baseline, tmp_path / "job", query=query, start=7, duration=12)
    assert result["status"] == "verified" and result["selected_file"] == "download.wav"
    assert {r["file"] for r in result["candidates"]} == {"download.wav", "unrelated.wav", "corrupt.mp3"}
    assert digest(tmp_path / "job/reference.wav") == digest(reference)
    assert (cache / "private-config.json").read_text() == "not music"


@pytest.mark.parametrize("matching", [False, True])
def test_two_distinct_candidates_are_not_silently_picked(tmp_path, sounds, matching):
    reference, other, query = sounds
    cache, baseline = watch_setup(tmp_path)
    shutil.copy(reference, cache / "one.wav")
    if matching:
        samples, rate = sf.read(reference)
        sf.write(cache / "two.wav", samples * .5, rate)
    else:
        shutil.copy(other, cache / "two.wav")
    result = watch(cache, baseline, tmp_path / "job", query=query if matching else None, start=7, duration=12)
    assert result["status"] == "ambiguous" and not result["artifacts"]
    assert not list((tmp_path / "job").glob("reference*"))


def test_byte_identical_duplicates_and_existing_cache(tmp_path, sounds):
    reference, _, _ = sounds
    cache, baseline = watch_setup(tmp_path)
    shutil.copy(reference, cache / "one.wav")
    shutil.copy(reference, cache / "duplicate.wav")
    result = watch(cache, baseline, tmp_path / "first")
    assert result["status"] == "acquired_unverified"
    second_baseline = tmp_path / "after.json"
    library.snapshot(cache, second_baseline)
    result = library.collect(cache, second_baseline, tmp_path / "second", timeout=0)
    assert result["status"] == "no_new_stable_media" and not result["candidates"]
    result = library.import_file(cache / "one.wav", tmp_path / "explicit")
    assert result["status"] == "acquired_unverified"


def test_nonmatch_is_saved_without_false_success(tmp_path, sounds):
    _, other, query = sounds
    job = tmp_path / "job"
    assert main(["library-import", str(other), "--query", str(query), "--start", "7", "--duration", "12", "--out", str(job)]) == 2
    report = json.loads((job / "library-report.json").read_text())
    assert report["status"] == "no_verified_match" and not report["artifacts"]


def test_snapshot_binding_bounds_and_no_overwrite(tmp_path, sounds):
    reference, _, _ = sounds
    cache, baseline = watch_setup(tmp_path)
    with pytest.raises(FileExistsError):
        library.snapshot(cache, baseline)
    other = tmp_path / "another"
    other.mkdir()
    with pytest.raises(TraceError, match="different music directory"):
        watch(other, baseline, tmp_path / "mismatch")
    data = json.loads(baseline.read_text())
    data["files"]["../escape.mp3"] = {"size": 1, "mtime_ns": 1}
    baseline.write_text(json.dumps(data))
    with pytest.raises(TraceError, match="filename"):
        watch(cache, baseline, tmp_path / "traversal")
    data["cache_root"] = {"invalid": "path"}
    baseline.write_text(json.dumps(data))
    with pytest.raises(TraceError, match="identity"):
        watch(cache, baseline, tmp_path / "invalid-root")
    job = tmp_path / "kept"
    job.mkdir()
    (job / "precious.txt").write_text("keep")
    with pytest.raises(TraceError, match="not empty"):
        library.import_file(reference, job)
    assert (job / "precious.txt").read_text() == "keep"
    with pytest.raises(TraceError, match="outside"):
        library._job(cache / "output", cache.resolve())


def test_candidate_limit_and_changing_download(tmp_path, sounds, monkeypatch):
    reference, _, _ = sounds
    cache, baseline = watch_setup(tmp_path)
    shutil.copy(reference, cache / "one.wav")
    shutil.copy(reference, cache / "two.wav")
    assert watch(cache, baseline, tmp_path / "limited", max_candidates=1)["status"] == "candidate_limit"
    actual = library.inventory
    counter = 0
    def growing(directory):
        nonlocal counter
        result = actual(directory)
        counter += 1
        result["one.wav"]["size"] += counter
        return result
    monkeypatch.setattr(library, "inventory", growing)
    result = library.collect(cache, baseline, tmp_path / "growing", timeout=.2, settle=.1, poll=.05)
    assert result["status"] == "no_new_stable_media" and not result["artifacts"]


def test_file_mutation_during_inspection_or_copy_is_rejected(tmp_path, sounds, monkeypatch):
    reference, other, _ = sounds
    original_inspect = library.inspect_audio
    def changed(path):
        media = original_inspect(path)
        shutil.copyfile(other, path)
        return media
    monkeypatch.setattr(library, "inspect_audio", changed)
    with pytest.raises(TraceError, match="changed while"):
        library.inspect_candidate(reference, None, 0, 12)
    monkeypatch.setattr(library, "inspect_audio", original_inspect)
    candidate = library.inspect_candidate(reference, None, 0, 12)
    candidate["sha256"] = "0" * 64
    job = tmp_path / "job"
    job.mkdir()
    with pytest.raises(TraceError, match="changed during"):
        library._copy_selected(reference, candidate, job)
    assert not (job / "reference.wav").exists()
    (job / "reference.wav").write_bytes(b"keep existing")
    with pytest.raises(FileExistsError):
        library._copy_selected(reference, candidate, job)
    assert (job / "reference.wav").read_bytes() == b"keep existing"


@pytest.mark.parametrize("option,value", [("--start", "nan"), ("--start", "-1"), ("--duration", "inf"), ("--duration", "601")])
def test_invalid_intervals_do_not_create_jobs(tmp_path, option, value):
    job = tmp_path / "job"
    assert main(["library-import", "unused.mp3", "--out", str(job), option, value]) == 2
    assert not job.exists()


def test_video_and_invalid_audio_rejected(tmp_path, sounds):
    reference, _, _ = sounds
    video = tmp_path / "not-just-audio.mp4"
    run_ffmpeg(["-n", "-f", "lavfi", "-i", "color=size=32x32:rate=1:duration=1", "-i", str(reference), "-shortest", "-c:v", "mpeg4", "-c:a", "aac", str(video)])
    with pytest.raises(TraceError, match="not a video"):
        library.inspect_audio(video)
    bad = tmp_path / "broken.mp3"
    bad.write_bytes(b"not audio")
    with pytest.raises(TraceError, match="decodable"):
        library.import_file(bad, tmp_path / "bad")
    assert json.loads((tmp_path / "bad/library-report.json").read_text())["status"] == "error"


def test_optional_transcode_failure_retains_native_evidence(tmp_path, sounds, monkeypatch):
    reference, _, _ = sounds
    def broken(source, target):
        target.write_bytes(b"partial")
        raise TraceError("transcoding failed")
    monkeypatch.setattr(library, "listening_copy", broken)
    result = library.import_file(reference, tmp_path / "job", mp3=True)
    assert result["status"] == "acquired_unverified" and result["warnings"]
    assert len(result["artifacts"]) == 1
    assert digest(tmp_path / "job/reference.wav") == digest(reference)
    assert not (tmp_path / "job/reference-listening.mp3").exists()


def test_source_clue_identity_is_bound_without_copying_private_text(tmp_path, sounds):
    reference, _, _ = sounds
    clues = tmp_path / "clues.json"
    clues.write_text('{"private_comment": "do not publish"}')
    result = library.import_file(reference, tmp_path / "job", clue_report=clues,
                                 source_urls=["https://user:secret@example.com/watch?v=abc&token=private"])
    assert result["source_context"]["clue_report"] == {"file": "clues.json", "sha256": digest(clues)}
    assert result["source_context"]["urls"] == ["https://example.com/watch?v=abc"]
    assert "do not publish" not in json.dumps(result)
    assert "secret" not in json.dumps(result) and str(tmp_path) not in json.dumps(result)
