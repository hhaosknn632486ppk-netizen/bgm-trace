# Obtain audio through another route

The user's objective is usable music audio and a supported identification. The supplied link is a starting point. When direct acquisition fails, keep working through relevant accessible alternatives instead of immediately handing the download task back to the user.

## Same source, another acquisition method

`identify` tries the available public Bilibili standalone audio formats and their backup addresses, verifies that a download actually decodes, then tries yt-dlp if that ordinary route fails. yt-dlp can obtain an audio track or a combined audio/video format supported by its extractor. Access/rate restrictions, invalid page selections and configured output/size limits stop retries for that input. Inspect `input_attempts` and the source's `acquisition_attempts` to see what ran. A successful HTTP response or a file named `.mp3` is not a decoding check.

For other platforms, use their available extractor or browser tools to inspect the actual player and sound page. A public direct media/manifest link found in the page can be passed to the downloader. Preserve the public page URL; keep temporary signed media addresses out of shared reports. Respect the selected episode/page and musical passage. A video download is also useful when no separate audio URL is exposed: extract its audio locally.

## Search for another relevant source

Use available web/search/browser capabilities with the exact video title and creator, characteristic quoted text, or a concrete music title/credit from the comments. Open candidate pages rather than relying only on search snippets. Useful paths include the creator's own repost on another platform, an original upload behind a repost, a duplicate clip, an attached platform sound page, an artist's release or an accessible official preview. Start with the strongest provenance and stop broad searching once usable matching material is available.

Read the source/comment report as described in [source-investigation.md](source-investigation.md). Follow an actual music credit through to a playable recording and acquire it when available for the requested use; do not stop at repeating the title. An editing-app sound name can guide a search even when it is absent from mainstream recognition catalogs.

For a named app music library, continue with [library-recovery.md](library-recovery.md): ordinary UI download/export, scoped file reception or explicit cached-file import, actual-format decoding and selected-passage verification. Windows Jianying has an experimental observed-window helper described there.

Compare the uploader, content, duration and edit to assess alternate videos. A visually identical repost may have replaced the soundtrack, so those checks alone do not verify the audio. If the requested audio is available, compare it to the alternate. If it is unavailable, deliver a promising candidate with the creator/source evidence and say that its relationship to the original remains unverified. A candidate need not be withheld merely because audio verification is not yet possible.

The CLI does not perform web searches by itself. The skill uses the host's available search/browser tools for discovery, then can try a discovered URL/file with:

```console
python scripts/bgm_trace_cli.py identify ORIGINAL_URL --alternate-input ALTERNATE_URL --out NEW_JOB --online
```

Up to four alternates are attempted in order only if earlier acquisition/decoding fails. Failed downloads/extractions stay in separate input folders. The same `--start` and `--duration` apply to every input, so use a separate job with appropriate timing for a differently edited clip or a full music track. Attach the original URL via `--source-url` and explain the relationship when using such a separate job. Offline mode requires all inputs to be local.

For a named recording available only as a preview or on a blocked upload, continue with [full-recording.md](full-recording.md): cross-platform release search, edition disambiguation, complete-file checks and official-preview verification. The user's preferred subscription platform can be searched without assuming its catalog or entitlement matches another service.

## Playback capture and final handoff

If an accessible player can play the music but downloading fails, and the host offers suitable playback/capture tools, capture only the intended passage with system audio. Verify the recording has audible content, then process it locally. The CLI has no built-in browser or audio recorder; do not describe capture as completed when the host lacks these tools. Do not request exported cookies or defeat access challenges. Use another accessible source or explain the remaining access gap.

Only after applicable routes are unavailable or unsuccessful, request a local video/audio file or recording containing system audio. A recording through a microphone may add noise and cannot restore music masked in the original mixture.

Deliver a playable file or listening copy when obtained, with the correct role: extracted original mixture, separated music, audio from an alternate upload, candidate reference recording, or verified reference-derived excerpt. State where it came from and whether it was compared with the original. Retain user-approved versions. Avoid claiming a reference or alternate upload was extracted from the inaccessible original video.
