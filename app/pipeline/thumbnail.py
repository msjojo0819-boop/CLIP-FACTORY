"""
Thumbnail frame suggestion — spec section 3.5 ("Auto-generated thumbnail
frame suggestions — picks the highest-energy frame").

"Highest energy" = the sharpest, most visually active frame in the clip,
approximated via frame-to-frame pixel difference (motion) combined with
Laplacian variance (sharpness, to avoid picking a motion-blurred frame).
Real, deterministic, and runs in one pass over the clip.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.config import CLIPS_DIR


def pick_thumbnail_frame(clip_path: str, clip_id: str) -> Path | None:
    cap = cv2.VideoCapture(str(clip_path))
    if not cap.isOpened():
        return None

    prev_gray = None
    best_score = -1.0
    best_frame = None

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        motion = 0.0
        if prev_gray is not None and prev_gray.shape == gray.shape:
            motion = float(np.mean(cv2.absdiff(gray, prev_gray)))
        prev_gray = gray

        score = sharpness * 0.6 + motion * 40  # weighted combo
        if score > best_score:
            best_score = score
            best_frame = frame

    cap.release()
    if best_frame is None:
        return None

    out_path = CLIPS_DIR / f"{clip_id}_thumbnail.jpg"
    cv2.imwrite(str(out_path), best_frame)
    return out_path
