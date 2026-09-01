"""
Core data models — mirrors spec section 7 (Data Models / Core Entities).

Phase 1 only needs SourceVideo, Transcript, and Clip. Workspace/User/
ScheduledPost/UsageRecord are stubbed as simple dataclasses so the schema
already matches the full spec and Postgres models can be dropped in later
without changing the pipeline code.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class JobStatus(str, Enum):
    QUEUED = "queued"
    TRANSCRIBING = "transcribing"
    SCORING = "scoring"
    CUTTING = "cutting"
    DONE = "done"
    FAILED = "failed"


class ClipStatus(str, Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    PUBLISHED = "published"


@dataclass
class Word:
    word: str
    start: float
    end: float


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    speaker: Optional[str] = None
    sentiment_score: float = 0.0
    avg_confidence: float = 1.0
    words: list["Word"] = field(default_factory=list)


@dataclass
class Transcript:
    id: str
    source_video_id: str
    language: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    low_confidence_segment_indices: list[int] = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        return d


@dataclass
class SourceVideo:
    id: str
    workspace_id: str
    filename: str
    path: str
    upload_type: str  # "file" or "link"
    duration: float = 0.0
    status: JobStatus = JobStatus.QUEUED
    transcript_id: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self):
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, JobStatus) else self.status
        return d


@dataclass
class Clip:
    id: str
    source_video_id: str
    start: float
    end: float
    score: float
    reason: str  # human-readable "why this was picked"
    aspect_ratios: list[str] = field(default_factory=lambda: ["16:9"])
    caption_style: Optional[str] = None
    logo_applied: bool = False
    status: ClipStatus = ClipStatus.DRAFT
    path: Optional[str] = None  # primary/16:9 path, kept for backward compat
    aspect_paths: dict = field(default_factory=dict)  # {"16:9": path, "9:16": path, "1:1": path}
    thumbnail_path: Optional[str] = None
    censored: bool = False
    platform_post_ids: dict = field(default_factory=dict)
    title_suggestions: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)  # non-fatal stage failures for this clip (reframe/caption/censor) — surfaced in the review UI instead of silently dropped

    def to_dict(self):
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, ClipStatus) else self.status
        return d


class PostStatus(str, Enum):
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class ScheduledPost:
    id: str
    clip_id: str
    workspace_id: str
    platform: str  # "tiktok" | "instagram" | "youtube"
    scheduled_time: str  # ISO8601
    status: PostStatus = PostStatus.SCHEDULED
    title: str = ""
    hashtags: list[str] = field(default_factory=list)
    published_metrics: dict = field(default_factory=dict)  # views/likes/completion_rate
    platform_post_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self):
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, PostStatus) else self.status
        return d


@dataclass
class UsageRecord:
    id: str
    workspace_id: str
    minutes_processed: float
    billing_period: str  # "YYYY-MM"

    def to_dict(self):
        return asdict(self)
