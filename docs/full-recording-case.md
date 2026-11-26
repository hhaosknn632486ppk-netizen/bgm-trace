# Full recording recovery: Jeremy Brauns

Observed on 2026-11-26. This case documents finding a particular cover recording after its original upload could not be downloaded, then checking the user's preferred platform. Catalog availability can change. No commercial media, account information or browser dumps are included here.

## The requested edition

The candidate was Jeremy Brauns's **Avengers Doomsday (Final Trailer)**, associated with the [artist's YouTube upload](https://www.youtube.com/watch?v=rR4fAzcf3os). The user wanted the full recording, particularly its later climax. A previously obtained official Apple Music preview covered only about 90 seconds.

| Source | Edition and observed result |
| --- | --- |
| [Apple Music release](https://music.apple.com/be/album/avengers-doomsday-final-trailer-single/6838809023) | `Avengers Doomsday (Final Trailer)`, Jeremy Brauns; public preview acquired, approximately 90 seconds. |
| [NetEase song 3465358977](https://music.163.com/song?id=3465358977) | Same title/artist; listed duration 180419 ms. An ordinary public playback source supplied an MP3, approximately 180.42 seconds, 128 kb/s, 44.1 kHz, stereo. Full decoding succeeded. |
| [Kugou Final Trailer album](https://www.kugou.com/album/info/3krnfka4/) | Normal public browser search returned Jeremy Brauns, `Avengers Doomsday (Final Trailer)`, **03:00**, and this album link. Catalog presence checked; no Kugou download, audio comparison or account entitlement check performed. |
| [Kugou Trailer Music album](https://www.kugou.com/album/info/3be49u87/) | Search also returned `Avengers Doomsday (Trailer Music)`, Jeremy Brauns, **02:15**. This is a distinct catalog edition and was not substituted for the requested Final Trailer version. |

The initial broad artist query showed the older 02:15 result among its first 30 entries but did not show the desired release. Searching `Jeremy Brauns Avengers Doomsday` then returned both editions. A text-only reader had shown a static template; a temporary browser connection error was retried successfully. These failures did not establish that the track was absent.

The original video player's access challenge was not bypassed. Other video candidates were not accepted on titles alone. The successful NetEase route is an observed public playback acquisition, not a guaranteed permanent endpoint or a claim that all tracks are freely downloadable.

## Official-preview verification

The official Apple preview was the query and the complete NetEase MP3 the reference. The documented command was rerun locally against the repository after integrating the existing alignment fixes:

```console
python skills/bgm-trace/scripts/bgm_trace_cli.py verify OFFICIAL_PREVIEW.m4a FULL_CANDIDATE.mp3 --start 2 --duration 85 --speed-min 1 --speed-max 1 --out PRIVATE_JOB/preview-full.json
```

Three separated six-second windows passed with absolute normalized waveform correlations of approximately **0.977, 0.964 and 0.961**. Median correlation was **0.964**, offset spread **0.000125 seconds**, and placement was not marked ambiguous. The selected preview portion began at full-track **46.997 seconds**, so the original preview's start corresponds to approximately **44.997 seconds** at unit speed.

This supports that the checked preview sections and the full candidate are the same recording despite different encodings. These values are **not** identification probabilities or a percentage of cover quality. The preview does not independently verify the remaining ending. Completeness was assessed separately from catalog duration and full-file decoding; unseen edits outside the preview are not ruled out by waveform checks.

The artist's cover and the trailer's original music remain separate recordings. This check did not recover the original trailer master or establish its authorship. Comparing the cover's arrangement with the trailer is a separate task and cannot be replaced by preview matching.

## Delivery and reusable behavior

The native full MP3 was retained. A separate MP3 excerpt from approximately **1:50 to the end** was made with frame copying, preserving lead-in to the later section without another lossy encode. That start was a convenient listening boundary, not a claimed exact climax onset. Prior previews and extracted tracks were retained.

For the subsequent question about Kugou, the result was a confirmed catalog link with title, artist and duration. The user's membership was not inspected and specific playback/download quality was not promised. The already delivered local MP3 did not require a NetEase subscription to play.

The reusable [skill workflow](../skills/bgm-trace/references/full-recording.md) separates search, edition identity, access, full-file checks, preview recording evidence and final delivery. Host tools perform catalog research and acquisition; the existing CLI automates local waveform verification. This single case is not a cross-platform coverage or recognition benchmark.
