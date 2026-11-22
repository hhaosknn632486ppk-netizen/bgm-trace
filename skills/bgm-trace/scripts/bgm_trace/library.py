"""Receive ordinary local music downloads; this module does not access app accounts."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import stat
import subprocess
import time

from .alignment import verify
from .media import TraceError, digest, ffmpeg, listening_copy, read_mono, safe_url, save_json

MEDIA_SUFFIXES = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus", ".mp4", ".webm", ".mka"}
MAX_FILES = 10000
MAX_BYTES = 256 * 1024 * 1024


def _regular(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISREG(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 0x400)


def _signature(path: Path) -> dict:
    if not _regular(path):
        raise TraceError("Library media must be a regular file, not a link or reparse point.")
    info = path.stat()
    if not 0 < info.st_size <= MAX_BYTES:
        raise TraceError("Library media must be nonempty and at most 256 MiB.")
    return {"size": info.st_size, "mtime_ns": info.st_mtime_ns}


def inventory(cache: Path) -> dict:
    cache = cache.expanduser().resolve(strict=True)
    if not cache.is_dir():
        raise TraceError("Choose the app's music-only download/cache directory.")
    files = {}
    for index, path in enumerate(cache.iterdir()):
        if index >= MAX_FILES:
            raise TraceError("Music directory is too large; choose a narrower directory.")
        if path.suffix.lower() not in MEDIA_SUFFIXES:
            continue
        try:
            if _regular(path):
                info = path.stat()
                files[path.name] = {"size": info.st_size, "mtime_ns": info.st_mtime_ns}
        except FileNotFoundError:
            continue
    return files


def snapshot(cache: Path, output: Path) -> dict:
    cache = cache.expanduser().resolve(strict=True)
    result = {"schema_version": 1, "kind": "music_library_snapshot", "cache_root": str(cache),
              "created_at": datetime.now(timezone.utc).isoformat(), "files": inventory(cache)}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    return {"status": "snapshot_saved", "file_count": len(result["files"]), "private_manifest": True}


def _baseline(cache: Path, path: Path) -> dict:
    if path.stat().st_size > 4 * 1024 * 1024:
        raise TraceError("Snapshot is too large.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("kind") != "music_library_snapshot" or data.get("schema_version") != 1:
        raise TraceError("Unsupported music snapshot.")
    root = data.get("cache_root")
    if not isinstance(root, str) or not root or not Path(root).is_absolute():
        raise TraceError("Invalid snapshot music-directory identity.")
    if Path(root).resolve() != cache:
        raise TraceError("Snapshot belongs to a different music directory.")
    files = data.get("files")
    if not isinstance(files, dict) or len(files) > MAX_FILES:
        raise TraceError("Invalid snapshot file inventory.")
    for name, row in files.items():
        if not isinstance(name, str) or not name or any(c in name for c in "/\\:") or name in {".", ".."}:
            raise TraceError("Invalid snapshot filename.")
        if not isinstance(row, dict) or any(type(row.get(key)) is not int or row[key] < 0 for key in ("size", "mtime_ns")):
            raise TraceError("Invalid snapshot file metadata.")
    return files


def inspect_audio(path: Path) -> dict:
    """Probe actual bytes, then decode the complete supported (<=600 s) audio."""
    _signature(path)
    try:
        probe = subprocess.run([ffmpeg(), "-hide_banner", "-nostdin", "-protocol_whitelist", "file,pipe",
                                "-i", str(path), "-map", "0:a:0", "-t", "0", "-f", "null", "-"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TraceError("Library media probe did not complete.") from exc
    header = probe.stderr.decode("utf-8", errors="replace").split("Stream mapping:")[0]
    if probe.returncode:
        raise TraceError("Candidate does not contain decodable ordinary audio.")
    audio = re.search(r"Stream #0:\d+[^\n]*?Audio: ([^,\s]+)[^\n]*?, (\d+) Hz, ([^,\n]+)", header)
    if not audio or any("Video:" in line and "attached pic" not in line for line in header.splitlines() if "Stream #0:" in line):
        raise TraceError("Library import expects audio, not a video or encrypted asset.")
    with path.open("rb") as stream:
        magic = stream.read(64)
        payload_magic = magic[:4]
        if magic[:3] == b"ID3" and len(magic) >= 10 and all(byte < 0x80 for byte in magic[6:10]):
            id3_size = ((magic[6] & 0x7F) << 21) | ((magic[7] & 0x7F) << 14) | ((magic[8] & 0x7F) << 7) | (magic[9] & 0x7F)
            offset = 10 + id3_size + (10 if magic[5] & 0x10 else 0)
            stream.seek(offset)
            payload_magic = stream.read(4)
    has_mp3_sync = len(payload_magic) >= 2 and payload_magic[0] == 0xFF and (payload_magic[1] & 0xE0) == 0xE0
    has_adts_sync = len(payload_magic) >= 2 and payload_magic[0] == 0xFF and (payload_magic[1] & 0xF6) == 0xF0
    formats = [(magic[4:8] == b"ftyp", ".m4a", "M4A"),
               (magic[:4] == b"fLaC", ".flac", "FLAC"),
               (magic[:4] in {b"RIFF", b"RF64"} and magic[8:12] == b"WAVE", ".wav", "WAVE"),
               (magic[:4] == b"OggS" and (audio[1] == "opus" or b"OpusHead" in magic), ".opus", "Ogg Opus"),
               (magic[:4] == b"OggS", ".ogg", "Ogg"),
               (magic[:4] == b"\x1a\x45\xdf\xa3" and b"webm" in magic.lower(), ".webm", "WebM"),
               (magic[:4] == b"\x1a\x45\xdf\xa3", ".mka", "Matroska"),
               (audio[1] == "mp3" and (magic[:3] == b"ID3" or has_mp3_sync), ".mp3", "MP3"),
               (audio[1] == "aac" and has_adts_sync, ".aac", "ADTS AAC")]
    detected = next(((suffix, container) for valid, suffix, container in formats if valid), None)
    if detected is None:
        raise TraceError("Unsupported native audio container; use the app's ordinary audio export.")
    samples = read_mono(path, maximum=601)
    seconds = len(samples) / 4000
    if seconds > 600:
        raise TraceError("Library import currently supports complete tracks up to 600 seconds.")
    return {"extension": detected[0], "container": detected[1], "codec": audio[1],
            "sample_rate": int(audio[2]), "channel_layout": audio[3], "seconds": seconds,
            "original_extension": path.suffix.lower(), "extension_corrected": path.suffix.lower() != detected[0],
            "complete_audio_decoded": True}


def inspect_candidate(path: Path, query: Path | None, start: float, duration: float) -> dict:
    before = _signature(path)
    identity = digest(path)
    media = inspect_audio(path)
    result = {"file": path.name, "sha256": identity, "media": media}
    if query is not None:
        result["verification"] = verify(query, path, query_start=start, query_duration=duration)
    if _signature(path) != before or digest(path) != identity:
        raise TraceError("Candidate changed while being inspected; wait for the download to finish.")
    return result


def _job(output: Path, cache: Path | None = None) -> Path:
    job = output.expanduser().resolve()
    if cache is not None and (job == cache or cache in job.parents):
        raise TraceError("Keep the output directory outside the watched music directory.")
    if job.exists() and any(job.iterdir()):
        raise TraceError("Library job directory is not empty; choose a new directory.")
    job.mkdir(parents=True, exist_ok=True)
    return job


def _report(title: str, artist: str, platform: str, source_urls: list[str] | None, clue_report: Path | None) -> dict:
    result = {"schema_version": 1, "kind": "music_library_recovery", "created_at": datetime.now(timezone.utc).isoformat(),
            "source_claim": {"title": title, "artist": artist, "platform": platform, "basis": "caller_supplied_catalog_claim"},
            "candidates": [], "artifacts": [], "note": "Waveform matching supports the same recording; it does not authenticate catalog metadata, authorship or licensing."}
    result["source_context"] = {"urls": [safe_url(url) for url in (source_urls or [])]}
    if clue_report is not None:
        result["source_context"]["clue_report"] = {"file": clue_report.name, "sha256": digest(clue_report)}
    return result


def _save(report: dict, job: Path) -> dict:
    save_json(job / "library-report.json", report)
    return report


def _copy_selected(source: Path, candidate: dict, job: Path) -> list[dict]:
    target = job / ("reference" + candidate["media"]["extension"])
    before = _signature(source)
    hashed = hashlib.sha256()
    copied = 0
    created = False
    try:
        with source.open("rb") as incoming, target.open("xb") as outgoing:
            created = True
            for block in iter(lambda: incoming.read(1024 * 1024), b""):
                copied += len(block)
                if copied > MAX_BYTES:
                    raise TraceError("Candidate exceeded the file-size limit during copying.")
                outgoing.write(block)
                hashed.update(block)
        if hashed.hexdigest() != candidate["sha256"] or _signature(source) != before:
            raise TraceError("Candidate changed during copying; no reference was retained.")
    except Exception:
        if created:
            target.unlink(missing_ok=True)
        raise
    artifacts = [{"file": target.name, "role": "native_library_audio", "sha256": candidate["sha256"], "bytes": copied,
                  "byte_identical_copy": True, "reencoded": False}]
    return artifacts


def _select(report: dict, paths: dict[str, Path], job: Path, query: Path | None, mp3: bool) -> dict:
    valid = [row for row in report["candidates"] if "media" in row]
    eligible = [row for row in valid if row.get("verification", {}).get("evidence_passed")] if query else valid
    # Byte-identical duplicates are one recording; different matching recordings remain ambiguous.
    unique = {row["sha256"]: row for row in eligible}
    if len(unique) != 1:
        report["status"] = "ambiguous" if len(unique) > 1 else "no_verified_match" if query and valid else "no_valid_audio"
        report["next_step"] = "Review candidates and the selected video interval; use library-import on the exact UI-selected file if appropriate."
        return _save(report, job)
    chosen = next(iter(unique.values()))
    report["selected_file"] = chosen["file"]
    report["status"] = "verified" if query else "acquired_unverified"
    try:
        report["artifacts"] = _copy_selected(paths[chosen["file"]], chosen, job)
    except (OSError, TraceError) as exc:
        report.update(status="copy_failed", error=str(exc) if isinstance(exc, TraceError) else "Could not save the selected local audio.")
        return _save(report, job)
    if mp3:
        listening = job / "reference-listening.mp3"
        existed = listening.exists()
        try:
            listening_copy(job / report["artifacts"][0]["file"], listening)
            report["artifacts"].append({"file": listening.name, "role": "transcoded_listening_copy", "sha256": digest(listening)})
        except (OSError, TraceError):
            if not existed:
                listening.unlink(missing_ok=True)
            report["warnings"] = ["Native audio is retained, but the optional MP3 listening copy failed."]
    if "verification" in chosen:
        alignment = dict(chosen["verification"])
        alignment["reference"] = {"file": report["artifacts"][0]["file"], "sha256": chosen["sha256"]}
        save_json(job / "alignment.json", alignment)
    return _save(report, job)


def import_file(source: Path, output: Path, *, title: str = "", artist: str = "", platform: str = "jianying",
                query: Path | None = None, start: float = 0., duration: float = 600., mp3: bool = False,
                source_urls: list[str] | None = None, clue_report: Path | None = None) -> dict:
    source = source.expanduser().absolute()
    _signature(source)
    job = _job(output)
    report = _report(title, artist, platform, source_urls, clue_report)
    report["mode"] = "explicit_local_file"
    try:
        report["candidates"].append(inspect_candidate(source, query, start, duration))
        return _select(report, {source.name: source}, job, query, mp3)
    except (TraceError, ValueError) as exc:
        report.update(status="error", error=str(exc))
        _save(report, job)
        raise


def collect(cache: Path, baseline: Path, output: Path, *, title: str = "", artist: str = "", platform: str = "jianying",
            query: Path | None = None, start: float = 0., duration: float = 600., mp3: bool = False,
            timeout: float = 120., settle: float = 2., poll: float = .5, max_candidates: int = 8,
            source_urls: list[str] | None = None, clue_report: Path | None = None) -> dict:
    if not all(math.isfinite(x) for x in (timeout, settle, poll)) or not 0 <= timeout <= 600 or not .1 <= settle <= 30 or not .05 <= poll <= 5 or not 1 <= max_candidates <= 32:
        raise TraceError("Invalid bounded library-watch timing or candidate limit.")
    cache = cache.expanduser().resolve(strict=True)
    baseline_files = _baseline(cache, baseline)
    job = _job(output, cache)
    report = _report(title, artist, platform, source_urls, clue_report)
    report.update(mode="changed_files_since_snapshot", snapshot_file=baseline.name)
    deadline = time.monotonic() + timeout
    previous = None
    stable_since = time.monotonic()
    while True:
        now = time.monotonic()
        current = inventory(cache)
        changed = {name: info for name, info in current.items() if baseline_files.get(name) != info}
        if changed != previous:
            stable_since = now
            previous = changed
        if len(changed) > max_candidates:
            report.update(status="candidate_limit", candidate_count=len(changed), next_step="Choose the exact music file from this operation with library-import.")
            return _save(report, job)
        if changed and now - stable_since >= settle:
            paths = {name: cache / name for name in sorted(changed)}
            for name, path in paths.items():
                try:
                    report["candidates"].append(inspect_candidate(path, query, start, duration))
                except (OSError, TraceError, ValueError) as exc:
                    report["candidates"].append({"file": name, "status": "unavailable", "reason": str(exc) if isinstance(exc, TraceError) else "Candidate is no longer readable."})
            return _select(report, paths, job, query, mp3)
        if now >= deadline:
            report.update(status="no_new_stable_media", next_step="Finish the ordinary app download and collect again with a new job. Already cached audio needs an explicit library-import; unchanged files are not inferred to be this download.")
            return _save(report, job)
        time.sleep(min(poll, max(0., deadline - now)))
