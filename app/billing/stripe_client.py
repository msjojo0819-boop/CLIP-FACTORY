"""
Stripe integration — spec 3.8/6/8 ("Stripe billing integration, self-serve
upgrade/downgrade/cancel").

Real Stripe API calls via the official `stripe` Python SDK. Requires
STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET env vars (from your Stripe
Dashboard) plus a Price ID per paid plan (see plans.py). Without a secret
key set, checkout session creation raises a clear "billing not configured"
error instead of pretending to charge someone.
"""
from __future__ import annotations

import os

import stripe

from app.billing.plans import get_plan, stripe_price_id
from app import workspaces

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
CHECKOUT_SUCCESS_URL = os.environ.get("CLIP_FACTORY_CHECKOUT_SUCCESS_URL", "http://localhost:5173/billing?success=true")
CHECKOUT_CANCEL_URL = os.environ.get("CLIP_FACTORY_CHECKOUT_CANCEL_URL", "http://localhost:5173/billing?canceled=true")


class BillingNotConfigured(Exception):
    pass


def _client():
    if not STRIPE_SECRET_KEY:
        raise BillingNotConfigured(
            "Stripe isn't configured yet — set STRIPE_SECRET_KEY (and "
            "STRIPE_PRICE_* for each paid plan) from your Stripe Dashboard."
        )
    stripe.api_key = STRIPE_SECRET_KEY
    return stripe


def create_checkout_session(workspace_id: str, plan_id: str, customer_email: str | None = None) -> str:
    client = _client()
    price_id = stripe_price_id(plan_id)
    if not price_id:
        raise BillingNotConfigured(f"No Stripe price configured for plan '{plan_id}' (set its env var in plans.py).")

    ws = workspaces.get_or_create_workspace(workspace_id)
    session = client.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=CHECKOUT_SUCCESS_URL,
        cancel_url=CHECKOUT_CANCEL_URL,
        customer_email=customer_email,
        metadata={"workspace_id": workspace_id, "plan_id": plan_id},
        subscription_data={"metadata": {"workspace_id": workspace_id, "plan_id": plan_id}},
    )
    return session.url


def create_billing_portal_session(stripe_customer_id: str) -> str:
    """Self-serve upgrade/downgrade/cancel, per spec 3.8."""
    client = _client()
    session = client.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=CHECKOUT_SUCCESS_URL,
    )
    return session.url


def handle_webhook_event(payload: bytes, sig_header: str) -> dict:
    client = _client()
    if not STRIPE_WEBHOOK_SECRET:
        raise BillingNotConfigured("STRIPE_WEBHOOK_SECRET is not set — can't verify webhook signatures.")

    event = client.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    obj = event["data"]["object"]
    event_type = event["type"]

    if event_type in ("checkout.session.completed",):
        workspace_id = obj.get("metadata", {}).get("workspace_id")
        plan_id = obj.get("metadata", {}).get("plan_id")
        if workspace_id and plan_id:
            workspaces.update_workspace(workspace_id, plan=plan_id, stripe_customer_id=obj.get("customer"))

    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        workspace_id = obj.get("metadata", {}).get("workspace_id")
        if workspace_id:
            if event_type == "customer.subscription.deleted" or obj.get("status") in ("canceled", "unpaid"):
                workspaces.update_workspace(workspace_id, plan="free_trial")

    return {"handled": event_type}
