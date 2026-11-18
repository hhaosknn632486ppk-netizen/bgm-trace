# Related projects and overlap

Audio-project review: 2026-11-18. Jianying-project review: 2026-11-19. This is a bounded source/README review, not a comprehensive survey or a comparative accuracy benchmark. BGM Trace is an independent implementation of a workflow whose main ingredients already exist. No source files were copied from the projects below.

| Project | Existing overlap | BGM Trace's current emphasis |
| --- | --- | --- |
| [Snoop2023/video-background-music-identification-skill](https://github.com/Snoop2023/video-background-music-identification-skill) — MIT | **Very close.** Codex skill/plugin, extraction, HPSS, optional Demucs, Shazam, adjacent-window agreement, full-reference NCC, false-positive checks and labeled evidence. | An executable orchestration pipeline; joint multi-window placement while searching playback speed; ambiguity checks; hash-bound reference excerpts; self-contained skill sharing the CLI implementation. |
| [A-2788553793/dsh-song-id](https://github.com/A-2788553793/dsh-song-id) — MIT | Video URLs, Bilibili, multiple excerpts, Shazam + NetEase, transformation retries and timestamped multi-song results. | Local speech separation and a separate reference verification stage. This release has only Shazam recognition; it does **not** match this project's dual-engine coverage. |
| [onashia/cuezy](https://github.com/onashia/cuezy) — GPL-3.0 | Desktop workflow for identifying tracks in long mixes/videos; tracklist, TXT, CUE and JSON exports. | Short dialogue-heavy excerpts with model-separated artifacts and evidence of recording/time alignment. BGM Trace has no desktop GUI or full-mix tracklist editing. |

## Closest implementation comparison

The first project's inspected tree was `ad61b9753be54f86048faee9383e8963705f2cb7`. Its [recognition script](https://github.com/Snoop2023/video-background-music-identification-skill/blob/ad61b9753be54f86048faee9383e8963705f2cb7/skills/video-background-music-identification/scripts/recognize_shazam.py) submits one supplied audio file; its skill instructions already require checking multiple segments. Therefore it would be misleading to claim multi-window reasoning is new.

Its [comparison script](https://github.com/Snoop2023/video-background-music-identification-skill/blob/ad61b9753be54f86048faee9383e8963705f2cb7/skills/video-background-music-identification/scripts/compare_candidate.py) performs sliding normalized waveform correlation at the supplied playback rate. BGM Trace searches resampling rates, refines them with longer windows, then jointly searches a common placement. This addresses the motivating clip's approximately 3% speed increase and an earlier repeated musical phrase that attracts a single window's highest peak.

Its [separation script](https://github.com/Snoop2023/video-background-music-identification-skill/blob/ad61b9753be54f86048faee9383e8963705f2cb7/skills/video-background-music-identification/scripts/separate_vocals.py) uses Demucs' two-stem CLI. BGM Trace loads the official `htdemucs_ft` vocal specialist and subtracts estimated vocals from the source. This is an implementation choice, not a demonstrated universal separation improvement. Both depend on Demucs.

BGM Trace does not currently implement the closest project's HPSS path or visual-clue workflow. Version 0.2 adds a source/creator/comment fallback, with automated public Bilibili pagination and a browser evidence workflow for other platforms. Metadata research already exists in the closest project's instructions; the fallback is not claimed as a novel idea. Features may change after the inspected revisions.

## Jianying automation overlap (0.4)

| Project / inspected primary source | Existing capability / boundary | BGM Trace's scope |
| --- | --- | --- |
| [Gwaky07/Auto-Cut-skill](https://github.com/Gwaky07/Auto-Cut-skill), including [build_cloud_music_library.py](https://github.com/Gwaky07/Auto-Cut-skill/blob/main/scripts/build_cloud_music_library.py) | Editing/export workflow; README recommends older Windows app versions for automated export. The inspected cloud-music index builder reads music material IDs/titles from existing draft JSON. That is not demonstrated general search of the current app's full music catalog. | Follow a comment's music lead in the currently installed UI, receive ordinary task-related audio files, and verify the recording. No old-app requirement or draft JSON mining. |
| [yangdke/jianying-autoedit-agent](https://github.com/yangdke/jianying-autoedit-agent) | Existing native-UI editing instructions use current observed controls. Observed UI interaction is not a new idea. | A small guarded Windows input/capture helper plus an audio-evidence workflow; not a general autoediting assistant. |
| [Ppppan9/jianying-mcp](https://github.com/Ppppan9/jianying-mcp) | Draft-generation tooling; its README explicitly lists cloud music/effect integration as unavailable in the reviewed version. | Ordinary music-library acquisition and local waveform comparison, without claiming a draft generator provides music search. |

These repositories may change. This inspection did not establish that no music-search API exists anywhere, and it was not an installation or comparative reliability test. BGM Trace's native UI path remains experimental and agent-driven. Its executed scope is in [the case record](jianying-case.md).

## What is and is not original

Demucs supplies separation; Shazam supplies catalog recognition through ShazamIO; FFmpeg supplies media decoding; yt-dlp supplies most URL adapters; normalized cross-correlation and multi-window agreement are established techniques. Our contribution is the particular orchestration, local evidence handling, joint placement/rate search and packaging. Individual features also exist elsewhere. We do not claim the first “video → remove dialogue → identify music” tool, a new music model, or superiority over mobile apps across a representative dataset.

The user-facing benefit is avoiding manual file conversion, repeated phone playback and manual switching between steps. Whether it recognizes more music depends on the recording, source separation, catalog coverage and provider availability.
