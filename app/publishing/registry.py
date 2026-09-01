from app.publishing.tiktok import TikTokClient
from app.publishing.instagram import InstagramClient
from app.publishing.youtube import YouTubeClient

CLIENTS = {
    "tiktok": TikTokClient(),
    "instagram": InstagramClient(),
    "youtube": YouTubeClient(),
}


def get_client(platform: str):
    client = CLIENTS.get(platform)
    if not client:
        raise ValueError(f"Unknown platform '{platform}'. Supported: {list(CLIENTS)}")
    return client
