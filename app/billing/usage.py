"""
Usage metering — spec 3.8 ("Usage metering: minutes of source video
processed per month") + section 7 (UsageRecord entity).

JSON-file store, same pattern as the rest of Phase 1's persistence layer.
record_usage() is called from the pipeline runner right after a source
video's duration is known. enforce_plan_limit() is called before a job is
allowed to start.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.config import STORAGE_DIR
from app.billing.plans import get_plan, OVERAGE_PER_MINUTE_USD, FREE_TRIAL_MAX_VIDEOS, FREE_TRIAL_MAX_CLIPS
from app.models import UsageRecord, new_id

USAGE_DIR = STORAGE_DIR / "usage"
USAGE_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()


def _current_period() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def _path(workspace_id: str, period: str) -> Path:
    return USAGE_DIR / f"{workspace_id}_{period}.json"


def record_usage(workspace_id: str, minutes: float) -> UsageRecord:
    period = _current_period()
    p = _path(workspace_id, period)
    with _lock:
        if p.exists():
            data = json.loads(p.read_text())
            data["minutes_processed"] = data.get("minutes_processed", 0) + minutes
        else:
            data = {
                "id": new_id(), "workspace_id": workspace_id,
                "minutes_processed": minutes, "billing_period": period,
            }
        p.write_text(json.dumps(data, indent=2))
    return UsageRecord(**data)


def get_usage(workspace_id: str, period: str | None = None) -> UsageRecord:
    period = period or _current_period()
    p = _path(workspace_id, period)
    if not p.exists():
        return UsageRecord(id="", workspace_id=workspace_id, minutes_processed=0.0, billing_period=period)
    return UsageRecord(**json.loads(p.read_text()))


class PlanLimitExceeded(Exception):
    pass


def estimate_overage_cost(workspace_id: str, plan_id: str) -> float:
    plan = get_plan(plan_id)
    usage = get_usage(workspace_id)
    if plan.minutes_per_month is None:
        return 0.0
    over = max(0.0, usage.minutes_processed - plan.minutes_per_month)
    return round(over * OVERAGE_PER_MINUTE_USD, 2)


def enforce_plan_limit(workspace_id: str, plan_id: str, video_minutes: float, video_count_this_trial: int = 0) -> None:
    """Raises PlanLimitExceeded with a clear message if this upload would
    violate the plan's caps. Free trial has a hard cap (spec 3.8); paid
    plans allow overage (billed automatically) rather than hard-blocking."""
    plan = get_plan(plan_id)
    if plan_id == "free_trial":
        if video_count_this_trial >= FREE_TRIAL_MAX_VIDEOS:
            raise PlanLimitExceeded(
                f"Free trial is limited to {FREE_TRIAL_MAX_VIDEOS} video and "
                f"{FREE_TRIAL_MAX_CLIPS} clips (watermarked). Upgrade to process more."
            )
    # paid plans: no hard block, overage bills automatically per spec 3.8/8
