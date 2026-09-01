"""
Instagram publishing via the Meta Graph API — spec sections 3.5/6.

Implements the real container-then-publish flow for Reels. Requires:
  - a Meta developer app with Instagram Graph API access
  - the connected IG account be a Business/Creator account linked to a
    Facebook Page (Meta's hard requirement, not ours)
  - META_APP_ID / META_APP_SECRET env vars, and app review approval for
    instagram_content_publish

Docs: https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/content-publishing
"""
from __future__ import annotations

import time

import requests

from app.publishing.base import PlatformClient, PublishError, NotConfiguredError
from app.publishing.config import META_APP_ID, META_APP_SECRET, META_REDIRECT_URI, is_configured

GRAPH_BASE = "https://graph.facebook.com/v19.0"
AUTH_BASE = "https://www.facebook.com/v19.0/dialog/oauth"


class InstagramClient(PlatformClient):
    name = "instagram"

    def authorize_url(self, workspace_id: str, state: str) -> str:
        if not is_configured("instagram"):
            raise NotConfiguredError(
                "Instagram isn't connected yet — set META_APP_ID and "
                "META_APP_SECRET (from a Meta developer app approved for "
                "instagram_content_publish) before connecting."
            )
        params = {
            "client_id": META_APP_ID,
            "redirect_uri": META_REDIRECT_URI,
            "state": state,
            "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement",
            "response_type": "code",
        }
        query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
        return f"{AUTH_BASE}?{query}"

    def exchange_code(self, code: str) -> dict:
        resp = requests.get(f"{GRAPH_BASE}/oauth/access_token", params={
            "client_id": META_APP_ID,
            "client_secret": META_APP_SECRET,
            "redirect_uri": META_REDIRECT_URI,
            "code": code,
        }, timeout=30)
        data = resp.json()
        if resp.status_code != 200 or "access_token" not in data:
            raise PublishError(f"Instagram token exchange failed: {data}")

        # exchange short-lived token for a long-lived one (60 days)
        long_resp = requests.get(f"{GRAPH_BASE}/oauth/access_token", params={
            "grant_type": "fb_exchange_token",
            "client_id": META_APP_ID,
            "client_secret": META_APP_SECRET,
            "fb_exchange_token": data["access_token"],
        }, timeout=30)
        long_data = long_resp.json()
        return long_data if long_resp.status_code == 200 else data

    def refresh_token(self, refresh_token: str) -> dict:
        # Meta long-lived tokens are refreshed the same way as an exchange
        resp = requests.get(f"{GRAPH_BASE}/oauth/access_token", params={
            "grant_type": "fb_exchange_token",
            "client_id": META_APP_ID,
            "client_secret": META_APP_SECRET,
            "fb_exchange_token": refresh_token,
        }, timeout=30)
        data = resp.json()
        if resp.status_code != 200:
            raise PublishError(f"Instagram token refresh failed: {data}")
        return data

    def publish_video(self, access_token: str, video_path: str, title: str,
                       hashtags: list[str], account_meta: dict) -> str:
        """account_meta must include 'ig_user_id' and 'video_url' — Meta's
        Reels publishing API requires a publicly reachable URL for the
        video (it does not accept raw binary upload), so the caller is
        responsible for having the clip hosted somewhere fetchable (e.g.
        object storage with a signed URL) before calling this."""
        ig_user_id = account_meta.get("ig_user_id")
        video_url = account_meta.get("video_url")
        if not ig_user_id or not video_url:
            raise PublishError(
                "Instagram publishing needs 'ig_user_id' and a public "
                "'video_url' in account_meta (Graph API requires a "
                "fetchable URL, not a direct file upload)."
            )

        caption = f"{title}\n\n{' '.join(hashtags)}".strip()

        create_resp = requests.post(f"{GRAPH_BASE}/{ig_user_id}/media", data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption[:2200],
            "access_token": access_token,
        }, timeout=60)
        create_data = create_resp.json()
        if create_resp.status_code != 200 or "id" not in create_data:
            raise PublishError(f"Instagram media container creation failed: {create_data}")
        container_id = create_data["id"]

        # poll container status until FINISHED (Meta processes async)
        for _ in range(30):
            status_resp = requests.get(f"{GRAPH_BASE}/{container_id}", params={
                "fields": "status_code", "access_token": access_token,
            }, timeout=30)
            status_data = status_resp.json()
            code = status_data.get("status_code")
            if code == "FINISHED":
                break
            if code == "ERROR":
                raise PublishError(f"Instagram container processing failed: {status_data}")
            time.sleep(5)
        else:
            raise PublishError("Instagram container processing timed out after 150s.")

        publish_resp = requests.post(f"{GRAPH_BASE}/{ig_user_id}/media_publish", data={
            "creation_id": container_id,
            "access_token": access_token,
        }, timeout=30)
        publish_data = publish_resp.json()
        if publish_resp.status_code != 200 or "id" not in publish_data:
            raise PublishError(f"Instagram publish failed: {publish_data}")

        return publish_data["id"]

    def get_metrics(self, access_token: str, platform_post_id: str) -> dict:
        resp = requests.get(f"{GRAPH_BASE}/{platform_post_id}/insights", params={
            "metric": "plays,likes,comments,shares,total_interactions",
            "access_token": access_token,
        }, timeout=30)
        data = resp.json()
        if resp.status_code != 200:
            raise PublishError(f"Instagram metrics fetch failed: {data}")
        out = {}
        for item in data.get("data", []):
            values = item.get("values", [])
            if values:
                out[item["name"]] = values[0].get("value")
        return out
