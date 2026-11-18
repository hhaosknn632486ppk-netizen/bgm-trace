from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
import soundfile as sf


class TraceError(RuntimeError):
    """An actionable error suitable for a CLI without a traceback."""


class AcquisitionStop(TraceError):
    """Stop retries for access/rate limits, invalid selections or output limits."""


class AcquisitionError(TraceError):
    def __init__(self, message: str, attempts: list[dict]):
        super().__init__(message)
        self.attempts = attempts


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def ffmpeg() -> str:
    override = os.environ.get("BGM_TRACE_FFMPEG")
    if override:
        if not Path(override).is_file():
            raise TraceError("BGM_TRACE_FFMPEG must point to an existing FFmpeg executable.")
        return override
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise TraceError("Install FFmpeg or imageio-ffmpeg, or set BGM_TRACE_FFMPEG.") from exc


def run_ffmpeg(arguments: list[str], *, capture: bool = False) -> bytes:
    try:
        completed = subprocess.run(
            [ffmpeg(), "-v", "error", "-nostdin", "-protocol_whitelist", "file,pipe", *arguments],
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.PIPE, timeout=600, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TraceError(f"FFmpeg did not complete ({type(exc).__name__}).") from exc
    if completed.returncode:
        # Decoder stderr can contain local paths and signed URLs. Keep it out of reports.
        raise TraceError("FFmpeg could not decode/process the media; check its format and audio stream.")
    return completed.stdout if capture else b""


def extract(source: Path, target: Path, start: float = 0, duration: float = 90) -> dict:
    if not np.isfinite(start) or start < 0 or not np.isfinite(duration) or not 0 < duration <= 600:
        raise TraceError("Use a nonnegative start and a duration in (0, 600] seconds.")
    if target.exists():
        raise TraceError("Extraction target already exists; choose a new job directory.")
    run_ffmpeg(["-n", "-ss", f"{start:.8f}", "-i", str(source), "-t", f"{duration:.8f}", "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_f32le", str(target)])
    info = sf.info(target)
    if info.frames < info.samplerate:
        raise TraceError("The selected interval contains less than one second of audio.")
    return {"file": target.name, "role": "source_extraction", "seconds": info.duration, "sample_rate": info.samplerate, "channels": info.channels, "sha256": digest(target)}


def read_mono(path: Path, rate: int = 4000, maximum: float = 600) -> np.ndarray:
    payload = run_ffmpeg(["-i", str(path), "-t", str(maximum), "-vn", "-ac", "1", "-ar", str(rate), "-f", "f32le", "pipe:1"], capture=True)
    result = np.frombuffer(payload, dtype="<f4").astype(np.float64)
    if not result.size or not np.isfinite(result).all():
        raise TraceError("Audio is empty or contains non-finite samples.")
    return result


def listening_copy(source: Path, target: Path) -> None:
    run_ffmpeg(["-n", "-i", str(source), "-c:a", "libmp3lame", "-b:a", "320k", str(target)])


def safe_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    kept = [(key, value) for key, value in urllib.parse.parse_qsl(parts.query) if key in {"v", "p", "id", "modal_id", "aweme_id", "music_id"}]
    host = parts.hostname or ""
    return urllib.parse.urlunsplit((parts.scheme, host, parts.path, urllib.parse.urlencode(kept), ""))


def input_identity(value: str) -> dict:
    """Keep a safe source identity even if acquisition never returns metadata."""
    local = Path(value).expanduser()
    try:
        if local.is_file():
            return {"kind": "local", "name": local.name}
    except OSError:
        # Long or otherwise invalid filesystem paths can still be valid URLs.
        pass
    if re.fullmatch(r"BV[0-9A-Za-z]{10}", value):
        return {"kind": "bilibili", "url": "https://www.bilibili.com/video/" + value + "/"}
    try:
        parts = urllib.parse.urlsplit(value)
        if parts.scheme in {"http", "https"} and parts.hostname:
            return {"kind": "url", "url": safe_url(value)}
    except ValueError:
        pass
    return {"kind": "unknown"}


def _get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def _download(url: str, target: Path, limit: int, referer: str) -> None:
    if target.exists():
        raise AcquisitionStop("Download target already exists.")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": referer})
    total = 0
    try:
        with urllib.request.urlopen(request, timeout=30) as response, target.open("xb") as output:
            while block := response.read(1024 * 1024):
                total += len(block)
                if total > limit:
                    raise AcquisitionStop("Download exceeded --max-download-mib.")
                output.write(block)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    if total < 1024:
        target.unlink(missing_ok=True)
        raise TraceError("The media response was unexpectedly short.")


def _check_audio(source: Path) -> None:
    # Check actual decoding, not a successful HTTP status or a filename extension.
    payload = run_ffmpeg(["-i", str(source), "-t", "1", "-vn", "-ac", "1", "-ar", "8000", "-f", "f32le", "pipe:1"], capture=True)
    if len(payload) < 4:
        raise TraceError("Downloaded media has no decodable audio.")


def _bilibili_data(payload: dict) -> dict:
    if payload.get("code") in {-101, -352, -412, -799, -10403, 87007}:
        raise AcquisitionStop("Bilibili reported an access/rate restriction; use another accessible source.")
    if payload.get("code") != 0 or not isinstance(payload.get("data"), dict):
        raise TraceError("Bilibili public metadata/playback route was unavailable.")
    return payload["data"]


def _acquire_bilibili(value: str, job: Path, limit: int) -> tuple[Path, dict]:
    parts = urllib.parse.urlsplit(value)
    match = re.search(r"/video/(BV[0-9A-Za-z]{10})", parts.path)
    if not match:
        raise TraceError("This Bilibili URL needs the general extractor.")
    bvid = match.group(1)
    info = _bilibili_data(_get_json("https://api.bilibili.com/x/web-interface/view?bvid=" + bvid))
    try:
        requested_page = int(urllib.parse.parse_qs(parts.query).get("p", ["1"])[0])
    except ValueError as exc:
        raise AcquisitionStop("Bilibili page number must be an integer.") from exc
    pages = info.get("pages", [])
    if not 1 <= requested_page <= len(pages):
        raise AcquisitionStop("Bilibili page number is out of range.")
    cid = pages[requested_page - 1]["cid"]
    canonical = f"https://www.bilibili.com/video/{bvid}/?p={requested_page}"
    playback = _bilibili_data(_get_json(f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval=4048&fnver=0&fourk=1"))
    tracks = (playback.get("dash") or {}).get("audio") or []
    seen = set()
    stream_attempts = []
    for track in sorted(tracks, key=lambda item: item.get("bandwidth", 0), reverse=True)[:3]:
        urls = [track.get("baseUrl") or track.get("base_url"), *(track.get("backupUrl") or track.get("backup_url") or [])]
        for url in urls[:3]:
            if not url or url in seen or len(seen) >= 6:
                continue
            seen.add(url)
            target = job / f"stream-{len(seen)}.m4a"
            attempt = {"audio_id": track.get("id"), "stream_number": len(seen)}
            try:
                _download(url, target, limit, canonical)
                _check_audio(target)
                stream_attempts.append({**attempt, "status": "ready"})
                return target, {"kind": "bilibili", "url": canonical, "bvid": bvid, "page": requested_page,
                                "cid": cid, "title": info.get("title"), "audio_id": track.get("id"),
                                "source_sha256": digest(target), "stream_attempts": stream_attempts}
            except AcquisitionStop:
                raise
            except urllib.error.HTTPError as exc:
                if exc.code in {412, 429}:
                    raise AcquisitionStop("Media service rate/access limit; stop retrying this source.") from exc
                stream_attempts.append({**attempt, "status": "failed", "error_type": f"http_{exc.code}"})
            except (TraceError, OSError, ValueError) as exc:
                stream_attempts.append({**attempt, "status": "failed", "error_type": type(exc).__name__})
    raise AcquisitionError("No usable standalone Bilibili audio stream; try the general extractor.", stream_attempts)


class _QuietDownloaderLog:
    def debug(self, message):
        pass

    info = warning = error = debug


def _acquire_ytdlp(value: str, job: Path, limit: int) -> tuple[Path, dict]:
    try:
        from yt_dlp import YoutubeDL

        def size_guard(progress):
            if progress.get("downloaded_bytes", 0) > limit:
                raise AcquisitionStop("Download exceeded --max-download-mib.")

        options = {"format": "bestaudio/best", "noplaylist": True, "outtmpl": str(job / "download.%(ext)s"),
                   "quiet": True, "no_warnings": True, "logger": _QuietDownloaderLog(), "socket_timeout": 25,
                   "retries": 0, "fragment_retries": 0, "extractor_retries": 0, "max_filesize": limit,
                   "progress_hooks": [size_guard], "overwrites": False, "ffmpeg_location": ffmpeg()}
        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(value, download=True)
            if not info or info.get("entries") is not None:
                raise TraceError("Playlists are not supported; provide a single video.")
            target = Path(downloader.prepare_filename(info))
        if not target.resolve().is_relative_to(job.resolve()) or not target.is_file():
            raise TraceError("No media was downloaded; check availability or the size limit.")
        if target.stat().st_size > limit:
            raise AcquisitionStop("Download exceeded --max-download-mib.")
        _check_audio(target)
        return target, {"kind": "yt-dlp", "url": safe_url(info.get("webpage_url") or value), "title": info.get("title"), "source_sha256": digest(target)}
    except ImportError as exc:
        raise TraceError("Install yt-dlp for this URL; local files and public Bilibili audio also work.") from exc
    except TraceError:
        raise
    except Exception as exc:
        raise TraceError("The general extractor could not obtain playable audio; investigate another source.") from exc


def acquire(value: str, job: Path, max_download_mib: int = 100) -> tuple[Path, dict]:
    identity = input_identity(value)
    if identity["kind"] == "local":
        local = Path(value).expanduser().resolve()
        return local, {**identity, "sha256": digest(local)}
    if identity["kind"] == "unknown":
        raise TraceError("Input must be an existing local media file, HTTP(S) URL, or Bilibili BV identifier.")
    if not 1 <= max_download_mib <= 2000:
        raise TraceError("Download limit must be 1-2000 MiB.")
    if re.fullmatch(r"BV[0-9A-Za-z]{10}", value):
        value = identity["url"]
    attempts = []
    parts = urllib.parse.urlsplit(value)
    if parts.hostname == "b23.tv":
        try:
            request = urllib.request.Request(value, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=25) as response:
                value = response.url
            parts = urllib.parse.urlsplit(value)
            attempts.append({"method": "short_link_resolution", "status": "ready"})
        except (OSError, ValueError) as exc:
            attempts.append({"method": "short_link_resolution", "status": "failed", "error_type": type(exc).__name__})
            if isinstance(exc, urllib.error.HTTPError) and exc.code in {401, 403, 412, 429}:
                raise AcquisitionError("Short-link service access/rate restriction; use another source.", attempts) from exc
    routes = []
    if parts.hostname in {"bilibili.com", "www.bilibili.com", "m.bilibili.com"}:
        routes.append(("bilibili_public_audio", _acquire_bilibili))
    routes.append(("yt-dlp", _acquire_ytdlp))
    for method, handler in routes:
        route_dir = job / ("acquire-" + method)
        route_dir.mkdir(parents=True, exist_ok=False)
        try:
            target, metadata = handler(value, route_dir, max_download_mib * 1024 * 1024)
            attempts.append({"method": method, "status": "ready"})
            return target, {**metadata, "acquisition_attempts": attempts}
        except Exception as exc:
            attempt = {"method": method, "status": "failed", "error_type": type(exc).__name__}
            if isinstance(exc, AcquisitionError):
                attempt["stream_attempts"] = exc.attempts
            attempts.append(attempt)
            if isinstance(exc, AcquisitionStop) or (isinstance(exc, urllib.error.HTTPError) and exc.code in {401, 403, 412, 429}):
                raise AcquisitionError("Source acquisition stopped at an access/rate/selection/output limit; use another accessible source or review the limit.", attempts) from exc
    raise AcquisitionError("Available download routes failed. Investigate alternate media or a candidate music source.", attempts)
