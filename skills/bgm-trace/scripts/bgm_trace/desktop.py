"""Experimental observe/act helper. It never infers a music-search result."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from .media import TraceError, digest


def read_observation(path: Path) -> dict:
    if path.stat().st_size > 8192:
        raise TraceError("Observation is too large.")
    try:
        frame = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(frame, dict) or frame.get("kind") != "jianying_window_observation" or frame.get("schema_version") != 1:
            raise ValueError()
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(frame["captured_at"])).total_seconds()
        if not 0 <= age <= 60:
            raise TraceError("Observation expired; capture and inspect the window again.")
        name = frame["image"]
        if not isinstance(name, str) or not name or any(c in name for c in "/\\:") or name in {".", ".."}:
            raise ValueError()
        if digest(path.parent / name) != frame["image_sha256"]:
            raise TraceError("Observation image changed.")
        if any(type(frame[k]) is not int or frame[k] < 0 for k in ("process_id", "process_started", "window_handle", "active_handle", "last_input")):
            raise ValueError()
        if not isinstance(frame["bounds"], list) or len(frame["bounds"]) != 4 or any(type(v) is not int for v in frame["bounds"]):
            raise ValueError()
    except (TypeError, ValueError, KeyError) as exc:
        raise TraceError("Invalid window observation.") from exc
    if path.with_suffix(path.suffix + ".used").exists():
        raise TraceError("Observation was already used; capture and inspect again.")
    return frame


def run(args) -> int:
    if os.name != "nt":
        raise TraceError("The experimental Jianying desktop helper requires Windows. Local library import/collection remain cross-platform.")
    from .windows_desktop import WindowsDesktop

    desktop = WindowsDesktop()
    if args.action == "inspect":
        result = {"status": "inspected", "windows": desktop.windows(), "screenshots_taken": False, "experimental": True}
    elif args.action == "capture":
        if args.out is None or args.out.suffix.lower() != ".png":
            raise TraceError("Capture needs a new .png output filename.")
        target = args.out.expanduser().absolute()
        frame_path = target.with_suffix(".json")
        if target.exists() or frame_path.exists():
            raise TraceError("Capture output already exists.")
        frame, png = desktop.capture(args.pid)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(png)
        frame.update(schema_version=1, kind="jianying_window_observation", image=target.name, image_sha256=digest(target))
        with frame_path.open("x", encoding="utf-8") as stream:
            json.dump(frame, stream, indent=2)
        result = {"status": "captured", "image": str(target), "frame": str(frame_path), "expires_after_seconds": 60, "experimental": True}
    else:
        if args.frame is None:
            raise TraceError("An action requires a freshly captured, visually inspected --frame JSON.")
        if args.action == "type" and (not args.text or len(args.text) > 200 or any(ord(c) < 32 or ord(c) == 127 for c in args.text)):
            raise TraceError("Provide a literal search term of 1-200 characters without control characters.")
        frame = read_observation(args.frame)
        desktop.validate(frame)
        # Exclusive marker: one input action per observation, including failed attempts.
        with args.frame.with_suffix(args.frame.suffix + ".used").open("xb"):
            pass
        desktop.act(args, frame)
        result = {"status": "action_sent", "action": args.action, "capture_again": True, "semantic_success_unverified": True}
    print(json.dumps(result, ensure_ascii=False))
    return 0
