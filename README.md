# BGM Trace

**[中文说明](README.zh-CN.md)** · CLI + self-contained Codex skill · MIT

Identify music underneath dialogue in short videos. Extract audio, compare multiple recognition windows, optionally remove vocals, and check a candidate against a local reference while searching playback-speed changes.

This is an independent workflow implementation built on existing tools. **Source separation, audio fingerprinting, multi-window recognition, and reference correlation already exist.** See [related projects and overlap](docs/related-projects.md). This is an early release, not a new recognition model or a demonstrated replacement for every mobile recognition app.

Version 0.2 adds a source-investigation fallback: when fingerprint recognition or reference verification is inconclusive, inspect the supplied video link, creator information and comment threads for leads. Public Bilibili collection is automated; other platforms have an agent/browser workflow and evidence import. **Douyin comments are not claimed to be automatically accessible.**

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

## Investigate source clues

Online identification defaults to `--clues auto`: an inconclusive result triggers source investigation when a supplied source link is available. Use `--source-url URL` for a local audio input, `--clues always` to investigate regardless of the fingerprint result, or `--clues never` to disable the automatic collector. Offline identification never reads online source pages.

```console
bgm-trace investigate "https://b23.tv/xQwffio" --online --out jobs/source-clues.json
bgm-trace investigate "https://www.douyin.com/video/123456789" --evidence capture.json --out jobs/reviewed-clues.json
```

The second URL is a synthetic format example. The Bilibili collector reads the description, paginated comments, expanded replies, creator profile and a bounded creator-work listing. Default limits are 200 API requests, 100 pages per comment thread, and 3 creator-work pages; adjust `--max-requests`, `--max-pages`, and `--author-pages` as needed. Access/rate limits stop the service. Budget exhaustion, empty-but-counted comments and incomplete reply threads are explicitly reported.

The skill then reads the collected material and continues incomplete areas with available web/browser tools. For platforms without a direct collector, the CLI writes a browser handoff; that is not a completed search. External browser captures can be analyzed without further network requests. See the [source-investigation workflow and capture schema](skills/bgm-trace/references/source-investigation.md).

`clues.json` contains all collected documents, parent/reply relationships, ranked leads and coverage. Keyword ranking is not an exhaustive semantic review. A bare song title under a song question may be useful; a movie title may be irrelevant to the BGM. Every textual lead remains unverified until independently checked against candidate audio. Collected comments/profiles belong in a private job folder, not the open-source repository.

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
| `clues.json`, `clues.txt` | Local source/creator/comment evidence, unverified leads and actual reading coverage |
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
