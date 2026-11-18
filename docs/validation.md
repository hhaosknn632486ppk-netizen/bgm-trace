# Validation status

Updated on 2026-11-19. Older version sections preserve their original observation scope. These are executed checks, not a general music-identification accuracy claim.

## Version 0.4 music-library recovery

The local Windows suite passed **94 tests**. New tests generate their own media and cover selected-passage timestamps and reference excerpts, actual AAC in a misleading `.mp3` filename, stable changed-file selection, unrelated/corrupt candidates, ambiguous matching files, identical duplicates, unchanged caches, invalid baselines and limits, files changing during inspection/copy, no overwrite, optional-transcode failure, source-clue provenance and blocked desktop observations. Desktop guard tests do not send real UI input or establish that an app search succeeded.

Separate live/private checks used the [Jianying case](jianying-case.md):

- The new Windows helper on Jianying Pro 11.8.0.14778 opened the known task draft, navigated the music library, entered Chinese text and showed the target title/artist. A real foreground change stopped an attempted action. This is an observed agent-driven sequence, not universal unattended search.
- The normal app download had already occurred on November 18. The new importer read that exact cached file, detected M4A/AAC despite its `.mp3` name, retained byte identity and created a distinct MP3. Unchanged-cache collection correctly reported no new file.
- A controlled replay placed the real library recording and unrelated generated audio into an isolated music directory after a snapshot. The collector selected only the verified recording and retained the source/clue-report identity. This was not a fresh native-app download.
- Direct selection of full-video 48–86 seconds matched reference 1–39 seconds at 1.0×. Original-mixture and separated-track checks both passed; median absolute NCC was 0.4031 and 0.8917 respectively, with zero offset spread and no competing placement. These checks reproduced the earlier case result.

Native desktop screenshot/input assistance is Windows-only and experimental. Local media collection/import/comparison is separately exercised by the cross-platform test suite. No app credentials, private IPC, draft decryption, full-cache copying or commercial audio are included. The live checks used the existing installation/account state; they do not establish anonymous or subscription-independent access to every catalog asset. Consult release CI for each OS/Python result.

The skill structure validator and relative documentation links passed. A wheel and source distribution were built; a new Windows CPython 3.12.13 environment installed the wheel and completed synthetic AAC-with-MP3-name import, selected-passage verification and listening-copy output outside the checkout. A separately copied skill ran the same workflow with its own module path verified, so it did not depend on the installed engine as a fallback. Packaged Python sources were compared with the checkout. These checks do not install optional Demucs/PyTorch in the new environment or imply a clean native-app installation test.

## Version 0.3 alternate acquisition

Controlled tests cover a corrupt/failed primary stream followed by a valid backup, another available audio format, fallback from missing standalone audio to a combined video through the general extractor, stopping conditions, alternate-input recovery after acquisition/decoding failure, offline network rejection and preservation of original-versus-alternate identity. Successful recognition/reference evidence on an alternate is not silently assigned to the original video.

A live check on the motivating Bilibili source deliberately disabled the native route, then used the real yt-dlp extractor to obtain **57.898684807 seconds** of audio. Local waveform verification against the previously obtained source audio passed. This demonstrates the second route working for that one sample; the first failure was injected, not an observed native-service outage. No new Shazam identification was needed or claimed.

Search-driven mirror discovery and playback capture are skill workflows using host capabilities, not autonomous CLI crawlers/recorders. They were not demonstrated by that live download test. Media and the detailed private run are excluded from the repository. See the release revision's CI for the complete test-suite result.

## Version 0.2.1 unavailable-audio recovery

Focused tests simulate acquisition failure for a URL, short link and BV ID, and generate real MP4 files without audio tracks to exercise FFmpeg decoding failure. They verify that source investigation can continue without any fingerprint/reference calls, token-bearing error details are omitted, offline/disabled-clue modes do not fetch pages, both reports survive a source-reader failure, and a subsequent local recording can be analyzed in a separate job while preserving the earlier report and original source link.

These are controlled regression tests, not live access tests for restricted websites. No automatic screen-capture feature, universal URL compatibility or guaranteed clean separation was added. Consult CI for the complete test suite result on the release revision.

## Version 0.2 source investigation

The source-investigation tests cover root pagination, complete reply expansion, nested question/answer context, creator attribution, rate/access blocks, false empty responses, repeated cursors, exhausted budgets, offline evidence import, untrusted imported verification claims, preservation of reports, and automatic fallback routing. The original audio tests remain in the suite.

Two live public Bilibili reads were performed:

| Source | Actual coverage | Finding / limit |
| --- | --- | --- |
| `BV1ctRZYGEsQ` | 25 root comments + 60 replies = 85; source description and creator profile | No explicit music lead in the read material. Creator work listing was blocked by the public service. |
| `BV1VuCwBTEkV` | 144 root comments + 348 replies = 492; source description, creator profile, 30 creator-work titles/descriptions | A creator reply gave a music name and a follow-up identified the editing app's music library. The creator-work listing reported 508 entries and stopped with an access/rate error after 30, so creator-history coverage stays partial. |

Both comment collections reached the exposed API end, expanded accessible reply threads and accounted for the reported comment totals at collection time. This does not establish access to deleted/private/withheld comments. Full collected documents were reviewed in the development session; audience text and profile captures are retained outside this repository.

At the version 0.2 checkpoint, the second example validated finding a creator-supplied lead, but no new fingerprint test or independent audio verification had yet been completed for it. The later native-library acquisition and recording checks are documented in the version 0.4 section and [follow-up case](jianying-case.md). Neither checkpoint establishes that the song is absent from all mainstream catalogs.

The Douyin path is currently a browser workflow plus offline evidence import. Its synthetic capture tests are not a live Douyin comment-access test. No universal automatic Douyin comment collector is claimed. Consult CI for the test count and results on each published revision.

## Original version 0.1 audio validation

## Local checks

| Check | Executed result |
| --- | --- |
| Clean core installation on Windows, standard CPython 3.12.13 | Passed; CLI doctor, FFmpeg discovery, numerical and provider libraries imported |
| Automated tests | **24 passed**; generated-audio positives at 1.0, 1.03 and 1.0273 playback rates, independent noise, silence, repeated passage ambiguity, duplicate/overlapping votes, offline extraction, no overwrite, reference identity/coverage, rate-limit stopping and separation-first ordering |
| Skill structure validator | Passed for `skills/bgm-trace` |
| Python distribution | Source distribution and wheel built; wheel installed independently of the checkout and offline CLI extraction executed successfully |
| Local reference check on the motivating video | Passed on the final separated output; rate 1.029943235, start 16.025913 s, three offset estimates within 0.002833 s |
| Reference-derived MP3 export | Executed; audio file plus hash-bound role/provenance sidecar written |
| GPU separation | Executed with an existing PyTorch 2.7.1 + CUDA 12.8 environment and cached official checkpoint; not a clean installation of the optional GPU dependencies |

The desktop's bundled Python initially failed inside setuptools because the sandbox's redirected temporary path contained braces. A standard CPython environment and a normal workspace temporary directory built/installed successfully. This was an environment failure; no permissive fallback was added to the project.

## Live service test

The final run used the public Bilibili short link, downloaded its audio, extracted 57.899 seconds, separated with the official `04573f0d` checkpoint using two shifts, queried three non-overlapping music windows, and checked the locally available reference.

**Two of the three separated windows returned Sinister Hex Melody — Lumea**, Shazam ID `811998829`. The run reached `candidate_consensus` with provider availability `completed`, and local reference verification passed. The reviewed report is in [examples/bilibili-case-report.json](examples/bilibili-case-report.json); no source audio, checkpoint, private path, or signed CDN URL is included.

An earlier packaged run encountered Shazam `RateLimited` after scanning the raw mixture. That result was not treated as a negative match. The final implementation prioritizes separated music when `--separate always` is selected, stops after a rate limit, spaces normal calls, and reports service availability separately. The later successful run does not establish an uptime guarantee.

## Remaining scope

- No broad corpus or controlled comparison against NetEase/Kugou/mobile apps has been run.
- No guarantee of complete speech/effect removal; no new human listening evaluation of every exported variant is claimed.
- Linux/other Python versions are covered by the repository's CI configuration; consult the actual Actions result for each revision rather than inferring success from this file.
- GPU dependency installation on another machine, CPU performance across a corpus, URLs outside the documented cases, independent pitch/tempo edits, covers and long-form mixed sets remain unbenchmarked. The later Jianying case records one executed CPU separation run, not a runtime guarantee.
- Recognition requires an external unofficially accessed catalog. Offline processing cannot identify an unknown song from that catalog.
