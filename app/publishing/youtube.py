"""
YouTube Shorts publishing via the YouTube Data API v3 — spec sections 3.5/6.

Implements real OAuth 2.0 (Google) + resumable video upload. A vertical
video under 60s uploaded with #Shorts in the title/description is treated
by YouTube as a Short automatically — there's no separate "Shorts API".
Requires:
  - a Google Cloud project with the YouTube Data API v3 enabled
  - an OAuth consent screen configured + verified for the
    youtube.upload scope (Google reviews this for public apps)
  - YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET env vars

Docs: https://developers.google.com/youtube/v3/guides/uploading_a_video
"""
from __future__ import annotations

import os

import requests

from app.publishing.base import PlatformClient, PublishError, NotConfiguredError
from app.publishing.config import (
    YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REDIRECT_URI, is_configured,
)

AUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_INIT_URL = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"


class YouTubeClient(PlatformClient):
    name = "youtube"

    def authorize_url(self, workspace_id: str, state: str) -> str:
        if not is_configured("youtube"):
            raise NotConfiguredError(
                "YouTube isn't connected yet — set YOUTUBE_CLIENT_ID and "
                "YOUTUBE_CLIENT_SECRET (from a Google Cloud OAuth client "
                "with YouTube Data API v3 enabled) before connecting."
            )
        params = {
            "client_id": YOUTUBE_CLIENT_ID,
            "redirect_uri": YOUTUBE_REDIRECT_URI,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
        return f"{AUTH_BASE}?{query}"

    def exchange_code(self, code: str) -> dict:
        resp = requests.post(TOKEN_URL, data={
            "client_id": YOUTUBE_CLIENT_ID,
            "client_secret": YOUTUBE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": YOUTUBE_REDIRECT_URI,
        }, timeout=30)
        data = resp.json()
        if resp.status_code != 200 or "access_token" not in data:
            raise PublishError(f"YouTube token exchange failed: {data}")
        return data

    def refresh_token(self, refresh_token: str) -> dict:
        resp = requests.post(TOKEN_URL, data={
            "client_id": YOUTUBE_CLIENT_ID,
            "client_secret": YOUTUBE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }, timeout=30)
        data = resp.json()
        if resp.status_code != 200:
            raise PublishError(f"YouTube token refresh failed: {data}")
        return data

    def publish_video(self, access_token: str, video_path: str, title: str,
                       hashtags: list[str], account_meta: dict) -> str:
        description = " ".join(hashtags)
        size = os.path.getsize(video_path)

        init_resp = requests.post(
            UPLOAD_INIT_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(size),
            },
            json={
                "snippet": {
                    "title": (title[:97] + "...") if len(title) > 100 else title,
                    "description": description[:5000],
                    "tags": [h.lstrip("#") for h in hashtags][:15],
                    "categoryId": "22",
                },
                "status": {"privacyStatus": account_meta.get("privacy_status", "private"), "selfDeclaredMadeForKids": False},
            },
            timeout=30,
        )
        if init_resp.status_code != 200:
            raise PublishError(f"YouTube upload session init failed: {init_resp.status_code} {init_resp.text[:500]}")

        upload_url = init_resp.headers.get("Location")
        if not upload_url:
            raise PublishError("YouTube upload init did not return a resumable session URL.")

        with open(video_path, "rb") as f:
            video_bytes = f.read()

        upload_resp = requests.put(
            upload_url,
            headers={"Content-Type": "video/mp4", "Content-Length": str(size)},
            data=video_bytes,
            timeout=600,
        )
        if upload_resp.status_code not in (200, 201):
            raise PublishError(f"YouTube video upload failed: {upload_resp.status_code} {upload_resp.text[:500]}")

        video_id = upload_resp.json().get("id")
        if not video_id:
            raise PublishError(f"YouTube upload succeeded but no video id returned: {upload_resp.text[:500]}")
        return video_id

    def get_metrics(self, access_token: str, platform_post_id: str) -> dict:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "statistics", "id": platform_post_id},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        data = resp.json()
        if resp.status_code != 200:
            raise PublishError(f"YouTube metrics fetch failed: {data}")
        items = data.get("items", [])
        if not items:
            return {}
        stats = items[0].get("statistics", {})
        return {
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
        }
