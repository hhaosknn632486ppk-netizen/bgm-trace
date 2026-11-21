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
from .media import TraceError, acquire, extract, ffmpeg, input_identity, listening_copy, save_json
from .recognition import recognize_file, summarize
from .vocals import VOICE_ROLES, plan as vocal_plan


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
    identify.add_argument("--voice-role", choices=VOICE_ROLES, default="unknown", help="Caller-reviewed role in this input/interval; auto removes only added speech.")
    identify.add_argument("--voice-evidence", default="", help="Brief basis for the voice assessment, not an automatic classifier result.")
    identify.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    identify.add_argument("--model-repo", type=Path, help="Trusted local official Demucs checkpoint directory.")
    identify.add_argument("--shifts", type=int, choices=range(1, 5), default=2)
    identify.add_argument("--start", type=float, default=0.)
    identify.add_argument("--duration", type=float, default=90., help="Analyze at most this many seconds (maximum 600).")
    identify.add_argument("--windows", type=int, choices=range(1, 9), default=3)
    identify.add_argument("--window-seconds", type=float, default=12.)
    identify.add_argument("--max-download-mib", type=int, default=100)
    identify.add_argument("--reference", type=Path, help="Optional local reference; no automatic full-track download.")
    identify.add_argument("--clues", choices=["auto", "always", "never"], default="auto", help="Investigate supplied source links when audio is unavailable or recognition/verification is inconclusive.")
    identify.add_argument("--source-url", action="append", default=[], help="User-supplied source link, especially for a local audio input; repeat for more links.")
    identify.add_argument("--alternate-input", action="append", default=[], help="Try another discovered URL/local file if audio preparation fails; repeat up to four times. Matching the original is not assumed.")
    lyrics = commands.add_parser("lyrics", help="Draft uncertain lyrics locally for subsequent unrestricted web search; does not identify a song.")
    lyrics.add_argument("input", type=Path, help="Local original audio/video, retaining musical vocals.")
    lyrics.add_argument("--out", type=Path, required=True, help="New or empty private job directory.")
    lyrics.add_argument("--model", type=Path, required=True, help="Trusted local faster-whisper model directory; never downloaded by this command.")
    lyrics.add_argument("--comparison-model", type=Path, help="Optional second cached model; disagreements remain visible.")
    lyrics.add_argument("--window", action="append", required=True, help="START:END in seconds relative to the supplied input; repeat up to 8, each 4-45 seconds.")
    lyrics.add_argument("--analysis-audio", type=Path, help="Optional aligned vocal estimate, for analysis only; must have the same time origin/length as input.")
    lyrics.add_argument("--language", help="Known language code; omit to detect, without artist/lyric prompting.")
    lyrics.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    lyrics.add_argument("--compute-type", choices=["int8", "float16", "float32"], default="int8")
    investigate = commands.add_parser("investigate", help="Read source/author/comments, or analyze a browser evidence capture.")
    investigate.add_argument("source")
    investigate.add_argument("--out", type=Path, required=True)
    method = investigate.add_mutually_exclusive_group(required=True)
    method.add_argument("--online", action="store_true")
    method.add_argument("--evidence", type=Path, nargs="+", help="Local JSON capture(s); no network calls in this mode.")
    investigate.add_argument("--max-pages", type=int, default=100)
    investigate.add_argument("--max-requests", type=int, default=200)
    investigate.add_argument("--author-pages", type=int, default=3)
    comparison = commands.add_parser("verify", help="Check a local reference, including playback-speed changes.")
    comparison.add_argument("query", type=Path)
    comparison.add_argument("reference", type=Path)
    comparison.add_argument("--out", type=Path, required=True)
    comparison.add_argument("--start", type=float, default=0., help="Start of the requested interval in the query file.")
    comparison.add_argument("--duration", type=float, default=600., help="Maximum query interval, 4-600 seconds.")
    comparison.add_argument("--speed-min", type=float, default=.94)
    comparison.add_argument("--speed-max", type=float, default=1.06)
    comparison.add_argument("--speed-step", type=float, default=.01)
    comparison.add_argument("--window-seconds", type=float, default=6.)
    export = commands.add_parser("export-reference", help="Create a clearly labeled excerpt from an already verified local reference.")
    export.add_argument("reference", type=Path)
    export.add_argument("--alignment", type=Path, required=True)
    export.add_argument("--out", type=Path, required=True)
    baseline = commands.add_parser("library-snapshot", help="Record only music-file metadata before a normal app download.")
    baseline.add_argument("cache", type=Path, help="Explicit music-only directory; not recursively scanned.")
    baseline.add_argument("--out", type=Path, required=True, help="New private snapshot JSON.")
    for name, help_text in [("library-import", "Save and optionally verify one explicitly selected local library file."),
                            ("library-collect", "Wait for stable new/changed music files since a snapshot, then verify/select.")]:
        library = commands.add_parser(name, help=help_text)
        library.add_argument("input", type=Path, help="Selected file for import; music-only directory for collect.")
        library.add_argument("--out", type=Path, required=True, help="New or empty job directory outside the cache.")
        library.add_argument("--title", default="", help="Catalog claim read from the app; not inferred from cached filenames.")
        library.add_argument("--artist", default="")
        library.add_argument("--platform", default="jianying")
        library.add_argument("--source-url", action="append", default=[], help="Public source identity; repeat for more links. This does not fetch the page.")
        library.add_argument("--clue-report", type=Path, help="Bind an existing private source-investigation report by filename and SHA-256.")
        library.add_argument("--query", type=Path, help="Original video/audio or its separated track for local matching.")
        library.add_argument("--start", type=float, default=0.)
        library.add_argument("--duration", type=float, default=600.)
        library.add_argument("--mp3", action="store_true", help="Also create a labeled MP3 listening copy.")
        if name == "library-collect":
            library.add_argument("--snapshot", type=Path, required=True)
            library.add_argument("--timeout", type=float, default=120., help="Bounded wait in seconds, at most 600.")
            library.add_argument("--settle", type=float, default=2., help="Require all changed music-file metadata to remain stable for this many seconds.")
            library.add_argument("--max-candidates", type=int, default=8)
    desktop = commands.add_parser("jianying-desktop", help="Experimental Windows window-observed UI helper; not an autonomous song search API.")
    desktop.add_argument("action", choices=["inspect", "capture", "click", "type", "key"])
    desktop.add_argument("--pid", type=int)
    desktop.add_argument("--out", type=Path, help="New PNG path for capture; a private JSON observation is saved alongside it.")
    desktop.add_argument("--frame", type=Path, help="Fresh, visually inspected observation JSON required for every input action.")
    desktop.add_argument("--x", type=int)
    desktop.add_argument("--y", type=int)
    desktop.add_argument("--text")
    desktop.add_argument("--key", choices=["Enter", "Escape", "SelectAll"])
    desktop.add_argument("--select-all", action="store_true")
    desktop.add_argument("--submit", action="store_true")
    return parser


def _report_text(report: dict) -> str:
    lines = [f"BGM Trace {__version__}", f"Status: {report['recognition']['status']}", f"Recognition service: {report['recognition']['availability']}", ""]
    preparation = report.get("audio_preparation", {})
    if preparation.get("status") == "unavailable":
        lines += [f"Audio preparation failed at: {preparation['failed_stage']}", preparation["reason"],
                  "No fingerprint recognition or audio verification was performed.", ""]
    if preparation.get("relationship_to_requested_source") == "unverified_alternative":
        lines += ["Analyzed an alternate input; its correspondence to the requested video is not audio-verified.",
                  "Recognition/reference results below apply to that alternate recording.", ""]
    if "vocal_assessment" in report:
        voice = report["vocal_assessment"]
        lines += [f"Voice role (caller review): {voice['role']}", voice["reason"],
                  f"Recognition input: {voice.get('recognition_input', 'not analyzed')}", ""]
    for item in report["recognition"]["candidates"]:
        lines += [f"{item['title']} — {item['artist']}", f"Independent windows: {item['independent_windows']}; layers: {', '.join(item['layers'])}", str(item.get("url") or ""), ""]
    for error in report.get("warnings", []):
        lines.append("Note: " + error)
    if "verification" in report:
        result = report["verification"]
        lines += ["", f"Local reference evidence passed: {result['evidence_passed']}", f"Speed: {result['speed_factor']:.6f}; reference start: {result['reference_start_seconds']:.3f}s"]
    for investigation in report.get("source_investigations", []):
        lines += ["", f"Source clues: {investigation['file']}; {investigation['status']}",
                  "Coverage complete: " + str(investigation["coverage_complete"]),
                  "Text leads require audio verification; read the full documents and coverage gaps."]
    for step in report.get("next_steps", []):
        lines.append("Next: " + step)
    lines += ["", "Candidate agreement alone does not prove the requested sound layer or composition.", "Separated music may contain speech/effects; reference-derived audio is a different artifact role."]
    return "\n".join(lines) + "\n"


def _investigate_sources(args: argparse.Namespace, report: dict, job: Path, inconclusive: bool) -> None:
    if not args.online or args.clues == "never" or (args.clues != "always" and not inconclusive):
        return
    from .clues import collect, write_report
    sources = list(args.source_url)
    if report["source"].get("url"):
        sources.insert(0, report["source"]["url"])
    if report.get("requested_source", {}).get("url"):
        sources.insert(0, report["requested_source"]["url"])
    if not sources:
        report["warnings"].append("Source clues need a user-supplied link; add --source-url or use investigate.")
    for index, url in enumerate(dict.fromkeys(sources)):
        print("Investigating supplied source/author/comments...", file=sys.stderr)
        try:
            clues = collect(url)
            name = "clues.json" if index == 0 else f"clues-{index + 1}.json"
            write_report(clues, job / name)
            report.setdefault("source_investigations", []).append({"file": name, "source_url": clues["source_url"], "status": clues["status"], "coverage_complete": clues["coverage_complete"]})
        except Exception as exc:
            # A source-reader failure must not discard the independent audio outcome.
            report["warnings"].append(f"Source investigation failed ({type(exc).__name__}); existing evidence was retained.")


def _finish_report(report: dict, job: Path) -> None:
    save_json(job / "report.json", report)
    text = _report_text(report)
    (job / "report.txt").write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"Artifacts: {job}")


def _prepare_audio(args: argparse.Namespace, report: dict, job: Path) -> bool:
    report["input_attempts"] = []
    for index, value in enumerate(dict.fromkeys([args.input, *args.alternate_input])):
        folder = job / f"input-{index + 1}"
        folder.mkdir()
        attempt = {"input": input_identity(value), "role": "requested" if index == 0 else "alternate"}
        stage = "acquire"
        try:
            source, metadata = acquire(value, folder, args.max_download_mib)
            report["source"] = metadata
            attempt["source"] = metadata
            stage = "extract"
            artifact = extract(source, folder / "source.wav", args.start, args.duration)
            (folder / "source.wav").rename(job / "source.wav")
            report["artifacts"].append(artifact)
            report["input_attempts"].append({**attempt, "status": "ready"})
            relationship = "requested_input" if index == 0 else "unverified_alternative"
            report["audio_preparation"] = {"status": "ready", "selected_input_index": index,
                                           "relationship_to_requested_source": relationship}
            return True
        except Exception as exc:
            reason = str(exc) if isinstance(exc, TraceError) else f"Audio preparation failed ({type(exc).__name__})."
            attempt.update(status="failed", failed_stage=stage, reason=reason)
            if hasattr(exc, "attempts"):
                attempt["acquisition_attempts"] = exc.attempts
            report["input_attempts"].append(attempt)
    report["audio_preparation"] = {"status": "unavailable", "failed_stage": stage, "reason": reason}
    report["error"] = reason
    report["recognition"] = {**summarize([]), "status": "audio_unavailable"}
    report["next_steps"] = [
        "Review source clues and search the exact video title/uploader or music title for another upload or public sound page.",
        "Try a discovered source with --alternate-input in a new job. The same --start applies to each input; analyze differently timed recordings in separate jobs.",
        "If available, capture audible public playback with host tools; request a local file/recording only after accessible alternatives are exhausted.",
        "Keep alternate recordings and reference candidates labeled until their relationship to the requested video can be verified.",
    ]
    return False


def identify(args: argparse.Namespace) -> int:
    voice = vocal_plan(args.voice_role, args.separate, args.voice_evidence)
    if args.offline and not Path(args.input).expanduser().is_file():
        raise TraceError("--offline requires a local media file.")
    if args.offline and voice["separate"] and args.model_repo is None:
        raise TraceError("Offline separation requires --model-repo with trusted cached weights.")
    if len(args.alternate_input) > 4:
        raise TraceError("Use at most four alternate inputs per job.")
    if args.offline and any(not Path(value).expanduser().is_file() for value in args.alternate_input):
        raise TraceError("--offline requires every alternate input to be an existing local file.")
    if not 4 <= args.window_seconds <= 30 or not 1 <= args.max_download_mib <= 2000:
        raise TraceError("Window length must be 4-30 seconds; download limit must be 1-2000 MiB.")
    if not math.isfinite(args.start) or args.start < 0 or not math.isfinite(args.duration) or not 0 < args.duration <= 600:
        raise TraceError("Use a nonnegative start and a duration in (0, 600] seconds.")
    job = args.out.expanduser().resolve()
    if job.exists() and any(job.iterdir()):
        raise TraceError("Job directory is not empty. Choose a new directory to preserve previous results.")
    job.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": 1, "tool_version": __version__, "created_at": datetime.now(timezone.utc).isoformat(), "source": input_identity(args.input), "selection": {"start_seconds": args.start, "max_duration_seconds": args.duration}, "artifacts": [], "attempts": [], "warnings": []}
    report["requested_source"] = dict(report["source"])
    report["vocal_assessment"] = voice
    try:
        print("Extracting audio...", file=sys.stderr)
        prepared = job / "source.wav"
        if not _prepare_audio(args, report, job):
            _investigate_sources(args, report, job, inconclusive=True)
            _finish_report(report, job)
            return 2
        if report["audio_preparation"]["relationship_to_requested_source"] == "unverified_alternative" and args.separate == "auto":
            # An alternate upload may change both music and narration. Review it separately.
            report["requested_vocal_assessment"] = voice
            voice = vocal_plan("unknown", "auto", "Alternate recording needs its own voice assessment.")
            report["vocal_assessment"] = voice
        needs_separation = voice["separate"]
        if args.online and not needs_separation:
            print("Recognizing source windows...", file=sys.stderr)
            report["attempts"] += asyncio.run(recognize_file(prepared, "source", job, args.windows, args.window_seconds))
        decision = summarize(report["attempts"])
        music = job / "music.wav"
        music_ready = False
        if needs_separation:
            print("Separating caller-assessed speech/vocals; preserving source...", file=sys.stderr)
            try:
                from .separation import separate
                artifact = separate(prepared, music, args.device, args.shifts, args.model_repo)
                music_ready = True
                report["artifacts"].append(artifact)
                try:
                    listening_copy(music, job / "music.mp3")
                    report["artifacts"].append({"file": "music.mp3", "role": "listening_copy_of_model_separated_music"})
                except Exception as exc:
                    (job / "music.mp3").unlink(missing_ok=True)
                    report["warnings"].append(f"Optional listening export failed ({type(exc).__name__}); separated WAV remains available for recognition.")
                if args.online and decision["availability"] != "rate_limited":
                    print("Recognizing separated windows...", file=sys.stderr)
                    report["attempts"] += asyncio.run(recognize_file(music, "music", job, args.windows, args.window_seconds))
            except Exception as exc:
                message = str(exc) if isinstance(exc, TraceError) else f"Separation failed ({type(exc).__name__}); source recognition evidence was retained."
                report["warnings"].append(message)
        if args.online and needs_separation and not music_ready:
            print("Recognizing source after separation was unavailable...", file=sys.stderr)
            report["attempts"] += asyncio.run(recognize_file(prepared, "source", job, args.windows, args.window_seconds))
        voice["recognition_input"] = "music.wav" if music_ready else "source.wav"
        if needs_separation and not music_ready:
            report["warnings"].append("Voice removal was unavailable; source fallback still contains the original voices.")
        if args.separate == "always" and args.voice_role == "unknown":
            report["warnings"].append("Explicit separation without a voice-role assessment can remove musical vocals as well as speech.")
        report["recognition"] = summarize(report["attempts"])
        if report["recognition"]["availability"] == "rate_limited":
            report["warnings"].append("Shazam rate-limited this run. Further recognition requests stopped; local artifacts and reference checking remain available.")
        if args.offline:
            report["recognition"]["status"] = "offline_prepared"
        if report["recognition"]["status"] != "candidate_consensus":
            report.setdefault("next_steps", []).append("Review the voice role in the original audio. For musical vocals, use lyrics on short intervals, mark uncertain words, and search without restricting the artist; text matches still need audio verification.")
        if args.reference:
            print("Verifying local reference...", file=sys.stderr)
            from .alignment import verify
            report["verification"] = verify(music if music_ready else prepared, args.reference)
            report["verification"]["input_relationship"] = report["audio_preparation"]["relationship_to_requested_source"]
            save_json(job / "alignment.json", report["verification"])
        inconclusive = (report["recognition"]["status"] != "candidate_consensus"
                        or report["audio_preparation"]["relationship_to_requested_source"] == "unverified_alternative"
                        or report["recognition"]["availability"] != "completed"
                        or ("verification" in report and not report["verification"]["evidence_passed"]))
        _investigate_sources(args, report, job, inconclusive)
        _finish_report(report, job)
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
            for package in ["numpy", "scipy", "soundfile", "shazamio", "yt_dlp", "demucs", "torch", "faster_whisper"]:
                print(f"{package}: {'available' if importlib.util.find_spec(package) else 'not installed'}")
        elif args.command == "identify":
            return identify(args)
        elif args.command == "lyrics":
            from .lyrics import transcribe
            result = transcribe(args.input, args.out, args.model, args.window,
                                comparison_model=args.comparison_model, analysis_audio=args.analysis_audio,
                                language=args.language, device=args.device, compute_type=args.compute_type)
            print(f"Lyrics: {result['status']}; not verified lyrics or song identification. Read uncertain spans and variants in {args.out / 'lyrics.txt'}")
            return 2 if result["status"] in {"asr_unavailable", "partial_draft"} else 0
        elif args.command == "investigate":
            from .clues import collect, import_evidence, write_report
            if args.out.exists() or args.out.with_suffix(".txt").exists():
                raise TraceError("Source investigation output already exists; choose a new filename.")
            if args.out.suffix.lower() != ".json":
                raise TraceError("Source investigation output must be a .json file.")
            result = import_evidence(args.source, args.evidence) if args.evidence else collect(args.source, args.max_pages, args.max_requests, args.author_pages)
            write_report(result, args.out)
            print(f"Source investigation: {result['status']}; {len(result['documents'])} documents; coverage complete: {result['coverage_complete']}")
            print(f"Report: {args.out}")
        elif args.command == "verify":
            from .alignment import verify
            if args.out.exists():
                raise TraceError("Alignment output already exists; choose another file.")
            result = verify(args.query, args.reference, query_start=args.start, query_duration=args.duration, speed_min=args.speed_min, speed_max=args.speed_max, speed_step=args.speed_step, window_seconds=args.window_seconds)
            save_json(args.out, result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "library-snapshot":
            from .library import snapshot
            print(json.dumps(snapshot(args.cache, args.out), ensure_ascii=False, indent=2))
        elif args.command in {"library-import", "library-collect"}:
            from .library import collect, import_file
            if not math.isfinite(args.start) or args.start < 0 or not math.isfinite(args.duration) or not 4 <= args.duration <= 600:
                raise TraceError("Library verification needs a nonnegative start and a duration of 4-600 seconds.")
            options = dict(title=args.title, artist=args.artist, platform=args.platform, query=args.query,
                           start=args.start, duration=args.duration, mp3=args.mp3, source_urls=args.source_url, clue_report=args.clue_report)
            if args.command == "library-collect":
                result = collect(args.input, args.snapshot, args.out, **options, timeout=args.timeout, settle=args.settle, max_candidates=args.max_candidates)
            else:
                result = import_file(args.input, args.out, **options)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] in {"verified", "acquired_unverified"} else 2
        elif args.command == "jianying-desktop":
            from .desktop import run
            return run(args)
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
