# BGM Trace

**[中文说明](README.zh-CN.md)** · CLI + self-contained Codex skill · MIT

Identify music underneath dialogue in short videos. Extract audio, compare multiple recognition windows, optionally remove vocals, and check a candidate against a local reference while searching playback-speed changes.

This is an independent workflow implementation built on existing tools. **Source separation, audio fingerprinting, multi-window recognition, and reference correlation already exist.** See [related projects and overlap](docs/related-projects.md). This is an early release, not a new recognition model or a demonstrated replacement for every mobile recognition app.

## Install

Python 3.10+ is required. From a downloaded/cloned checkout:

```console
python -m pip install .
bgm-trace doctor
```

FFmpeg is found on PATH or through the installed `imageio-ffmpeg` package. Set `BGM_TRACE_FFMPEG` to an executable path to override it. FFprobe is not required.

For dialogue/vocal separation, install the optional, substantially larger dependency set:

```console
python -m pip install ".[separate]"
```

PyTorch's CUDA support depends on its installed build. CPU mode works but is slower. Separation loads the official Demucs `htdemucs_ft` vocals checkpoint `04573f0d`; the first online separation may download it. `--model-repo PATH` uses a trusted existing checkpoint directory. Do not use checkpoints supplied by an unknown media uploader.

## Use

```console
# Public Bilibili links/BV IDs, other yt-dlp URLs, or a local file
bgm-trace identify "https://b23.tv/EXAMPLE" --out jobs/example --online --separate always
bgm-trace identify "clip.mp4" --out jobs/local --online

# Extraction only: no recognition request or model download
bgm-trace identify "clip.mp4" --out jobs/offline --offline --separate never

# A local, authorized reference recording is needed for independent checking
bgm-trace verify jobs/example/music.wav reference.mp3 --out jobs/example/alignment.json

# Optional derivative, clearly labeled as coming from the reference
bgm-trace export-reference reference.mp3 --alignment jobs/example/alignment.json --out jobs/example/reference-excerpt.mp3
```

For offline separation use `--offline --separate always --model-repo PATH` with installed dependencies and trusted cached weights. No model downloads occur in that mode.

Default analysis is the first 90 seconds; select another interval with `--start 120 --duration 60` (maximum 600 seconds). Downloads are limited to 100 MiB by default. Choose a **new or empty** output directory for each run. The CLI does not silently overwrite earlier jobs.

`--separate auto` first scans the original mixture and separates when it lacks a two-window consensus. For known dialogue-heavy media, use `always`: this separates first and prioritizes fingerprint requests for the requested music layer. A confident raw match can still refer to dialogue samples or sound effects. The CLI preserves candidates rather than treating the top result as proven.

## Skill installation

Copy `skills/bgm-trace` into your agent's skill directory, for example `~/.codex/skills/bgm-trace`. The folder includes the same Python implementation as the CLI, so standalone copying does not lose the engine. Install its dependencies into your chosen environment:

```console
python -m pip install -r /path/to/bgm-trace/scripts/requirements.txt
python /path/to/bgm-trace/scripts/bgm_trace_cli.py doctor
```

Invoke `$bgm-trace` with a local video or link. The skill describes how to interpret results, obtain legitimate reference audio, and distinguish a separated track from a reference-derived excerpt. It does not require a Codex plugin manifest or an MCP server.

## Results and evidence

| Artifact | Role |
| --- | --- |
| `source.wav` | Decoded source mixture; still contains dialogue/effects |
| `music.wav`, `music.mp3` | Optional model-separated derivative; residual speech/effects may remain |
| `report.json`, `report.txt` | Source identity, parameters, per-window outcomes, candidate agreement, warnings |
| `alignment.json` | Local reference hashes, estimated speed/start, correlations across separate windows |
| exported excerpt + JSON sidecar | Explicitly reference-derived audio; **not** an extracted source stem |

Reports omit absolute input paths and signed download URLs. They can still contain filenames, video titles, track metadata and source identities: review them before sharing. Media remains in the chosen job directory.

Recognition uses **ShazamIO 0.9.0**, an unofficial client. Fingerprints and request metadata go to Shazam when `--online` is selected. Decoding, separation and reference comparison run locally. There is no BGM Trace backend, account, telemetry, or bundled music catalog. URL acquisition and first-time model retrieval also use the network. This release does not bundle the reverse-engineered NetEase/Kugou fingerprinters.

Provider errors and rate limits are reported separately from `no_match`. A Shazam rate limit stops further recognition calls in that run; local separation and reference comparison can still finish. Do not run immediate repeated jobs to work around a limit.

Reference comparison searches a default playback-rate range of 0.94–1.06, then checks whether separate windows agree on their position. The pass flag uses explicit heuristic thresholds; correlation is **not a probability**. It is intended for the same recording with resampling-style speed/pitch changes. Key-locked tempo edits, independent pitch shifts, covers, live versions, repeated motifs and cut-up montages can need manual review. Reference analysis is capped at ten minutes. If an input is longer, preprocess the desired interval.

## Validation and scope

```console
python -m pip install ".[dev]"
python -m pytest -q
python -m build
```

Tests generate their own audio: shifted/speed-changed positives, unrelated negatives, silence, duplicate recognition votes, and output/provenance checks. The [worked case](docs/worked-case.md) documents the motivating 58-second Bilibili example without redistributing the recording. One successful case is not a general accuracy benchmark. See [validation status](docs/validation.md) for what was actually executed.

## Dependencies and rights

Our orchestration code is MIT licensed. Demucs, ShazamIO, yt-dlp, NumPy, SciPy, SoundFile and FFmpeg retain their own licenses; see [third-party notes](THIRD_PARTY_NOTICES.md). Recognition services and media have separate terms and rights. This repository contains no commercial recordings, credentials, cookies, model weights, or client secrets. The tool does not bypass login/payment restrictions or automatically download entire identified songs.
