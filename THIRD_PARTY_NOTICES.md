# Third-party components

BGM Trace's original orchestration code is MIT licensed. Dependencies and external services are separate. This source distribution does not vendor the following implementations, binaries, model weights or audio recordings.

| Component | Used for | Upstream licensing source |
| --- | --- | --- |
| [Demucs](https://github.com/facebookresearch/demucs) | Optional vocal separation, official checkpoint `04573f0d` | [MIT license](https://github.com/facebookresearch/demucs/blob/main/LICENSE); consult model documentation separately |
| [ShazamIO](https://github.com/shazamio/ShazamIO) | Unofficial Shazam API client and fingerprint interface | [Upstream repository/license](https://github.com/shazamio/ShazamIO) |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Public video/audio URL acquisition | [Unlicense](https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE); upstream distributions may include other components |
| [NumPy](https://github.com/numpy/numpy) / [SciPy](https://github.com/scipy/scipy) | Numerical processing and correlation | Their BSD licenses and bundled dependency notices |
| [SoundFile](https://github.com/bastibe/python-soundfile) | WAV/FLAC I/O | BSD license; libsndfile has its own LGPL license |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) | Finding a separately installed FFmpeg binary | Wrapper license and binary notices in the package |
| [FFmpeg](https://ffmpeg.org/) | Decoding, resampling and export | [LGPL/GPL conditions depend on the binary build](https://ffmpeg.org/legal.html) |
| [PyTorch](https://github.com/pytorch/pytorch) | Optional Demucs inference | Upstream BSD-style license and dependency notices |

The MIT license on this repository does not relicense dependencies, recordings, model weights, or recognition services. ShazamIO's open-source status does not make Shazam's service an open-source or availability-guaranteed catalog. Source separation does not establish permission to redistribute an input or reference recording.

Existing workflow projects are acknowledged in [related-projects.md](docs/related-projects.md). They were inspected for overlap, not incorporated as copied code. No commercial audio, credentials, cookies or checkpoints are included in the source archive.
