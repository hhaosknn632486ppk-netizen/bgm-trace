# Validation status

Recorded on 2026-11-18 for BGM Trace 0.1.0. These are executed checks, not a general music-identification accuracy claim.

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
