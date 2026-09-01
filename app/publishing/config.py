"""
Publishing credentials — spec section 6: "separate OAuth flows for
TikTok/Instagram/YouTube publishing permissions."

Every platform requires David to register a developer app on that
platform and get it approved for content-posting scopes (this is a
real, unavoidable step on every platform's side — Anthropic/Claude
cannot create these app registrations; a business must own them).
Credentials are read from environment variables so nothing secret ever
lives in source control. Until these are set, the OAuth authorize
endpoints return a clear "not configured" error instead of pretending
to work.
"""
import os

# TikTok Content Posting API — https://developers.tiktok.com/doc/content-posting-api-get-started
TIKTOK_CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")
TIKTOK_REDIRECT_URI = os.environ.get("TIKTOK_REDIRECT_URI", "http://localhost:8000/oauth/tiktok/callback")

# Meta Graph API (Instagram) — https://developers.facebook.com/docs/instagram-platform
META_APP_ID = os.environ.get("META_APP_ID", "")
META_APP_SECRET = os.environ.get("META_APP_SECRET", "")
META_REDIRECT_URI = os.environ.get("META_REDIRECT_URI", "http://localhost:8000/oauth/instagram/callback")

# YouTube Data API v3 — https://developers.google.com/youtube/v3/guides/uploading_a_video
YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REDIRECT_URI = os.environ.get("YOUTUBE_REDIRECT_URI", "http://localhost:8000/oauth/youtube/callback")

# Spec 9: "Rate limiting on publishing APIs to avoid tripping platform
# spam detection" — conservative defaults, one post per platform per
# workspace per this many seconds minimum.
MIN_SECONDS_BETWEEN_POSTS = {
    "tiktok": 60 * 5,
    "instagram": 60 * 5,
    "youtube": 60 * 2,
}


def is_configured(platform: str) -> bool:
    return {
        "tiktok": bool(TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET),
        "instagram": bool(META_APP_ID and META_APP_SECRET),
        "youtube": bool(YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET),
    }.get(platform, False)
