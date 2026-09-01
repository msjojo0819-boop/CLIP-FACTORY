"""
Analytics loop — spec section 3.7.

Three pieces:
  1. Metrics pull-back: for every PUBLISHED ScheduledPost, call the
     platform's get_metrics() and store the result on the post.
  2. Personalization: correlate which moment-scoring "reasons" (keyword
     cue / emotional language / audio energy spike) showed up on clips
     that actually performed well for THIS workspace, and turn that into
     per-reason weight multipliers that score.py applies on the next run
     — "the moment-scoring engine's confidence adjusts based on which of
     its picks actually performed well for that specific creator."
  3. Dashboard: best clip this week, best caption style, best clip length.

Everything here is real arithmetic over real stored data — there's no
model to "train" in the ML sense; the personalization is a weighted
average of historical performance per feature, which is exactly the
right scope for what section 3.7 describes (not a claim of deep learning).
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import STORAGE_DIR
from app import store, scheduler, workspaces
from app.publishing.registry import get_client
from app.publishing.base import PublishError

WEIGHTS_DIR = STORAGE_DIR / "scoring_weights"
WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()

DEFAULT_WEIGHTS = {
    "keyword/topic cue": 1.0,
    "emotional language": 1.0,
    "audio energy spike": 1.0,
}


def _weights_path(workspace_id: str) -> Path:
    return WEIGHTS_DIR / f"{workspace_id}.json"


def get_scoring_weights(workspace_id: str) -> dict[str, float]:
    p = _weights_path(workspace_id)
    if not p.exists():
        return dict(DEFAULT_WEIGHTS)
    with _lock:
        data = json.loads(p.read_text())
    return {**DEFAULT_WEIGHTS, **data}


def _find_clip(clip_id: str) -> dict | None:
    for job in store.list_jobs():
        for clip in job.get("clips", []):
            if clip["id"] == clip_id:
                return clip
    return None


def _primary_metric_value(metrics: dict) -> float:
    """Normalizes different platforms' metric shapes into one comparable
    'engagement' number: prefer views/plays, fall back to likes."""
    for key in ("views", "plays", "play_count"):
        if key in metrics:
            try:
                return float(metrics[key])
            except (TypeError, ValueError):
                pass
    for key in ("likes", "like_count", "total_interactions"):
        if key in metrics:
            try:
                return float(metrics[key])
            except (TypeError, ValueError):
                pass
    return 0.0


def pull_metrics_for_workspace(workspace_id: str) -> list[dict]:
    """Calls each connected platform's get_metrics() for every published
    post in this workspace and stores results. Returns the updated posts.
    Silently skips posts on platforms that aren't connected/configured —
    metrics pull-back is best-effort, not a hard dependency."""
    updated = []
    for post in scheduler.list_posts(workspace_id):
        if post.get("status") != "published" or not post.get("platform_post_id"):
            continue
        account = workspaces.get_account(workspace_id, post["platform"])
        if not account:
            continue
        access_token, _ = account
        try:
            client = get_client(post["platform"])
            metrics = client.get_metrics(access_token, post["platform_post_id"])
        except (PublishError, ValueError):
            continue
        updated.append(scheduler.update_post(post["id"], published_metrics=metrics))
    return updated


def recompute_scoring_weights(workspace_id: str) -> dict[str, float]:
    """Weighted-average update: for each scoring 'reason' tag, compare the
    average engagement of clips that had that reason vs. clips that
    didn't, and nudge the weight up/down proportionally. Weights are
    clamped to [0.5, 2.0] so one viral fluke can't blow up the model."""
    reason_engagement: dict[str, list[float]] = {}
    baseline_engagement: list[float] = []

    for post in scheduler.list_posts(workspace_id):
        if post.get("status") != "published":
            continue
        clip = _find_clip(post["clip_id"])
        if not clip:
            continue
        engagement = _primary_metric_value(post.get("published_metrics") or {})
        reasons = [r.strip() for r in (clip.get("reason") or "").split(",") if r.strip()]
        baseline_engagement.append(engagement)
        for r in reasons:
            reason_engagement.setdefault(r, []).append(engagement)

    if not baseline_engagement:
        return get_scoring_weights(workspace_id)  # not enough data yet

    overall_avg = sum(baseline_engagement) / len(baseline_engagement)
    weights = dict(DEFAULT_WEIGHTS)

    for reason, values in reason_engagement.items():
        if reason not in weights or not values or overall_avg <= 0:
            continue
        reason_avg = sum(values) / len(values)
        ratio = reason_avg / overall_avg
        # smooth toward the new ratio rather than snapping to it outright
        weights[reason] = max(0.5, min(2.0, 0.5 * weights[reason] + 0.5 * ratio))

    with _lock:
        _weights_path(workspace_id).write_text(json.dumps(weights, indent=2))
    return weights


def dashboard(workspace_id: str, days: int = 7) -> dict[str, Any]:
    """Simple performance dashboard (spec 3.7): best clip this week,
    best-performing caption style, best-performing clip length."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = []

    for post in scheduler.list_posts(workspace_id):
        if post.get("status") != "published":
            continue
        try:
            sched = datetime.fromisoformat(post["scheduled_time"])
            if sched.tzinfo is None:
                sched = sched.replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        clip = _find_clip(post["clip_id"])
        if not clip:
            continue
        engagement = _primary_metric_value(post.get("published_metrics") or {})
        rows.append({
            "post": post, "clip": clip, "engagement": engagement,
            "in_window": sched >= cutoff,
            "length_bucket": _length_bucket(clip["end"] - clip["start"]),
        })

    if not rows:
        return {
            "best_clip_this_week": None,
            "best_caption_style": None,
            "best_clip_length": None,
            "sample_size": 0,
        }

    window_rows = [r for r in rows if r["in_window"]] or rows
    best = max(window_rows, key=lambda r: r["engagement"])

    by_style: dict[str, list[float]] = {}
    by_length: dict[str, list[float]] = {}
    for r in rows:
        style = r["clip"].get("caption_style") or "unknown"
        by_style.setdefault(style, []).append(r["engagement"])
        by_length.setdefault(r["length_bucket"], []).append(r["engagement"])

    best_style = max(by_style.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))[0] if by_style else None
    best_length = max(by_length.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))[0] if by_length else None

    return {
        "best_clip_this_week": {
            "clip_id": best["clip"]["id"],
            "engagement": best["engagement"],
            "platform": best["post"]["platform"],
            "title": best["post"].get("title"),
        },
        "best_caption_style": best_style,
        "best_clip_length": best_length,
        "sample_size": len(rows),
        "scoring_weights": get_scoring_weights(workspace_id),
    }


def _length_bucket(seconds: float) -> str:
    if seconds < 30:
        return "under_30s"
    if seconds < 60:
        return "30_60s"
    if seconds < 120:
        return "60_120s"
    return "over_120s"


def refresh(workspace_id: str) -> dict[str, Any]:
    """One call that does the full loop: pull metrics, recompute weights,
    return the dashboard."""
    pull_metrics_for_workspace(workspace_id)
    recompute_scoring_weights(workspace_id)
    return dashboard(workspace_id)
