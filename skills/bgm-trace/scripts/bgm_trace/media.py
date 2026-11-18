from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.parse
import urllib.request

import numpy as np
import soundfile as sf


class TraceError(RuntimeError):
    """An actionable error suitable for a CLI without a traceback."""


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
        raise TraceError("Download target already exists.")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": referer})
    total = 0
    try:
        with urllib.request.urlopen(request, timeout=30) as response, target.open("xb") as output:
            while block := response.read(1024 * 1024):
                total += len(block)
                if total > limit:
                    raise TraceError("Download exceeded --max-download-mib.")
                output.write(block)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    if total < 1024:
        target.unlink(missing_ok=True)
        raise TraceError("The media response was unexpectedly short.")


def acquire(value: str, job: Path, max_download_mib: int = 100) -> tuple[Path, dict]:
    local = Path(value).expanduser()
    if local.is_file():
        return local.resolve(), {"kind": "local", "name": local.name, "sha256": digest(local)}
    if re.fullmatch(r"BV[0-9A-Za-z]{10}", value):
        value = "https://www.bilibili.com/video/" + value
    parts = urllib.parse.urlsplit(value)
    if parts.scheme not in {"http", "https"}:
        raise TraceError("Input must be an existing local media file, HTTP(S) URL, or Bilibili BV identifier.")
    if parts.hostname == "b23.tv":
        request = urllib.request.Request(value, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=25) as response:
            value = response.url
        parts = urllib.parse.urlsplit(value)
    if parts.hostname in {"bilibili.com", "www.bilibili.com", "m.bilibili.com"}:
        match = re.search(r"/video/(BV[0-9A-Za-z]{10})", parts.path)
        if match:
            bvid = match.group(1)
            view = _get_json("https://api.bilibili.com/x/web-interface/view?bvid=" + bvid)
            if view.get("code") != 0:
                raise TraceError(f"Bilibili metadata unavailable (code {view.get('code')}).")
            info = view["data"]
            requested_page = int(urllib.parse.parse_qs(parts.query).get("p", ["1"])[0])
            pages = info.get("pages", [])
            if not 1 <= requested_page <= len(pages):
                raise TraceError("Bilibili page number is out of range.")
            cid = pages[requested_page - 1]["cid"]
            canonical = f"https://www.bilibili.com/video/{bvid}/?p={requested_page}"
            playback = _get_json(f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval=4048&fnver=0&fourk=1")
            tracks = (playback.get("data") or {}).get("dash", {}).get("audio") or []
            if playback.get("code") != 0 or not tracks:
                raise TraceError("Bilibili did not provide a public audio stream. Supply an accessible local file.")
            track = max(tracks, key=lambda item: item.get("bandwidth", 0))
            target = job / "download.m4a"
            errors = []
            for url in [track.get("baseUrl") or track["base_url"], *track.get("backupUrl", [])][:3]:
                try:
                    _download(url, target, max_download_mib * 1024 * 1024, canonical)
                    break
                except TraceError:
                    raise
                except (OSError, TimeoutError) as exc:
                    errors.append(type(exc).__name__)
            else:
                raise TraceError("Bilibili audio download failed: " + ", ".join(errors))
            return target, {"kind": "bilibili", "url": canonical, "bvid": bvid, "page": requested_page, "cid": cid, "title": info["title"], "audio_id": track.get("id"), "source_sha256": digest(target)}
    try:
        from yt_dlp import YoutubeDL
        options = {"format": "bestaudio/best", "noplaylist": True, "outtmpl": str(job / "download.%(ext)s"), "quiet": True, "no_warnings": True, "socket_timeout": 25, "retries": 1, "max_filesize": max_download_mib * 1024 * 1024}
        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(value, download=True)
            if not info or info.get("entries") is not None:
                raise TraceError("Playlists are not supported; provide a single video.")
            target = Path(downloader.prepare_filename(info))
        if not target.is_file():
            raise TraceError("No media was downloaded; check availability or the size limit.")
        return target, {"kind": "yt-dlp", "url": safe_url(info.get("webpage_url") or value), "title": info.get("title"), "source_sha256": digest(target)}
    except ImportError as exc:
        raise TraceError("Install yt-dlp for this URL; local files and public Bilibili audio also work.") from exc
    except TraceError:
        raise
    except Exception as exc:
        raise TraceError("URL download failed. Supply a local file; this tool does not bypass access restrictions.") from exc
