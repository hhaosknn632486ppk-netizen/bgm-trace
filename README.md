# BGM Trace

**[中文说明](README.zh-CN.md)** · CLI + self-contained Codex skill · MIT

Identify music underneath dialogue in short videos. Extract audio, compare multiple recognition windows, optionally remove vocals, and check a candidate against a local reference while searching playback-speed changes.

This is an independent workflow implementation built on existing tools. **Source separation, audio fingerprinting, multi-window recognition, and reference correlation already exist.** See [related projects and overlap](docs/related-projects.md). This is an early release, not a new recognition model or a demonstrated replacement for every mobile recognition app.

Version 0.2 adds a source-investigation fallback: when fingerprint recognition or reference verification is inconclusive, inspect the supplied video link, creator information and comment threads for leads. Version 0.2.1 also continues this investigation when acquiring or decoding the audio fails. Public Bilibili collection is automated; other platforms have an agent/browser workflow and evidence import. **Douyin comments are not claimed to be automatically accessible.**

Version 0.3 actively pursues alternate acquisition routes: public Bilibili backup audio/other formats, then yt-dlp; discovered alternate URLs/files can be queued with `--alternate-input`. The skill searches relevant alternate uploads and credited music sources before asking the user to provide a file.

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

## When a link cannot provide audio

A video page does not guarantee a downloadable, decodable audio track. The page may require access that the downloader lacks, its URL/parser may no longer work, or the file may have no audio stream. Even successful audio extraction yields a mixture; vocal separation cannot guarantee clean background music.

From 0.2.1, acquisition/decoding failure writes both reports with `recognition.status: audio_unavailable`, the failed stage and recovery steps. It does not submit fingerprints or attempt reference verification. With `--online --clues auto|always`, the original source link can still be investigated for text clues. If those pages also fail, their access gap is reported. The exit code remains **2**, because audio analysis did not complete; readable comments do not make it an audio success. `--offline` and `--clues never` keep their existing behavior.

Version 0.3 first tries public Bilibili standalone audio backups/other audio formats and then the general yt-dlp extractor after an ordinary failure. Each remote success is checked for decodable audio. A combined video format is useful too; local extraction obtains its audio. Access/rate restrictions, invalid selections and size/output limits stop retries for that input. The size cap applies per downloaded file; native stream attempts are bounded at six.

Use the skill's search/browser tools to find another relevant upload, credited sound page or accessible music recording. The CLI itself does not search the web. Pass up to four discovered alternatives with `--alternate-input`; only failed acquisition/decoding advances to the next input. Reports preserve the original request, each attempt and the selected source. Results from alternate media are explicitly scoped to that recording, with its relationship to the original unverified:

```console
bgm-trace identify "ORIGINAL_URL" --alternate-input "ALTERNATE_URL" --out jobs/another-route --online --separate always
```

The same start/duration apply to all queued inputs. Use a separate job for another edit or a full music track requiring different timing. After applicable accessible routes are exhausted, continue with a local video/audio file or a user-provided recording containing system audio, preserving the original source:

```console
bgm-trace identify "recording.mp4" --source-url "https://b23.tv/EXAMPLE" --out jobs/local-recovery --online --separate always
```

Host playback capture can be used when suitable tools exist; the CLI itself does not record the screen. A promising acquired candidate may be delivered with its source and unverified status even when the original audio is unavailable. Distinguish unavailable audio, imperfect separation and an actual fingerprint `no_match`. See the [alternate-media workflow](skills/bgm-trace/references/media-recovery.md).

## Investigate source clues

Online identification defaults to `--clues auto`: unavailable audio or an inconclusive result triggers source investigation when a supplied source link is available. Use `--source-url URL` for a local audio input, `--clues always` to investigate regardless of the fingerprint result, or `--clues never` to disable the automatic collector. Offline identification never reads online source pages.

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
