# Source, creator and comment investigation

Use this fallback when audio cannot be acquired/decoded, fingerprint recognition does not establish the requested music, or the user asks to inspect source clues. Source-text investigation does not require a successfully downloaded video. Start from links the human supplied. Directly linked creator profiles, sound pages and credited sources are in scope; do not turn this into an unbounded crawl of unrelated accounts.

## Read the source thoroughly

1. Read the video's title, complete description, credits, tags and linked sound/music page. On short-video platforms, an “original sound” label identifies a platform sound item; it does not by itself prove authorship of the underlying music.
2. Read the linked creator's profile, pinned posts and posts relevant to the clip or their music sources. Search the creator's public content for title/lyrics/BGM information when a site search is available. State how much of their work was reviewed; do not silently label a recent-post sample as their full history.
3. Read pinned comments, root comments and their replies. Expand “more replies” and pagination/scrolling until the accessible end. Where the interface offers different sort orders, use them to uncover replies or creator answers omitted from the first view; deduplicate by comment ID.
4. Search within the collected material for `BGM`, `配乐`, `背景音乐`, `歌名`, `什么歌`, `求歌`, `原声`, `原曲`, `音源`, `soundtrack`, `song`, `remix`, lyrics and candidate titles. These terms prioritize reading; **also review text without these words**. A bare title such as “Lantern II” underneath a song request may be the useful answer.
5. Preserve the chain: original link → comment/profile/post → claimed title/source → candidate recording. Keep creator statements, audience guesses, quoted lyrics and genuine audio alignment distinct. Likes and repeated copied comments are not independent verification.

The collector ranks clues for review; it does not ask an LLM to adjudicate them or declare a title verified. In particular, a movie title mentioned in comments may explain the scene while having nothing to do with the added BGM.

## Available acquisition paths

For Bilibili, `investigate SOURCE --online --out JOB/clues.json` reads public metadata, pages through root comments, expands reply threads, then reads the author profile and their public work titles/descriptions. It uses a request budget of 200, up to 100 pages per comment thread, and up to 3 creator-work pages by default. Increase `--max-requests`, `--max-pages` or `--author-pages` when the requested scope warrants it. The creator-work collector does not automatically open every linked video's comments.

Rate/access blocks stop further API calls for that service. Empty comments while the video advertises comments, repeated cursors, missing replies, count mismatches and budget limits are recorded as incomplete. `complete_visible` means the exposed result ended and applicable counts were accounted for, not that deleted, private, folded or withheld content was recovered.

Other platforms, including Douyin, currently receive a **browser handoff**, not a claim of automatic comment access. Use available browsing tools and the user's normally accessible session to read the same areas. Search-engine snippets can find leads but cannot prove full comment coverage. Do not request/export cookies, bypass access challenges, or infer missing content. If the needed interface is unavailable, preserve what was read and identify the missing access or source information.

## Capture external evidence for analysis

Store browser-read or user-provided text in local JSON using this schema. This can also represent content from a creator profile or sound page. IDs only need to be stable within the capture; `parent_id` connects an answer to its question.

```json
{
  "source_url": "https://www.douyin.com/video/123456789",
  "documents": [
    {"id": "q1", "kind": "comment", "text": "求BGM？", "url": "https://www.douyin.com/video/123456789"},
    {"id": "a1", "kind": "comment", "text": "Unlisted Lantern — Demo Artist", "url": "https://www.douyin.com/video/123456789", "parent_id": "q1", "is_uploader": true, "locator": "reply under q1"}
  ],
  "coverage": [
    {"area": "comments", "url": "https://www.douyin.com/video/123456789", "status": "partial", "items_read": 2, "reported_total": 50, "stop_reason": "remaining replies require login"}
  ]
}
```

The URLs/titles above are synthetic examples. Do not present them as real findings. Supported coverage states are `complete_visible`, `partial`, `blocked`, `unavailable`, `not_attempted` and `browser_required`. Include separate coverage entries for source metadata, creator material, sound page and comments as applicable. Capture coverage is a statement by its producer, not independently verified by the importer. Merge captures from the same source with multiple file arguments:

```console
python scripts/bgm_trace_cli.py investigate SOURCE_URL --evidence capture1.json capture2.json --out JOB/clues-reviewed.json
```

This import mode makes no network requests. The source URL must match. It preserves raw text and links, deduplicates evidence IDs, connects parent context and rejects imported claims of audio verification. Read `documents` in manageable batches when large; the lexical `clues` list is not an exhaustive semantic review.

## Finish the investigation

Search narrowly using concrete title/lyric/author clues and inspect their source pages. A candidate can come from an accessible Douyin video, an independent creator page or a local recording; it need not be listed on a mainstream music service. Extract an authorized candidate audio file and run `verify` against the separated query. If waveform comparison fails because it is a cover or a different edit, report that limitation instead of declaring the composition disproved.

Report the actual coverage and remaining gaps, each useful lead's URL/locator and whether audio verification passed. If nothing useful was found, say “no usable clue in the material read.” Do not claim the entire platform or creator history contains no answer. Keep collected comments/profiles in the local job directory; open-source releases include synthetic fixtures and coverage totals, not the captured audience text or account details.
