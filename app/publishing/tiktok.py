"""
TikTok Content Posting API client — spec sections 3.5/6.

Implements the real OAuth 2.0 + PULL_FROM_URL video-init flow per
TikTok's published Content Posting API (v2). Requires:
  - a TikTok developer app with the "Content Posting API" product added
  - that app approved for the `video.publish` scope (TikTok reviews this)
  - TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET env vars set

Docs: https://developers.tiktok.com/doc/content-posting-api-get-started
"""
from __future__ import annotations

import requests

from app.publishing.base import PlatformClient, PublishError, NotConfiguredError
from app.publishing.config import (
    TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REDIRECT_URI, is_configured,
)

AUTH_BASE = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
VIDEO_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
VIDEO_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"


class TikTokClient(PlatformClient):
    name = "tiktok"

    def authorize_url(self, workspace_id: str, state: str) -> str:
        if not is_configured("tiktok"):
            raise NotConfiguredError(
                "TikTok isn't connected yet — set TIKTOK_CLIENT_KEY and "
                "TIKTOK_CLIENT_SECRET (from an approved TikTok developer app "
                "with the Content Posting API product) before connecting."
            )
        params = {
            "client_key": TIKTOK_CLIENT_KEY,
            "scope": "user.info.basic,video.publish",
            "response_type": "code",
            "redirect_uri": TIKTOK_REDIRECT_URI,
            "state": state,
        }
        query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
        return f"{AUTH_BASE}?{query}"

    def exchange_code(self, code: str) -> dict:
        resp = requests.post(TOKEN_URL, data={
            "client_key": TIKTOK_CLIENT_KEY,
            "client_secret": TIKTOK_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": TIKTOK_REDIRECT_URI,
        }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
        data = resp.json()
        if resp.status_code != 200 or "access_token" not in data:
            raise PublishError(f"TikTok token exchange failed: {data}")
        return data

    def refresh_token(self, refresh_token: str) -> dict:
        resp = requests.post(TOKEN_URL, data={
            "client_key": TIKTOK_CLIENT_KEY,
            "client_secret": TIKTOK_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }, timeout=30)
        data = resp.json()
        if resp.status_code != 200:
            raise PublishError(f"TikTok token refresh failed: {data}")
        return data

    def publish_video(self, access_token: str, video_path: str, title: str,
                       hashtags: list[str], account_meta: dict) -> str:
        """Uses TikTok's FILE_UPLOAD source (direct binary upload) rather
        than PULL_FROM_URL, since our clips live on private storage without
        a public URL by default."""
        caption = f"{title} {' '.join(hashtags)}".strip()
        import os
        size = os.path.getsize(video_path)

        init_resp = requests.post(
            VIDEO_INIT_URL,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={
                "post_info": {
                    "title": caption[:150],
                    "privacy_level": "SELF_ONLY",  # safest default; creator flips to public in-app
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": size,
                    "chunk_size": size,
                    "total_chunk_count": 1,
                },
            },
            timeout=30,
        )
        init_data = init_resp.json()
        if init_resp.status_code != 200 or "data" not in init_data:
            raise PublishError(f"TikTok video init failed: {init_data}")

        upload_url = init_data["data"]["upload_url"]
        publish_id = init_data["data"]["publish_id"]

        with open(video_path, "rb") as f:
            video_bytes = f.read()
        upload_resp = requests.put(
            upload_url,
            headers={
                "Content-Type": "video/mp4",
                "Content-Range": f"bytes 0-{size - 1}/{size}",
            },
            data=video_bytes,
            timeout=300,
        )
        if upload_resp.status_code not in (200, 201):
            raise PublishError(f"TikTok video upload failed: {upload_resp.status_code} {upload_resp.text[:500]}")

        return publish_id

    def get_metrics(self, access_token: str, platform_post_id: str) -> dict:
        resp = requests.post(
            VIDEO_STATUS_URL,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"publish_id": platform_post_id},
            timeout=30,
        )
        data = resp.json()
        if resp.status_code != 200:
            raise PublishError(f"TikTok status fetch failed: {data}")
        # TikTok's public status endpoint reports publish status, not
        # view/like counts directly (those require the separate Display
        # API with additional review) -- surface what's available.
        return {"raw_status": data.get("data", {})}
