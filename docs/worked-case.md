# Worked case: dialogue-heavy Bilibili excerpt

This documents one motivating case, not a representative benchmark. Original commercial audio and derived excerpts are intentionally absent from the repository.

- Video: [老头心知肚明自己摊上大事了](https://www.bilibili.com/video/BV1ctRZYGEsQ/), approximately 57.899 seconds.
- Candidate recording: **Sinister Hex Melody — Lumea**.
- Catalog references: [Apple Music](https://music.apple.com/us/album/sinister-hex-melody/1793602511?i=1793602512), [NetEase song 2670775192](https://music.163.com/song?id=2670775192).
- Shazam recording identifier: `811998829`.

## Observations before packaging

In the original investigation, 12-second windows beginning at 4, 22 and 40 seconds of the separated audio all returned the candidate above. A middle window of the source mixture instead returned `Nobody — Freedomdeus Mostart`. That source result was retained as competing evidence; we did not establish exactly which sound caused it.

Public NetEase and Kugou recognition attempts did not produce a match in that investigation. A NetEase catalog lookup did locate the reference recording. This distinction matters: finding a title in a catalog is not a successful audio-recognition result, and one example does not establish comparative provider accuracy.

The separated output retained some speech/effects. A cleaner listening excerpt was created from the independently aligned reference and labeled as reference-derived, rather than being represented as a pristine extracted stem.

## Local reference check

The standalone CLI was exercised against the separated case audio and a locally available reference. It estimated:

- Playback-rate factor: approximately **1.029943**.
- Reference start: approximately **16.026 seconds**.
- Three separate query windows agreed on the base offset within about **0.003 seconds** in that run.

The middle window's unconstrained highest peak landed on a repeated phrase approximately 21.333 seconds earlier. Joint multi-window placement resolved that conflict. These figures establish useful same-recording/time-alignment evidence for this case, not a calibrated confidence percentage.

## Reproduce with your own accessible media

```console
bgm-trace identify "https://b23.tv/xQwffio" --out jobs/case --online --separate always
bgm-trace verify jobs/case/music.wav YOUR_LOCAL_REFERENCE.mp3 --out jobs/case/alignment.json
```

An independently obtained, authorized local reference is required. The repository does not supply or automatically retrieve the complete song. Public video availability, service behavior and fingerprint matches may change. See [validation.md](validation.md) for the packaged implementation's actual test status, including the live service limit encountered during retesting.
