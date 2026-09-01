"""
Profanity audio censor — spec section 3.4 ("bleep audio + blur captions
for creators who need brand-safe versions"). Caption blur/masking is
handled in captions.py (censor_captions flag); this module handles the
audio bleep half.

Detects profane words from word-level transcript timestamps and overlays
a sine-wave "bleep" tone over each hit using ffmpeg's `volume`+`sine`
generator via filter_complex, muting the original audio under the bleep
so the word underneath isn't audible.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from app.config import CLIPS_DIR
from app.models import Word
from app.pipeline.captions import PROFANITY_WORDS


def find_profanity_hits(words: list[Word], clip_start: float, clip_end: float) -> list[tuple[float, float]]:
    hits = []
    for w in words:
        if not (clip_start <= w.start < clip_end):
            continue
        token = re.sub(r"[^a-zA-Z]", "", w.word).lower()
        if token in PROFANITY_WORDS:
            hits.append((w.start - clip_start, w.end - clip_start))
    return hits


def bleep_audio(source_clip_path: str, clip_id: str, aspect_suffix: str, hits: list[tuple[float, float]]) -> Path:
    out_path = CLIPS_DIR / f"{clip_id}_{aspect_suffix}_censored.mp4"

    if not hits:
        # nothing to censor; just copy through
        cmd = ["ffmpeg", "-y", "-i", str(source_clip_path), "-c", "copy", str(out_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0 or not out_path.exists():
            raise RuntimeError(f"ffmpeg censor passthrough failed: {result.stderr[-1000:]}")
        return out_path

    # mute original audio during each hit window, then mix in a sine tone
    # gated to only play during those windows.
    mute_expr = "+".join([f"between(t,{s:.3f},{e:.3f})" for s, e in hits])
    volume_filter = f"volume=0:enable='{mute_expr}'"

    tone_gate_terms = "+".join([f"between(t,{s:.3f},{e:.3f})" for s, e in hits])
    filter_complex = (
        f"[0:a]{volume_filter}[muted];"
        f"sine=frequency=1000[tone];"
        f"[tone]volume=1:enable='{tone_gate_terms}'[gated_tone];"
        f"[muted][gated_tone]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )

    cmd = [
        "ffmpeg", "-y", "-i", str(source_clip_path),
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"ffmpeg bleep censor failed for {clip_id}: {result.stderr[-1500:]}")
    return out_path
