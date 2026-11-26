# BGM Trace

**[中文说明](README.zh-CN.md)** · CLI + self-contained Codex skill · MIT

Identify music in short videos. Review whether voices belong to the song, preserve musical vocals, remove assessed added speech, and combine fingerprints, uncertain lyric drafts and source clues with reference-audio checks.

This is an independent workflow implementation built on existing tools. **Source separation, audio fingerprinting, multi-window recognition, and reference correlation already exist.** See [related projects and overlap](docs/related-projects.md). This is an early release, not a new recognition model or a demonstrated replacement for every mobile recognition app.

**Version 0.5 preserves song vocals by default and adds a lyric-search fallback.** `--separate auto` now removes only caller-assessed added speech; a fingerprint miss no longer triggers vocal removal. Optional local ASR retains uncertain words, timestamps and alternate readings. The skill searches without restricting the artist, then verifies candidates against audio. Voice-role assessment and web research remain agent/user judgments, not an autonomous classifier or search engine.

Version 0.2 adds a source-investigation fallback: when fingerprint recognition or reference verification is inconclusive, inspect the supplied video link, creator information and comment threads for leads. Version 0.2.1 also continues this investigation when acquiring or decoding the audio fails. Public Bilibili collection is automated; other platforms have an agent/browser workflow and evidence import. **Douyin comments are not claimed to be automatically accessible.**

Version 0.3 actively pursues alternate acquisition routes: public Bilibili backup audio/other formats, then yt-dlp; discovered alternate URLs/files can be queued with `--alternate-input`. The skill searches relevant alternate uploads and credited music sources before asking the user to provide a file.

**Version 0.4 completes the comment → music-library → local file → verification workflow.** It receives ordinary library downloads, corrects misleading file extensions without re-encoding native audio, and verifies a selected video passage. An experimental Windows helper enables an agent to observe and operate Jianying's normal music search UI. See the [Jianying case](docs/jianying-case.md) and the exact [automation boundary](skills/bgm-trace/references/jianying-desktop.md).

The skill also supports [finding full recordings across platforms](skills/bgm-trace/references/full-recording.md): prioritize a user's preferred service, distinguish similar release titles and durations, check complete downloaded audio, and compare it against an official preview. Search and acquisition use available host tools; no universal catalog API or subscription entitlement is assumed. See the [Jeremy Brauns case](docs/full-recording-case.md), including the separate NetEase acquisition and Kugou catalog check.

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
bgm-trace identify "https://b23.tv/EXAMPLE" --out jobs/example --online
bgm-trace identify "clip.mp4" --out jobs/local --online
# After reviewing voices: musical vocals are preserved; added speech is separated first.
bgm-trace identify "song-video.mp4" --voice-role song --out jobs/song --online
bgm-trace identify "narrated-video.mp4" --voice-role speech --out jobs/dialogue --online

# Extraction only: no recognition request or model download
bgm-trace identify "clip.mp4" --out jobs/offline --offline --separate never

# A local, authorized reference recording is needed for independent checking
bgm-trace verify jobs/example/source.wav reference.mp3 --out jobs/example/alignment.json

# Optional derivative, clearly labeled as coming from the reference
bgm-trace export-reference reference.mp3 --alignment jobs/example/alignment.json --out jobs/example/reference-excerpt.mp3
```

For offline added-speech separation use `--offline --voice-role speech --model-repo PATH` with installed dependencies and trusted cached weights. No model downloads occur in that mode.

Default analysis is the first 90 seconds; select another interval with `--start 120 --duration 60` (maximum 600 seconds). Downloads are limited to 100 MiB by default. Choose a **new or empty** output directory for each run. The CLI does not silently overwrite earlier jobs.

**Behavior change from 0.4:** `--separate auto` keeps the source for `song`, `mixed`, `unknown` (default) and `none`; only `speech` separates before recognition. Use `--voice-evidence "BASIS"` to record the assessment. A supplied alternate recording resets auto routing to unknown and needs its own review. `--separate never` preserves all voices; `always` is an explicit removal override and rejects conflict with `song`/`mixed`. Failed separation falls back to the source with a warning. Demucs cannot selectively distinguish narration from singing. A confident raw match can still refer to dialogue samples or effects. See [voice assessment](skills/bgm-trace/references/vocal-content.md).

## Lyric fallback, with uncertainty

If musical vocals are available but identification remains inconclusive, keep the original and draft short passages locally:

```console
python -m pip install ".[lyrics]"
bgm-trace lyrics original.wav --model LOCAL_MODEL --comparison-model SECOND_LOCAL_MODEL --window 30:55 --window 105:125 --language en --out jobs/lyrics
```

The second model is optional. Models must be trusted, complete local faster-whisper directories; this command does not download weights or upload audio. CPU/int8 is the default. For a standalone skill, install `scripts/requirements-lyrics.txt`. Optional `--analysis-audio` accepts an already aligned vocal estimate for analysis only and never replaces the original. Selected window coverage is checked; correct alignment still needs caller verification.

`lyrics.txt` marks doubtful words as `[? word]` and unreadable spans as `[unclear]`. `lyrics.json` keeps raw variants, input/model hashes, timestamps and heuristic reasons. Single-pass output stays uncertain. Agreement across models or processed layers is not proof; ASR can hallucinate in music or silence. Short query suggestions avoid uncertain gaps and contain no artist restriction. **The CLI does not search the web.** The skill reviews the audio and variants, searches exact/loose phrases and tentative alternatives using host search tools, follows source clues and checks candidate recordings. A suggested band is only a lead; no hit does not prove unreleased music. See the [full lyric workflow](skills/bgm-trace/references/lyric-search.md).

## When a link cannot provide audio

A video page does not guarantee a downloadable, decodable audio track. The page may require access that the downloader lacks, its URL/parser may no longer work, or the file may have no audio stream. Even successful audio extraction yields a mixture; vocal separation cannot guarantee clean background music.

From 0.2.1, acquisition/decoding failure writes both reports with `recognition.status: audio_unavailable`, the failed stage and recovery steps. It does not submit fingerprints or attempt reference verification. With `--online --clues auto|always`, the original source link can still be investigated for text clues. If those pages also fail, their access gap is reported. The exit code remains **2**, because audio analysis did not complete; readable comments do not make it an audio success. `--offline` and `--clues never` keep their existing behavior.

Version 0.3 first tries public Bilibili standalone audio backups/other audio formats and then the general yt-dlp extractor after an ordinary failure. Each remote success is checked for decodable audio. A combined video format is useful too; local extraction obtains its audio. Access/rate restrictions, invalid selections and size/output limits stop retries for that input. The size cap applies per downloaded file; native stream attempts are bounded at six.

Use the skill's search/browser tools to find another relevant upload, credited sound page or accessible music recording. The CLI itself does not search the web. Pass up to four discovered alternatives with `--alternate-input`; only failed acquisition/decoding advances to the next input. Reports preserve the original request, each attempt and the selected source. Results from alternate media are explicitly scoped to that recording, with its relationship to the original unverified:

```console
bgm-trace identify "ORIGINAL_URL" --alternate-input "ALTERNATE_URL" --out jobs/another-route --online
```

The same start/duration apply to all queued inputs. Use a separate job for another edit or a full music track requiring different timing. After applicable accessible routes are exhausted, continue with a local video/audio file or a user-provided recording containing system audio, preserving the original source:

```console
bgm-trace identify "recording.mp4" --source-url "https://b23.tv/EXAMPLE" --out jobs/local-recovery --online
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

## Recover a music-library recording

When a creator points to Jianying or another music library, follow the [library workflow](skills/bgm-trace/references/library-recovery.md). Confirm the catalog title/artist in the normal app, take a baseline of its **music-only directory** before downloading, then collect and verify:

```console
bgm-trace library-snapshot MUSIC_DIRECTORY --out jobs/library-before.json
# Complete the ordinary app download, then:
bgm-trace library-collect MUSIC_DIRECTORY --snapshot jobs/library-before.json --out jobs/library-result --query full-video.mp4 --start 48 --duration 38 --title "CATALOG_TITLE" --artist "CATALOG_ARTIST" --source-url PUBLIC_VIDEO_URL --clue-report jobs/clues.json --mp3
```

For an explicitly identified file already in the cache or an exported audio file:

```console
bgm-trace library-import SELECTED_FILE --out jobs/cached-result --query full-video.mp4 --start 48 --duration 38 --title "CATALOG_TITLE" --artist "CATALOG_ARTIST" --mp3
bgm-trace verify separated-full-video.wav jobs/cached-result/reference.m4a --start 48 --duration 38 --out jobs/separated-check.json
```

Use the actual extension named in the recovery report. These commands work locally, bind source/clue identities when supplied, and save a native byte-identical reference plus an optional labeled MP3 transcode. They do not infer a title from an opaque cache filename. Without `--query`, a uniquely selected file is `acquired_unverified`; multiple distinct eligible files remain `ambiguous`. Unchanged cached files are not claimed as new downloads. Jobs must be new/empty; the watcher never deletes cache files. Its limits and failure statuses are documented in the workflow.

On Windows, the agent can use `jianying-desktop inspect`, `capture`, `click`, `type` and `key` with a newly viewed observation for every input. It must inspect results and identify controls; **this is not an unattended song-search/download API**. The tested Chinese input/search sequence is on Jianying Pro 11.8.0.14778. Other layouts/platforms need their own validation. Read the [desktop helper instructions](skills/bgm-trace/references/jianying-desktop.md) before using it.

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
| `lyrics.json`, `lyrics.txt` | Private, unverified lyric drafts, uncertain spans, model/layer variants and suggested unrestricted queries; no web search is implied |
| `alignment.json` | Local reference hashes, estimated speed/start, correlations across separate windows |
| `clues.json`, `clues.txt` | Local source/creator/comment evidence, unverified leads and actual reading coverage |
| `library-report.json`, `reference.<actual-extension>` | Catalog/source claims, candidate checks and a byte-identical ordinary library file |
| `reference-listening.mp3` | Optional listening transcode, distinct from the native library audio |
| exported excerpt + JSON sidecar | Explicitly reference-derived audio; **not** an extracted source stem |

Audio evidence reports omit absolute input paths and signed download URLs. They can still contain filenames, video titles, track metadata and source identities: review them before sharing. **Cache snapshots and desktop observations contain private paths/window state and must remain private**, together with screenshots and collected comments. Media remains in the chosen job directory.

Recognition uses **ShazamIO 0.9.0**, an unofficial client. Fingerprints and request metadata go to Shazam when `--online` is selected. Decoding, separation and reference comparison run locally. There is no BGM Trace backend, account, telemetry, or bundled music catalog. URL acquisition and first-time model retrieval also use the network. This release does not bundle the reverse-engineered NetEase/Kugou fingerprinters.

Provider errors and rate limits are reported separately from `no_match`. A Shazam rate limit stops further recognition calls in that run; local separation and reference comparison can still finish. Do not run immediate repeated jobs to work around a limit.

Reference comparison searches a default playback-rate range of 0.94–1.06, then checks whether separate windows agree on their position. The pass flag uses explicit heuristic thresholds; correlation is **not a probability**. It is intended for the same recording with resampling-style speed/pitch changes. Key-locked tempo edits, independent pitch shifts, covers, live versions, repeated motifs and cut-up montages can need manual review. Reference analysis is capped at ten minutes. If an input is longer, preprocess the desired interval.

## Validation and scope

```console
python -m pip install ".[dev]"
python -m pytest -q
python -m build
```

Tests generate their own audio: shifted/speed-changed positives, unrelated negatives, silence, duplicate recognition votes, output/provenance checks, misleading library extensions, changed-file selection and stale/changed desktop observations. The [original worked case](docs/worked-case.md) and [comment-to-Jianying case](docs/jianying-case.md) document observed results without redistributing recordings. These cases are not a general accuracy benchmark. See [validation status](docs/validation.md) for what was actually executed.

## Dependencies and rights

Our orchestration code is MIT licensed. Demucs, ShazamIO, yt-dlp, faster-whisper/CTranslate2, NumPy, SciPy, SoundFile and FFmpeg retain their own licenses; see [third-party notes](THIRD_PARTY_NOTICES.md). Recognition services and media have separate terms and rights. This repository contains no commercial recordings, lyric transcripts, credentials, cookies, model weights, or client secrets. The tool does not bypass login/payment restrictions or automatically download entire identified songs.
