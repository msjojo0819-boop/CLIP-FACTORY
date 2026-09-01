"""
ScheduledPost store + rate-limited publish executor — spec sections 3.5
(Content Calendar / drip release), 3.6, and 9 ("rate limiting on
publishing APIs to avoid tripping platform spam detection").

Like store.py/workspaces.py, this is a JSON-file store. A lightweight
background loop (started from main.py's startup event) checks for posts
whose scheduled_time has arrived and publishes them via the appropriate
platform client, enforcing a minimum spacing between posts per
platform+workspace.
"""
from __future__ import annotations

import json
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import STORAGE_DIR
from app.models import PostStatus, new_id
from app.publishing.config import MIN_SECONDS_BETWEEN_POSTS
from app.publishing.registry import get_client
from app.publishing.base import PublishError

POSTS_DIR = STORAGE_DIR / "scheduled_posts"
POSTS_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()
_last_post_time: dict[tuple[str, str], float] = {}  # (workspace_id, platform) -> epoch seconds


def _path(post_id: str) -> Path:
    return POSTS_DIR / f"{post_id}.json"


def create_post(data: dict[str, Any]) -> dict:
    post_id = data.get("id") or new_id()
    data["id"] = post_id
    with _lock:
        _path(post_id).write_text(json.dumps(data, indent=2, default=str))
    return data


def update_post(post_id: str, **fields) -> dict:
    with _lock:
        p = _path(post_id)
        data = json.loads(p.read_text()) if p.exists() else {}
        data.update(fields)
        p.write_text(json.dumps(data, indent=2, default=str))
        return data


def get_post(post_id: str) -> dict | None:
    p = _path(post_id)
    return json.loads(p.read_text()) if p.exists() else None


def list_posts(workspace_id: str | None = None) -> list[dict]:
    with _lock:
        posts = [json.loads(p.read_text()) for p in sorted(POSTS_DIR.glob("*.json"))]
    if workspace_id:
        posts = [p for p in posts if p.get("workspace_id") == workspace_id]
    return posts


def delete_post(post_id: str) -> bool:
    p = _path(post_id)
    if p.exists():
        p.unlink()
        return True
    return False


def _rate_limit_ok(workspace_id: str, platform: str) -> bool:
    key = (workspace_id, platform)
    min_gap = MIN_SECONDS_BETWEEN_POSTS.get(platform, 60)
    last = _last_post_time.get(key)
    return last is None or (time.time() - last) >= min_gap


def _do_publish(post: dict, clip_path: str, access_token: str, account_meta: dict) -> None:
    platform = post["platform"]
    client = get_client(platform)
    try:
        update_post(post["id"], status=PostStatus.PUBLISHING.value)
        platform_post_id = client.publish_video(
            access_token, clip_path, post.get("title", ""), post.get("hashtags", []), account_meta,
        )
        _last_post_time[(post["workspace_id"], platform)] = time.time()
        update_post(post["id"], status=PostStatus.PUBLISHED.value, platform_post_id=platform_post_id, error=None)
    except PublishError as e:
        update_post(post["id"], status=PostStatus.FAILED.value, error=str(e))
    except Exception as e:  # noqa: BLE001
        update_post(post["id"], status=PostStatus.FAILED.value, error=f"{e}\n{traceback.format_exc()[-800:]}")


def try_publish_due_posts(resolve_clip_path, resolve_account) -> None:
    """Called periodically. `resolve_clip_path(clip_id) -> str | None` and
    `resolve_account(workspace_id, platform) -> (access_token, account_meta) | None`
    are injected so this module doesn't import app.store / app.workspaces
    directly (keeps it independently testable).
    """
    now = datetime.now(timezone.utc)
    for post in list_posts():
        if post.get("status") != PostStatus.SCHEDULED.value:
            continue
        try:
            sched = datetime.fromisoformat(post["scheduled_time"])
        except (KeyError, ValueError):
            continue
        if sched.tzinfo is None:
            sched = sched.replace(tzinfo=timezone.utc)
        if sched > now:
            continue
        if not _rate_limit_ok(post["workspace_id"], post["platform"]):
            continue  # will retry next tick

        clip_path = resolve_clip_path(post["clip_id"])
        account = resolve_account(post["workspace_id"], post["platform"])
        if not clip_path or not account:
            update_post(post["id"], status=PostStatus.FAILED.value,
                        error="Missing clip file or platform account connection at publish time.")
            continue

        access_token, account_meta = account
        _do_publish(post, clip_path, access_token, account_meta)


def start_background_loop(resolve_clip_path, resolve_account, interval_seconds: int = 30):
    def _loop():
        while True:
            try:
                try_publish_due_posts(resolve_clip_path, resolve_account)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(interval_seconds)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t
