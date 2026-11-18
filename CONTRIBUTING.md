# Contributing

Start with the scope and overlap described in [related projects](docs/related-projects.md). Useful improvements include licensed evaluation fixtures, additional providers behind explicit network controls, and better handling of independent pitch/tempo changes.

Install `.[dev]`, run `python -m pytest -q`, and build with `python -m build`. Tests synthesize their own audio and make no live recognition calls. Please keep fixtures free of commercial recordings and secrets. A provider error or rate limit must stay distinct from an unrecognized recording; new retry logic should respect rate limits.

For bug reports, include tool version, OS, relevant options, and a reviewed/redacted report. Do not upload cookies, API tokens or private media. For quality claims, specify which sound layer was requested, whether a separate reference was available, and whether human listening was performed.
