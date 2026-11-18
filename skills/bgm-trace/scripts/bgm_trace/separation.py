from __future__ import annotations

import os
from pathlib import Path
import time

import numpy as np
import soundfile as sf

from .media import TraceError, digest


def separate(source: Path, target: Path, device: str = "auto", shifts: int = 2, model_repo: Path | None = None) -> dict:
    if target.exists():
        raise TraceError("Separation target already exists; use a new job directory.")
    try:
        import torch
        from demucs.apply import apply_model
        from demucs.pretrained import get_model
    except ImportError as exc:
        raise TraceError("Separation needs Demucs and PyTorch: install 'bgm-trace[separate]' or 'demucs>=4,<5' in this environment.") from exc
    started = time.monotonic()
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise TraceError("CUDA is unavailable in this Python environment. Use --device cpu or install a matching PyTorch build.")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    torch.manual_seed(42)
    # This is the official htdemucs_ft vocal specialist, not a media-supplied checkpoint.
    # Demucs 4.0.1 uses legacy torch.load; limit compatibility mode to model loading.
    old = os.environ.get("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD")
    os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"
    try:
        model = get_model("04573f0d", repo=model_repo).to(device).eval()
    finally:
        if old is None:
            os.environ.pop("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", None)
        else:
            os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = old
    data, rate = sf.read(source, dtype="float32", always_2d=True)
    if rate != model.samplerate or data.shape[1] != model.audio_channels:
        raise TraceError("Separation expects the prepared 44.1 kHz stereo source.wav.")
    wave = torch.from_numpy(data.T.copy()).to(device)
    reference = wave.mean(0)
    mean, std = reference.mean(), reference.std()
    if float(std) < 1e-7:
        music = data
    else:
        with torch.inference_mode():
            stems = apply_model(model, ((wave - mean) / std)[None], device=device, shifts=shifts, split=True, overlap=.5, progress=False)[0] * std + mean
        vocals = stems[model.sources.index("vocals")].cpu().numpy().T
        music = data - vocals
    if not np.isfinite(music).all():
        raise TraceError("Separation produced non-finite samples.")
    peak = float(np.max(np.abs(music)))
    gain = min(1., .98 / max(peak, 1e-9))
    sf.write(target, music * gain, rate, subtype="PCM_24")
    return {"file": target.name, "role": "model_separated_music", "model": "htdemucs_ft vocals specialist 04573f0d", "method": "source minus estimated vocals", "device": device, "shifts": shifts, "gain": gain, "seconds": len(data) / rate, "elapsed_seconds": round(time.monotonic() - started, 3), "sha256": digest(target), "limitation": "Dialogue, sound effects, and separation artifacts may remain; no guarantee of a pristine instrumental."}
