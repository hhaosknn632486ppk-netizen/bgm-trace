# Validation status

Recorded on 2026-11-18. These are executed checks, not a general music-identification accuracy claim.

## Version 0.2 source investigation

The source-investigation tests cover root pagination, complete reply expansion, nested question/answer context, creator attribution, rate/access blocks, false empty responses, repeated cursors, exhausted budgets, offline evidence import, untrusted imported verification claims, preservation of reports, and automatic fallback routing. The original audio tests remain in the suite.

Two live public Bilibili reads were performed:

| Source | Actual coverage | Finding / limit |
| --- | --- | --- |
| `BV1ctRZYGEsQ` | 25 root comments + 60 replies = 85; source description and creator profile | No explicit music lead in the read material. Creator work listing was blocked by the public service. |
| `BV1VuCwBTEkV` | 144 root comments + 348 replies = 492; source description, creator profile, 30 creator-work titles/descriptions | A creator reply gave a music name and a follow-up identified the editing app's music library. The creator-work listing reported 508 entries and stopped with an access/rate error after 30, so creator-history coverage stays partial. |

Both comment collections reached the exposed API end, expanded accessible reply threads and accounted for the reported comment totals at collection time. This does not establish access to deleted/private/withheld comments. Full collected documents were reviewed in the development session; audience text and profile captures are retained outside this repository.

The second example validates finding a creator-supplied lead outside a fingerprint result. It does **not** establish that Shazam cannot identify this clip: no new fingerprint test was run for that example. Nor was the creator's claimed recording independently audio-verified; an accessible authoritative reference recording was not obtained from the targeted web searches.

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
- GPU dependency installation on another machine, CPU runtime, URLs outside the tested Bilibili case, independent pitch/tempo edits, covers and long-form mixed sets remain unbenchmarked.
- Recognition requires an external unofficially accessed catalog. Offline processing cannot identify an unknown song from that catalog.
