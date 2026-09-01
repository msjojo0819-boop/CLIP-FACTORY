"""
Minimal JSON-file "database" so Phase 1 runs with zero external services.

Swap this module for real Postgres models (spec section 6/7) later — every
other module talks to the store through the functions below, not to files
directly, so that swap doesn't touch the pipeline logic.
"""
import json
import threading
from pathlib import Path
from typing import Any

from app.config import JOBS_DIR

_lock = threading.Lock()


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def create_job(job_id: str, data: dict[str, Any]) -> None:
    with _lock:
        _job_path(job_id).write_text(json.dumps(data, indent=2, default=str))


def read_job(job_id: str) -> dict[str, Any] | None:
    p = _job_path(job_id)
    if not p.exists():
        return None
    with _lock:
        return json.loads(p.read_text())


def update_job(job_id: str, **fields) -> dict[str, Any]:
    with _lock:
        p = _job_path(job_id)
        data = json.loads(p.read_text()) if p.exists() else {}
        data.update(fields)
        p.write_text(json.dumps(data, indent=2, default=str))
        return data


def list_jobs() -> list[dict[str, Any]]:
    with _lock:
        return [json.loads(p.read_text()) for p in sorted(JOBS_DIR.glob("*.json"))]
