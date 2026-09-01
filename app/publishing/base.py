"""
Common interface every platform client implements, so main.py and the
scheduler never branch on platform name beyond picking which client to use.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class PublishError(Exception):
    pass


class NotConfiguredError(PublishError):
    """Raised when a platform's developer credentials aren't set — this is
    an honest "you haven't registered/approved this app on the platform
    yet" error, not a bug."""


class PlatformClient(ABC):
    name: str

    @abstractmethod
    def authorize_url(self, workspace_id: str, state: str) -> str:
        """Returns the URL to send the user to for OAuth consent."""

    @abstractmethod
    def exchange_code(self, code: str) -> dict:
        """Exchanges an OAuth authorization code for tokens.
        Returns a dict with at least {access_token, refresh_token?, expires_in?}."""

    @abstractmethod
    def refresh_token(self, refresh_token: str) -> dict:
        """Refreshes an expired access token."""

    @abstractmethod
    def publish_video(self, access_token: str, video_path: str, title: str,
                       hashtags: list[str], account_meta: dict) -> str:
        """Uploads+publishes a video. Returns the platform's post/video id."""

    @abstractmethod
    def get_metrics(self, access_token: str, platform_post_id: str) -> dict:
        """Returns {views, likes, completion_rate} where available."""
