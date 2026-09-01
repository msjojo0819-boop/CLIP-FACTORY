"""
Workspace/Brand store — spec section 3.6 (Multi-Channel/Agency Mode) and
section 7 (Workspace/Brand entity). JSON-file backed like app/store.py;
same swap-for-Postgres story applies.

This module is used starting in Phase 2 (a clip's caption style/logo come
from its workspace's defaults) and is fleshed out further in Phase 6
(team members, roles, per-client usage).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.config import WORKSPACES_DIR

_lock = threading.Lock()


def _path(workspace_id: str) -> Path:
    return WORKSPACES_DIR / f"{workspace_id}.json"


DEFAULT_WORKSPACE = {
    "id": "default",
    "name": "My Brand",
    "logo_path": None,
    "default_caption_style": "bold_pop",
    "connected_accounts": {},  # {"tiktok": {...}, "instagram": {...}, "youtube": {...}}
    "team_members": [],  # [{"user_id":..., "role": "editor"|"admin"}]
    "plan": "free_trial",
}


def get_or_create_workspace(workspace_id: str) -> dict[str, Any]:
    p = _path(workspace_id)
    with _lock:
        if p.exists():
            return json.loads(p.read_text())
        data = dict(DEFAULT_WORKSPACE)
        data["id"] = workspace_id
        data["name"] = workspace_id
        p.write_text(json.dumps(data, indent=2))
        return data


def update_workspace(workspace_id: str, **fields) -> dict[str, Any]:
    with _lock:
        p = _path(workspace_id)
        data = json.loads(p.read_text()) if p.exists() else {**DEFAULT_WORKSPACE, "id": workspace_id}
        data.update(fields)
        p.write_text(json.dumps(data, indent=2))
        return data


def list_workspaces() -> list[dict[str, Any]]:
    with _lock:
        return [json.loads(p.read_text()) for p in sorted(WORKSPACES_DIR.glob("*.json"))]


def connect_account(workspace_id: str, platform: str, token_data: dict, account_meta: dict | None = None) -> dict:
    ws = get_or_create_workspace(workspace_id)
    accounts = ws.get("connected_accounts", {})
    accounts[platform] = {
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
        "expires_in": token_data.get("expires_in"),
        "account_meta": account_meta or {},
    }
    return update_workspace(workspace_id, connected_accounts=accounts)


def get_account(workspace_id: str, platform: str) -> tuple[str, dict] | None:
    ws = get_or_create_workspace(workspace_id)
    acct = (ws.get("connected_accounts") or {}).get(platform)
    if not acct or not acct.get("access_token"):
        return None
    return acct["access_token"], acct.get("account_meta", {})


# --- Team seats / role permissions (spec 3.6) -----------------------------
# "editor can generate/edit, cannot publish; admin can do both"

ROLE_PERMISSIONS = {
    "editor": {"generate", "edit"},
    "admin": {"generate", "edit", "publish", "manage_team", "manage_billing"},
}


class PermissionDenied(Exception):
    pass


def add_team_member(workspace_id: str, user_id: str, role: str) -> dict:
    if role not in ROLE_PERMISSIONS:
        raise ValueError(f"Unknown role '{role}'. Valid: {list(ROLE_PERMISSIONS)}")
    ws = get_or_create_workspace(workspace_id)
    members = ws.get("team_members", [])
    members = [m for m in members if m.get("user_id") != user_id]
    members.append({"user_id": user_id, "role": role})
    return update_workspace(workspace_id, team_members=members)


def remove_team_member(workspace_id: str, user_id: str) -> dict:
    ws = get_or_create_workspace(workspace_id)
    members = [m for m in ws.get("team_members", []) if m.get("user_id") != user_id]
    return update_workspace(workspace_id, team_members=members)


def get_role(workspace_id: str, user_id: str) -> str | None:
    ws = get_or_create_workspace(workspace_id)
    for m in ws.get("team_members", []):
        if m.get("user_id") == user_id:
            return m.get("role")
    return None


def require_permission(workspace_id: str, user_id: str, action: str) -> None:
    """Raises PermissionDenied unless user_id has `action` in this
    workspace. A user_id with no team_members entry is treated as the
    workspace owner (full access) — team seats are additive per spec 3.6."""
    ws = get_or_create_workspace(workspace_id)
    if not ws.get("team_members"):
        return  # no team configured yet == solo owner, full access
    role = get_role(workspace_id, user_id)
    if role is None:
        raise PermissionDenied(f"'{user_id}' is not a member of workspace '{workspace_id}'.")
    if action not in ROLE_PERMISSIONS.get(role, set()):
        raise PermissionDenied(f"Role '{role}' cannot perform '{action}'.")
