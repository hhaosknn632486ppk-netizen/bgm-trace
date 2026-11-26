# Find a full recording and verify its edition

Use this workflow after a specific recording becomes a candidate but its upload cannot be acquired, only a preview is available, or the user prefers another service. Search with the host's web/browser tools; reuse the existing local `verify` command. This is not an automated cross-platform search, subscription manager or universal downloader.

## Search the relevant catalogs

Start with the artist's credited upload, release page or artist-linked services. Prefer a service the user already uses when they name one, including Kugou or NetEase. Search the exact artist and distinctive title together, then narrower edition words such as `Final Trailer`. A broad artist search may show only the first page of popular tracks; a missing result there is not evidence of absence.

Search engines, text-only page readers and native catalogs have different coverage. If a text reader returns an empty/static template, try the normal public search page in an available browser. Distinguish a connection error, an access challenge, truncated results and an actual completed search. A bounded retry is reasonable for a transient network failure; stop that route at access challenges or rate limits and continue another accessible source. Do not repeatedly refresh a blocked player or request exported login credentials.

For each serious candidate, keep a small private comparison record:

| Field | Why it matters |
| --- | --- |
| Public page URL, platform, observed date, track/album identifier | Reopen the actual listing; a search snippet alone is insufficient. |
| Exact title including parentheses, artist and album | `Trailer Music`, `Final Trailer`, covers, live versions and extended edits can be distinct recordings. |
| Listed duration and release date, when available | Useful disambiguation clues, not audio proof. Release dates can differ between services. |
| Availability observed | Separate listed, preview playable, full playback observed, acquired, and blocked/unknown. |
| Local filename/hash, detected format and decoded duration, if acquired | Bind the comparison to the actual file and distinguish preview from full track. |
| Preview source and comparison report, if checked | Record which relationship was tested and what remains unverified. |

Keep plausible editions separate. Duration rounding or a small encoder delay can be normal; a materially shorter duration needs investigation. Matching titles and lengths alone do not establish identical recordings. Do not conflate the composer of the original score with the performer/arranger of a cover.

## Acquire and check completeness

Use the ordinary accessible download/export path or a public playback source exposed by the service for the requested use. Keep the stable public page as provenance; do not publish temporary CDN URLs. A method that worked once is an observation, not a permanent platform adapter. Use the existing media-acquisition/library-import helpers where appropriate, or host download tools followed by local probing and full decoding.

Confirm actual container/codec, sample rate, channels, bitrate where meaningful, and full decoded duration. Compare that duration with the selected catalog edition. A file named `.mp3`, an HTTP 200, or a title containing “full” does not prove it is complete audio. Reject HTML/error bodies and truncated decodes. Do not turn a 90-second preview into a “full version” by padding or repeating it.

Retain the native file without re-encoding; create listening conversions separately. A higher export bitrate cannot restore lost quality. Paid or lossless availability needs its own evidence. A listing alone does not prove the user's particular membership covers full playback, downloads or every quality tier; use the normal logged-in app for those checks when available and authorized. No purchase is implied by a request to find the track.

## Use an official preview as a recording anchor

Download an accessible preview from a credible artist/release source and preserve its public page and bytes. Use the shorter preview as the query and the candidate full track as the reference:

```console
python scripts/bgm_trace_cli.py verify OFFICIAL_PREVIEW.m4a FULL_CANDIDATE.mp3 --out PRIVATE_JOB/preview-to-full.json
# Example for a 90-second preview: skip edge fades and compare its interior.
python scripts/bgm_trace_cli.py verify OFFICIAL_PREVIEW.m4a FULL_CANDIDATE.mp3 --start 2 --duration 85 --speed-min 1 --speed-max 1 --out PRIVATE_JOB/preview-interior.json
```

Choose the interval from the actual preview; 2/85 is an example, not a default for all preview lengths. A fixed unit speed is appropriate when checking ordinary encodings of the same release. If an edit/rate change is plausible, use the default bounded speed search and inspect the inferred rate. Do not widen parameters repeatedly simply to force a pass.

Read `evidence_passed`, `timing_ambiguous`, `windows`, `offset_spread_seconds`, `speed_factor`, and `query_selection`. Multiple separated windows should agree on placement, rather than merely matching one repeated melody. With a selected query start, the report's base offset refers to that selected portion; use each window's `source_query_start_seconds` to map back to the original preview. Keep reports for rejected candidates too.

A passing result supports that the preview's overlapping sections and the candidate belong to the same recording. It does not independently verify the full ending, authorship, licensing or lossless quality. Assess completeness separately from catalog length and full decoding; undetected edits outside the preview remain possible. A failed waveform check may reflect another arrangement/master/edit; it is not proof of a different composition. See [evidence.md](evidence.md).

Keep two questions separate when the target is a trailer:

1. Does the downloaded full cover match the artist's official preview? Use waveform verification.
2. How does that cover relate to the trailer music? Compare the requested trailer passage separately. Melody/chroma similarity can support an arrangement relationship but cannot establish the same master or a percentage of “reconstruction quality.” Do not call calculated features a listening judgment.

## Deliver what the user requested

For a full-track request, deliver the retained full file and actual source. If the user mainly wants the climax, also provide a separately named late excerpt with its start/end in the full track. Include some lead-in when useful; do not call an arbitrary timestamp the exact climax onset. A preview's timeline is not the full track's or trailer's timeline. `export-reference` extracts the verified overlap; it does not locate a climax outside the preview. Use an ordinary local trim for that excerpt and label it accordingly.

For a platform-availability question, provide the confirmed song/album link, exact title, artist and distinguishing duration. Do not download again solely to answer availability. Clearly label untested membership/download quality. An already delivered ordinary local MP3 does not require a subscription to its source platform to play.

Preserve earlier extracts, separated tracks and previews. Report whether the full file is a cover, original recording or still a candidate, and scope waveform evidence to the checked overlap. Keep commercial audio, account information, browser captures and private reports out of the public skill. A public case can include stable catalog links, non-sensitive metadata, aggregate checks and limitations.
