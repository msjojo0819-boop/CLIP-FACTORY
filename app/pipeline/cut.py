"""
Clip cutting — spec section 3.3 (Phase 1 slice: 16:9 only, no captions/
reframe yet — those land in Phase 2 per the roadmap).

Cuts each candidate window out of the source video with ffmpeg. Re-encodes
(rather than stream-copy) so the cut lands exactly on the requested
timestamps instead of snapping to the nearest keyframe, which matters
because our cut points are already snapped to speech-pause boundaries
upstream in score.py.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from app.config import CLIPS_DIR
from app.pipeline.score import CandidateClip


class CutError(Exception):
    pass


def cut_clip(source_video_path: str, clip_id: str, candidate: CandidateClip) -> Path:
    out_path = CLIPS_DIR / f"{clip_id}_16x9.mp4"
    duration = candidate.end - candidate.start

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{candidate.start:.2f}",
        "-i", str(source_video_path),
        "-t", f"{duration:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0 or not out_path.exists():
        raise CutError(f"ffmpeg failed cutting clip {clip_id}: {result.stderr[-2000:]}")
    return out_path
