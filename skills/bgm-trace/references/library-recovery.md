# From comments to a verified library recording

Use this path when a creator/comment names an editing-app music library, or when a credible candidate is absent from the recognition provider. It also works with an ordinary local audio download from another library. Keep private jobs outside the public repository.

## Establish the lead and requested passage

Read the source investigation with its full question/reply context and actual coverage. Record the public source URL, relevant reply identifiers, claimed title/artist, and named platform. A creator's attribution is a strong lead, but is not waveform evidence. Preserve the investigation file; `--clue-report` binds its filename and SHA-256 without copying private comment text into the recovery report.

Check whether the video changes music. Select the passage the user means rather than allowing consensus from other passages to dominate. Use both the original mixture and the separated track when useful. `--start` is relative to the actual query file, not automatically the original video's timeline. In a cut of original video 40–80 seconds, original time 48 becomes local time 8, and original time 86 is outside the file. Use the full recording when checking 48–86 seconds.

## Search and acquire through the named library

Open the app normally and search the exact title, distinctive title words, then artist if needed. Check the full result title, creator credit and approximate duration; similar titles are not sufficient. Chinese Jianying and international CapCut have distinct catalogs. Public search results or an empty web catalog do not prove the native app lacks a song.

For the native Windows app, see [jianying-desktop.md](jianying-desktop.md). Use its ordinary download button or supported export into a task-specific location. If a project is required, use a new scratch project or the known task-owned one. A visible “add” button may mean the media was already downloaded; adding it again is not necessary for file recovery. Inspect the actual UI before deciding.

Prefer an explicit exported/downloaded file. When using local cache files, choose only the app's music directory and record a baseline **before** clicking download:

```console
python scripts/bgm_trace_cli.py library-snapshot MUSIC_DIRECTORY --out PRIVATE_JOB/before.json
```

An observed default on one Windows installation was `%LOCALAPPDATA%\JianyingPro\User Data\Cache\music`. Confirm the installation's actual path; do not assume it is universal. Do not recursively search the entire user profile, read account databases or copy every cache item. The snapshot contains only immediate media filenames, size and modification time, but also an absolute cache path: keep it private.

After the ordinary app download completes, run:

```console
python scripts/bgm_trace_cli.py library-collect MUSIC_DIRECTORY --snapshot PRIVATE_JOB/before.json --out PRIVATE_JOB/received --title "CATALOG_TITLE" --artist "CATALOG_ARTIST" --query FULL_QUERY --start 48 --duration 38 --source-url PUBLIC_VIDEO_URL --clue-report PRIVATE_JOB/clues.json --mp3
```

The collector waits up to 120 seconds for new/changed immediate media files to remain stable for two seconds. It probes actual format and fully decodes supported audio, compares each candidate, and copies only a unique verified recording. Byte-identical duplicate files count as one candidate; different passing files remain ambiguous. Limits: eight changed candidates by default (maximum 32), 256 MiB per file, and complete tracks up to 600 seconds. Wait time and metadata stability do not guarantee that a stalled download is complete: confirm completion in the app. Rerun collection with the same baseline and a **new output directory** if needed.

No changed files can mean the song was already cached, the path is wrong, or the app has not downloaded it. Do not delete the cache to force a download. If the exact task-related file can be established from the UI and existing evidence, explicitly import it:

```console
python scripts/bgm_trace_cli.py library-import SELECTED_AUDIO --out PRIVATE_JOB/imported --title "CATALOG_TITLE" --artist "CATALOG_ARTIST" --query FULL_QUERY --start 48 --duration 38 --source-url PUBLIC_VIDEO_URL --clue-report PRIVATE_JOB/clues.json --mp3
```

If the existing cache contains many opaque filenames and no reliable mapping, obtain an ordinary export into a new task folder or request the exact file after applicable alternatives are exhausted. Never label an arbitrary recent file with the searched title.

These commands make no network requests and do not search or decrypt app databases/drafts. They handle ordinary decodable files. Login/payment/access requirements remain in the normal app; do not extract cookies, tokens, IPC tickets, encrypted draft contents or use a private native CLI that rejects the caller. A fingerprint failure does not authorize bypassing app access controls.

## Verify and deliver

Read `library-report.json`, `alignment.json`, warnings and exit status:

| Status | Meaning / next step |
| --- | --- |
| `verified` | One candidate passed the selected recording comparison and its native bytes were saved. Review the passage and evidence limits. |
| `acquired_unverified` | One decodable candidate was saved without a query. Deliver as a candidate; do not assert a match. |
| `no_new_stable_media` | No completed changed file was observed. Check normal download completion/path or use explicit import for known cached audio. |
| `ambiguous` | Multiple distinct eligible candidates. Review the exact UI selection/interval; do not choose by recency alone. |
| `no_verified_match` / `no_valid_audio` | Comparison failed or ordinary audio was unavailable. Preserve the report; continue source research or another candidate. |
| `candidate_limit` / `copy_failed` / `error` | A bounded operation could not finish. Read the reason and retain prior outputs. |

Successful acquisition statuses return exit code 0; unresolved statuses return 2. A failed optional MP3 transcode leaves the native file and a warning. `--title` and `--artist` remain caller-supplied catalog claims even after matching. Waveform evidence supports the recording relationship, not authorship or licensing.

`reference.<actual-extension>` is a byte-identical copy, not a re-encode. A downloaded `.mp3` can actually contain M4A/AAC; the detected extension fixes the name, not the audio quality. `reference-listening.mp3` is a separately labeled transcode. Never call an app-library file a separated stem. Retain the native audio, the video's separated track, and any reference-derived excerpt as distinct artifacts.

When the query is unavailable, omit `--query` and deliver the candidate with its source claim and unverified relationship. When multiple candidates exist, selection needs explicit review. Provide useful audio as soon as available while stating exactly what remains unverified. Do not include recordings, cache snapshots, screenshots or private reports in open-source packages.
