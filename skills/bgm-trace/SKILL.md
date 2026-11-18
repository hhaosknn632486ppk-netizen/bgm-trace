---
name: bgm-trace
description: Identify and verify background music in videos or noisy audio, including dialogue-heavy Bilibili clips. Extract audio, optionally separate vocals, compare multiple recognition windows, and check a local reference for speed and time alignment.
---

# BGM Trace

Use the self-contained entrypoint `scripts/bgm_trace_cli.py` with the chosen Python environment. Run `doctor` first if this environment has not been checked. Install `scripts/requirements.txt` when needed; Demucs/PyTorch are optional additional dependencies for separation. Avoid assuming another chat's absolute tool, environment or model paths exist.

## Analyze the requested sound layer

Accept a local audio/video file, public Bilibili URL/BV ID, or another yt-dlp URL. Preserve the user's target interval. Start with a representative short interval for long media; the default is the first 90 seconds and each job is limited to 600 seconds. Use a new work directory outside source control.

```console
python scripts/bgm_trace_cli.py identify INPUT --out JOB_DIRECTORY --online --separate always
```

`--online` means external fingerprint requests. When the user has already asked to identify a song using online services, that authorization is sufficient; do not ask again merely for this flag. If they require local-only handling, use `--offline` with a local input. Offline separation additionally requires `--model-repo` and already-installed dependencies. Do not imply an offline run can search Shazam's catalog.

For known dialogue-heavy mixtures or a requested instrumental, use `--separate always`. Otherwise `auto` first checks the raw mixture and separates only when two independent windows do not agree. A raw consensus can identify a dialogue sample or sound effect rather than the intended music. Inspect per-window results and layer provenance. `music.mp3` is a listening export, not proof of complete voice removal.

## Verify candidates

Read `report.json`. Keep multiple candidates when the video changes music or the evidence conflicts. Repeated transforms of the same timestamp are not independent votes. Do not report a candidate score as a calibrated probability.

Use connected search/web capabilities to find a matching official catalog page or authorized preview. The CLI does not automatically obtain a full song. A reference supplied by the user or available for the requested use can be checked locally:

```console
python scripts/bgm_trace_cli.py verify JOB_DIRECTORY/music.wav REFERENCE --out JOB_DIRECTORY/alignment.json
```

This searches resampling-style speed/pitch changes and checks agreement across different positions. It does not establish authorship, a canonical original, or equivalence of covers/live performances. A failed waveform check does not prove the composition differs. For methods and limits, consult [references/evidence.md](references/evidence.md).

Only if a reference comparison passes and the user wants a corresponding clean excerpt:

```console
python scripts/bgm_trace_cli.py export-reference REFERENCE --alignment JOB_DIRECTORY/alignment.json --out JOB_DIRECTORY/reference-excerpt.mp3
```

The command checks reference identity and coverage. Label this artifact as **reference-derived**, distinct from the **model-separated** video track. Do not replace one silently with the other.

## Handoff

Give the title/artist with an accessible official link, explain what evidence supports the match, and provide the requested audio. Distinguish extraction, source separation and reference-derived files. Report residual speech or unverified listening quality honestly. An interface error, no match, and a conflicting match are different outcomes. Keep commercial media, secrets, signed CDN links, model weights and private absolute paths out of public repositories; the report itself may still contain user-supplied filenames and titles.
