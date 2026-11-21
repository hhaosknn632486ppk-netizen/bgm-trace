"""Routing after a caller/agent reviews the role of voices in the requested audio."""
from __future__ import annotations

from .media import TraceError


VOICE_ROLES = ("unknown", "song", "speech", "mixed", "none")


def plan(role: str, mode: str, evidence: str = "") -> dict:
    if role not in VOICE_ROLES or mode not in {"auto", "always", "never"}:
        raise TraceError("Invalid voice role or separation mode.")
    if mode == "always" and role in {"song", "mixed"}:
        raise TraceError("--separate always conflicts with musical/mixed vocals. Preserve the source for song identification; any requested instrumental is a separate task.")
    separate = mode == "always" or (mode == "auto" and role == "speech")
    if mode == "always":
        reason = "Caller explicitly requested separation; this is not automatic voice classification."
    elif mode == "never":
        reason = "Caller explicitly requested preservation of the source."
    elif role == "speech":
        reason = "Caller assessed the voices as added speech, so prioritize the separated music."
    else:
        reason = "Preserve musical, absent, mixed or uncertain vocals; a fingerprint miss is not evidence of narration."
    return {
        "role": role, "assessment_source": "caller_review_not_an_automatic_classifier",
        "evidence": evidence, "separation_mode": mode, "separate": separate, "reason": reason,
        "original_preserved": True,
        "limitation": "Demucs estimates all vocals; it cannot selectively distinguish added speech from singing or musical spoken samples.",
    }
