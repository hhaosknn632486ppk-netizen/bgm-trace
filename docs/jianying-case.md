# Worked case: comments → Jianying → verified recording

Observed on 2026-11-18; the reusable 0.4 workflow was checked on 2026-11-19. This is one case, not a general success-rate benchmark. No commercial audio, cache snapshot, app screenshot, collected comment corpus or account information is included in the repository.

## Requested source and text evidence

Source: [当你和昔涟拥有不同的超能力时](https://www.bilibili.com/video/BV1VuCwBTEkV/), `BV1VuCwBTEkV`. The requested music was the middle passage in a roughly 120-second video.

The source investigation read 144 root comments and 348 replies, 492 in total, with thread context. The creator profile and 30 work summaries were also read; the reported 508-work listing then hit an access/rate restriction. Comment coverage reached the exposed service end at that time; creator-history coverage remained partial. This does not claim access to deleted/private comments or every comment under every creator work.

Two creator replies supplied the decisive lead:

- [Reply 282240916528](https://www.bilibili.com/video/BV1VuCwBTEkV/#reply282240916528) identified **《故事情绪 强烈色彩》— Ricky Wang** in response to a request for the middle BGM.
- [Reply 282268396736](https://www.bilibili.com/video/BV1VuCwBTEkV/#reply282268396736) identified **剪映** as the place to find it.

These were catalog claims until candidate audio was obtained and compared. Mainstream fingerprint results from the opening/ending and conflicting middle-window results did not establish the requested middle song. Separation helped the later waveform comparison; it did not make every fingerprint answer correct or prove that the song was absent from all provider catalogs.

## Acquisition and reusable automation

The public Bilibili audio was acquired and decoded. The official Demucs `htdemucs_ft` vocals specialist was used to produce a separate music estimate. The observed CPU run used one shift and took about 85 seconds for this video; this single run is not a CPU performance benchmark.

Other public searches did not obtain a reliable matching reference. The international CapCut library was not treated as equivalent to the named Chinese Jianying library. A native helper rejecting an unauthorized caller and a web access challenge were not bypassed.

The normal **剪映专业版音乐库** search for `强烈色彩` returned the full title and Ricky Wang credit. The ordinary Download button produced a local audio file on November 18. Its misleading `.mp3` filename actually contained **M4A/AAC, 44.1 kHz stereo, 157.884 decoded seconds**. The delivered native copy changed only the filename extension; a separate MP3 listening copy was transcoded.

Native audio identity: **2,555,065 bytes**, SHA-256 `fa6bb8f8805cb0ab66142c6079346baf5b3f2f38b95f3a04d6d32e32c86e66c7`. A file hash identifies bytes; it is not itself proof of the music's title or a redistribution license.

On November 19 the new Python window helper was exercised on Windows, Jianying Pro **11.8.0.14778**. It opened the known task scratch draft, selected Audio/Music Library, focused the search box, entered the Chinese query and returned the observed title/artist. An attempted action stopped when the foreground window changed; a new observation was required. No fixed coordinates from this installation are embedded in the skill.

The target was already cached, so its result showed an Add control. The test did not delete/re-download it or add a duplicate timeline track. `library-collect` correctly returned `no_new_stable_media`; `library-import` used the explicitly established cached file. A separate **controlled replay** copied that real recording into an isolated music directory after a baseline, alongside unrelated generated audio. `library-collect` selected the matching recording, rejected the unrelated one, corrected its extension, preserved its bytes and generated the listening copy. That replay validates file reception and selection, not a second live native-app download.

## Recording verification

Version 0.4 selected **video 48–86 seconds** directly from the full input. It matched **reference 1–39 seconds at 1.0× speed**. Three non-overlapping six-second windows agreed:

| Video window start | Reference window start | Original mixture absolute NCC | Separated music absolute NCC |
| --- | --- | --- | --- |
| 49 s | 2 s | 0.6878 | 0.9355 |
| 64 s | 17 s | 0.2874 | 0.8400 |
| 79 s | 32 s | 0.4031 | 0.8917 |

Both checks passed the documented heuristic thresholds. Their median absolute correlations were **0.4031** and **0.8917**, and the estimated offsets agreed with zero spread at the analysis resolution. No competing placement passed the ambiguity check. These numbers are same-recording evidence, not probabilities or a general listening-quality score. The checked relationship covers this passage, not every sound or the entirety of the video.

The reusable workflow is in [library-recovery.md](../skills/bgm-trace/references/library-recovery.md); native UI instructions and limitations are in [jianying-desktop.md](../skills/bgm-trace/references/jianying-desktop.md). The [redacted numerical record](examples/jianying-case-report.json) contains only public source identifiers, acquisition facts and selected comparison results. The native recording, separated derivative and listening transcode were delivered privately with distinct roles. Open-source code does not grant rights to redistribute the music.
