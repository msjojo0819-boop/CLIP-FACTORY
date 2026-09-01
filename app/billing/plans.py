"""
Plan definitions — spec section 8 (Monetization table), verbatim.

Stripe Price IDs are read from env vars (you create these in the Stripe
Dashboard/CLI — they're account-specific and can't be hardcoded here).
Until they're set, checkout session creation fails with a clear
"plan not configured" error rather than silently charging the wrong amount.
"""
import os
from dataclasses import dataclass


@dataclass
class Plan:
    id: str
    name: str
    price_usd: float | None  # None = usage-based / contact
    minutes_per_month: float | None  # None = unlimited
    max_workspaces: int | None  # None = unlimited
    team_seats: bool
    direct_publishing: bool
    analytics: bool
    priority_processing: bool
    stripe_price_id_env: str | None


PLANS: dict[str, Plan] = {
    "free_trial": Plan(
        id="free_trial", name="Free Trial", price_usd=0.0,
        minutes_per_month=None, max_workspaces=1, team_seats=False,
        direct_publishing=False, analytics=False, priority_processing=False,
        stripe_price_id_env=None,
    ),
    "creator": Plan(
        id="creator", name="Creator", price_usd=29.0,
        minutes_per_month=300, max_workspaces=1, team_seats=False,
        direct_publishing=False, analytics=False, priority_processing=False,
        stripe_price_id_env="STRIPE_PRICE_CREATOR",
    ),
    "pro": Plan(
        id="pro", name="Pro", price_usd=79.0,
        minutes_per_month=900, max_workspaces=3, team_seats=False,
        direct_publishing=True, analytics=True, priority_processing=False,
        stripe_price_id_env="STRIPE_PRICE_PRO",
    ),
    "agency": Plan(
        id="agency", name="Agency", price_usd=199.0,
        minutes_per_month=None, max_workspaces=None, team_seats=True,
        direct_publishing=True, analytics=True, priority_processing=True,
        stripe_price_id_env="STRIPE_PRICE_AGENCY",
    ),
}

OVERAGE_PER_MINUTE_USD = float(os.environ.get("CLIP_FACTORY_OVERAGE_RATE", "0.10"))
FREE_TRIAL_MAX_VIDEOS = 1
FREE_TRIAL_MAX_CLIPS = 3


def get_plan(plan_id: str) -> Plan:
    if plan_id not in PLANS:
        raise ValueError(f"Unknown plan '{plan_id}'. Valid: {list(PLANS)}")
    return PLANS[plan_id]


def stripe_price_id(plan_id: str) -> str | None:
    plan = get_plan(plan_id)
    if not plan.stripe_price_id_env:
        return None
    return os.environ.get(plan.stripe_price_id_env)
