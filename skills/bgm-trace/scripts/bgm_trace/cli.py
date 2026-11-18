from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import math
from pathlib import Path
import sys
from datetime import datetime, timezone

from . import __version__
from .media import TraceError, acquire, extract, ffmpeg, listening_copy, save_json
from .recognition import recognize_file, summarize


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bgm-trace", description="Identify background music in noisy video, then verify a candidate recording.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check the local runtime without network calls.")
    identify = commands.add_parser("identify", help="Extract and scan a local file or video URL.")
    identify.add_argument("input")
    identify.add_argument("--out", type=Path, required=True, help="New or empty job directory; contains private media.")
    network = identify.add_mutually_exclusive_group(required=True)
    network.add_argument("--online", action="store_true", help="Allow Shazam fingerprint requests for this job.")
    network.add_argument("--offline", action="store_true", help="Local input only; extract/separate without recognition or model download.")
    identify.add_argument("--separate", choices=["auto", "always", "never"], default="auto")
    identify.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    identify.add_argument("--model-repo", type=Path, help="Trusted local official Demucs checkpoint directory.")
    identify.add_argument("--shifts", type=int, choices=range(1, 5), default=2)
    identify.add_argument("--start", type=float, default=0.)
    identify.add_argument("--duration", type=float, default=90., help="Analyze at most this many seconds (maximum 600).")
    identify.add_argument("--windows", type=int, choices=range(1, 9), default=3)
    identify.add_argument("--window-seconds", type=float, default=12.)
    identify.add_argument("--max-download-mib", type=int, default=100)
    identify.add_argument("--reference", type=Path, help="Optional local reference; no automatic full-track download.")
    comparison = commands.add_parser("verify", help="Check a local reference, including playback-speed changes.")
    comparison.add_argument("query", type=Path)
    comparison.add_argument("reference", type=Path)
    comparison.add_argument("--out", type=Path, required=True)
    comparison.add_argument("--speed-min", type=float, default=.94)
    comparison.add_argument("--speed-max", type=float, default=1.06)
    comparison.add_argument("--speed-step", type=float, default=.01)
    comparison.add_argument("--window-seconds", type=float, default=6.)
    export = commands.add_parser("export-reference", help="Create a clearly labeled excerpt from an already verified local reference.")
    export.add_argument("reference", type=Path)
    export.add_argument("--alignment", type=Path, required=True)
    export.add_argument("--out", type=Path, required=True)
    return parser


def _report_text(report: dict) -> str:
    lines = [f"BGM Trace {__version__}", f"Status: {report['recognition']['status']}", f"Recognition service: {report['recognition']['availability']}", ""]
    for item in report["recognition"]["candidates"]:
        lines += [f"{item['title']} — {item['artist']}", f"Independent windows: {item['independent_windows']}; layers: {', '.join(item['layers'])}", str(item.get("url") or ""), ""]
    for error in report.get("warnings", []):
        lines.append("Note: " + error)
    if "verification" in report:
        result = report["verification"]
        lines += ["", f"Local reference evidence passed: {result['evidence_passed']}", f"Speed: {result['speed_factor']:.6f}; reference start: {result['reference_start_seconds']:.3f}s"]
    lines += ["", "Candidate agreement alone does not prove the requested sound layer or composition.", "Separated music may contain speech/effects; reference-derived audio is a different artifact role."]
    return "\n".join(lines) + "\n"


def identify(args: argparse.Namespace) -> int:
    if args.offline and not Path(args.input).expanduser().is_file():
        raise TraceError("--offline requires a local media file.")
    if args.offline and args.separate == "always" and args.model_repo is None:
        raise TraceError("Offline separation requires --model-repo with trusted cached weights.")
    if not 4 <= args.window_seconds <= 30 or not 1 <= args.max_download_mib <= 2000:
        raise TraceError("Window length must be 4-30 seconds; download limit must be 1-2000 MiB.")
    if not math.isfinite(args.start) or args.start < 0 or not math.isfinite(args.duration) or not 0 < args.duration <= 600:
        raise TraceError("Use a nonnegative start and a duration in (0, 600] seconds.")
    job = args.out.expanduser().resolve()
    if job.exists() and any(job.iterdir()):
        raise TraceError("Job directory is not empty. Choose a new directory to preserve previous results.")
    job.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": 1, "tool_version": __version__, "created_at": datetime.now(timezone.utc).isoformat(), "source": {}, "selection": {"start_seconds": args.start, "max_duration_seconds": args.duration}, "artifacts": [], "attempts": [], "warnings": []}
    try:
        print("Extracting audio...", file=sys.stderr)
        source, metadata = acquire(args.input, job, args.max_download_mib)
        report["source"] = metadata
        prepared = job / "source.wav"
        report["artifacts"].append(extract(source, prepared, args.start, args.duration))
        if args.online and args.separate != "always":
            print("Recognizing source windows...", file=sys.stderr)
            report["attempts"] += asyncio.run(recognize_file(prepared, "source", job, args.windows, args.window_seconds))
        decision = summarize(report["attempts"])
        needs_separation = args.separate == "always" or (args.separate == "auto" and args.online and decision["status"] != "candidate_consensus")
        music = job / "music.wav"
        music_ready = False
        if needs_separation:
            print("Separating dialogue/vocals...", file=sys.stderr)
            try:
                from .separation import separate
                artifact = separate(prepared, music, args.device, args.shifts, args.model_repo)
                music_ready = True
                report["artifacts"].append(artifact)
                listening_copy(music, job / "music.mp3")
                report["artifacts"].append({"file": "music.mp3", "role": "listening_copy_of_model_separated_music"})
                if args.online and decision["availability"] != "rate_limited":
                    print("Recognizing separated windows...", file=sys.stderr)
                    report["attempts"] += asyncio.run(recognize_file(music, "music", job, args.windows, args.window_seconds))
            except Exception as exc:
                message = str(exc) if isinstance(exc, TraceError) else f"Separation failed ({type(exc).__name__}); source recognition evidence was retained."
                report["warnings"].append(message)
        if args.online and args.separate == "always" and not music_ready:
            print("Recognizing source after separation was unavailable...", file=sys.stderr)
            report["attempts"] += asyncio.run(recognize_file(prepared, "source", job, args.windows, args.window_seconds))
        report["recognition"] = summarize(report["attempts"])
        if report["recognition"]["availability"] == "rate_limited":
            report["warnings"].append("Shazam rate-limited this run. Further recognition requests stopped; local artifacts and reference checking remain available.")
        if args.offline:
            report["recognition"]["status"] = "offline_prepared"
        if args.reference:
            print("Verifying local reference...", file=sys.stderr)
            from .alignment import verify
            report["verification"] = verify(music if music_ready else prepared, args.reference)
            save_json(job / "alignment.json", report["verification"])
        save_json(job / "report.json", report)
        (job / "report.txt").write_text(_report_text(report), encoding="utf-8")
        print(_report_text(report), end="")
        print(f"Artifacts: {job}")
        return 0
    except Exception as exc:
        report["error"] = str(exc) if isinstance(exc, TraceError) else type(exc).__name__
        report["recognition"] = summarize(report["attempts"])
        save_json(job / "report.json", report)
        raise


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":
            print(f"BGM Trace {__version__}; Python {sys.version.split()[0]}")
            print("FFmpeg: " + ffmpeg())
            for package in ["numpy", "scipy", "soundfile", "shazamio", "yt_dlp", "demucs", "torch"]:
                print(f"{package}: {'available' if importlib.util.find_spec(package) else 'not installed'}")
        elif args.command == "identify":
            return identify(args)
        elif args.command == "verify":
            from .alignment import verify
            if args.out.exists():
                raise TraceError("Alignment output already exists; choose another file.")
            result = verify(args.query, args.reference, speed_min=args.speed_min, speed_max=args.speed_max, speed_step=args.speed_step, window_seconds=args.window_seconds)
            save_json(args.out, result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "export-reference":
            from .alignment import export_reference
            alignment = json.loads(args.alignment.read_text(encoding="utf-8"))
            print(json.dumps(export_reference(args.reference, alignment, args.out), ensure_ascii=False, indent=2))
        return 0
    except (TraceError, ValueError, OSError, ImportError, KeyError) as exc:
        # Avoid accidental leakage of signed URLs, credentials or absolute paths.
        message = str(exc) if isinstance(exc, (TraceError, ValueError)) else f"{type(exc).__name__}: check input files and installed dependencies."
        print("bgm-trace: " + message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
