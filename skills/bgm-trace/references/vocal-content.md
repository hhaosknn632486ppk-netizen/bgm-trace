# Decide whether a voice belongs to the requested music

The target is the song as heard in the requested passage. A vocal stem is not synonymous with unwanted narration. Demucs estimates singing and speech together; removing that stem can remove the most identifiable part of a song.

## Review before routing

1. Preserve the original audio and requested interval. If necessary, prepare a local original with `identify INPUT --offline --separate never --out NEW_JOB`; use a local media input for this command. Review a few voiced and adjacent musical passages using available listening/media tools. If actual listening is unavailable, say so and keep the assessment uncertain.
2. Use direct user context, source credits, and audible context. Melody, repeated lyrical phrasing, musical timing, consistent vocal production and voices continuing across edits can support musical vocals. Foreground commentary describing the action or unrelated dialogue interrupting a continuous backing track can support added speech. These are clues, not a classifier with a measured accuracy.
3. When a candidate recording exists, compare the **voices as well as accompaniment** at corresponding positions. Voices also present in that recording support `song`; speech layered over matching instrumental content supports `speech`. Different vocal timbre alone is insufficient. Covers, remixes, musical dialogue samples and missing preview coverage can leave the result uncertain.
4. Record the role and a short basis with `--voice-role ROLE --voice-evidence "BASIS"`. User clarification that the singing belongs to the music is valid evidence; do not ask for it again. Never infer `speech` just because speech activity/ASR found words, a voice is spoken instead of sung, or fingerprints missed.

| Role | Default `--separate auto` behavior |
| --- | --- |
| `song` | Keep original vocals for identification, reference comparison and delivery. Includes rap, chants, choirs, screams and spoken samples that belong to the music. |
| `speech` | Separate before fingerprinting; preserve original. Intended for added narration/dialogue where musical vocals are not being discarded. |
| `mixed` | Keep original; prefer passages without overlay, or assess a narrower interval separately. Full vocal removal cannot selectively preserve singing. |
| `unknown` | Keep original and state the evidence gap. A recognition miss does not change the role. |
| `none` | Keep original; separation adds no justified benefit. |

```console
bgm-trace identify song-video.mp4 --voice-role song --out jobs/song --online
bgm-trace identify narrated-video.mp4 --voice-role speech --voice-evidence "Added commentary over instrumental backing" --out jobs/speech --online
```

`--separate never` is an explicit preservation choice. `--separate always` is still available for explicit removal, but the CLI rejects its conflict with `song` or `mixed`. A separately requested instrumental is a new derivative task, not a reason to discard musical vocals in the identification baseline. The agent must not silently change the role to bypass this guard.

The role applies to this input and interval. Automatic alternate-input recovery resets `auto` to `unknown`: another upload can contain different narration or music. Review that selected recording, then run a separate job if its voice role justifies removal. The report retains the original assessment and the reset.

## Analysis copies and limits

An optional estimated-vocal copy can help hear/transcribe lyrics. Label it **analysis only**, retain its relationship, start time and processing parameters, and never replace the original or call it a clean original vocal. Full source-minus-music reconstruction must reverse any recorded gain before subtraction and requires identical sampling/timing; otherwise do not infer an aligned vocal stem. Separation artifacts can invent or obscure syllables.

If both speech and singing exist, the current CLI has no guaranteed selective narration remover. Prefer unoverlaid windows and compare the original and any explicitly requested diagnostic derivative. Never claim that a general vocal separator knows which voice is part of the composition. If removal fails, the reported source fallback still contains the original voices.
