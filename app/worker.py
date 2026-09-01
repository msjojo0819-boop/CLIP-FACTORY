"""
Minimal background worker — a bounded thread pool standing in for the
"queue-based worker pool" the spec calls for in section 6. CPU/GPU-heavy
transcription and rendering run off the request thread so the API stays
responsive, satisfying the same architectural requirement as Celery/RQ
without needing Redis in Phase 1. Swap `submit()`'s body for
`celery_app.send_task(...)` later; nothing else in the codebase needs to
change since callers only ever see job_id + polling.
"""
from concurrent.futures import ThreadPoolExecutor

from app.pipeline.runner import run_pipeline

_executor = ThreadPoolExecutor(max_workers=2)


def submit(job_id, source_video_id, source_path, min_clips, max_clips,
           min_clip_seconds, max_clip_seconds, sensitivity,
           workspace_id="default", aspect_ratios=None, caption_style=None,
           add_emoji=True, censor=False):
    _executor.submit(
        run_pipeline, job_id, source_video_id, source_path,
        min_clips, max_clips, min_clip_seconds, max_clip_seconds, sensitivity,
        workspace_id, aspect_ratios, caption_style, add_emoji, censor,
    )
