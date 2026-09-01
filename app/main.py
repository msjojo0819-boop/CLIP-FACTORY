"""
Clip Factory — Phase 1 API.

Endpoints map to spec section 4 (User Flow) / section 5 (screens):
  POST /jobs            -> New Upload screen: accepts a video, kicks off
                            the pipeline in a background thread
  GET  /jobs/{id}        -> Processing View: live status polling
  GET  /jobs             -> Dashboard: recent uploads / queue
  GET  /jobs/{id}/clips  -> Clip Review Grid: candidate clips + scores
  GET  /clips/{job_id}/{clip_id}/download -> individual clip download (?aspect=16:9|9:16|1:1)
  GET  /jobs/{id}/download -> all clips as ZIP (spec 3.5 "one-click export")

Background processing uses a simple thread pool (see worker.py) rather
than Celery/Redis so Phase 1 has zero external service dependencies to
run. Swapping in a real job queue for production scale is a config
change, not a rewrite -- run_pipeline() in pipeline/runner.py is already
the single entrypoint a real worker would call.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse
import tempfile
import shutil
import uuid

from app.config import DEFAULT_MIN_CLIPS, DEFAULT_MAX_CLIPS, ABSOLUTE_MAX_CLIPS, \
    DEFAULT_MIN_CLIP_SECONDS, DEFAULT_MAX_CLIP_SECONDS, DEFAULT_ASPECT_RATIOS, \
    CAPTION_STYLES, LOGOS_DIR, TRANSCRIPTS_DIR, BASE_DIR
from app.models import SourceVideo, JobStatus, PostStatus, new_id
from app.pipeline import ingest
from app import store, workspaces, scheduler, analytics
from app.worker import submit
from app.publishing.registry import get_client
from app.publishing.base import PublishError, NotConfiguredError
from app.billing import usage as billing_usage, stripe_client
from app.billing.plans import PLANS, get_plan
from fastapi import Request, Header

app = FastAPI(title="Clip Factory API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your real frontend origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/jobs")
async def create_job(
    file: UploadFile = File(...),
    workspace_id: str = Form("default"),
    min_clips: int = Form(DEFAULT_MIN_CLIPS),
    max_clips: int = Form(DEFAULT_MAX_CLIPS),
    min_clip_seconds: int = Form(DEFAULT_MIN_CLIP_SECONDS),
    max_clip_seconds: int = Form(DEFAULT_MAX_CLIP_SECONDS),
    sensitivity: float = Form(0.5),
    aspect_ratios: str = Form(",".join(DEFAULT_ASPECT_RATIOS)),  # comma-separated: "16:9,9:16,1:1"
    caption_style: str | None = Form(None),  # falls back to workspace default
    add_emoji: bool = Form(True),
    censor: bool = Form(False),
):
    if max_clips > ABSOLUTE_MAX_CLIPS:
        raise HTTPException(400, f"max_clips cannot exceed {ABSOLUTE_MAX_CLIPS}.")
    if not (0.0 <= sensitivity <= 1.0):
        raise HTTPException(400, "sensitivity must be between 0.0 and 1.0.")
    ratio_list = [r.strip() for r in aspect_ratios.split(",") if r.strip()]
    for r in ratio_list:
        if r not in ("16:9", "9:16", "1:1"):
            raise HTTPException(400, f"Unsupported aspect ratio '{r}'.")
    if caption_style and caption_style not in CAPTION_STYLES:
        raise HTTPException(400, f"caption_style must be one of {CAPTION_STYLES}.")

    ws_precheck = workspaces.get_or_create_workspace(workspace_id)
    if ws_precheck.get("plan", "free_trial") == "free_trial":
        from app.billing.plans import FREE_TRIAL_MAX_CLIPS
        max_clips = min(max_clips, FREE_TRIAL_MAX_CLIPS)

    try:
        ingest.validate_extension(file.filename)
    except ingest.IngestionError as e:
        raise HTTPException(400, str(e))

    source_video_id = new_id()
    job_id = new_id()

    # stream to a temp file first so we can validate size before committing
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        tmp_path = Path(tmp.name)
        size = 0
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            tmp.write(chunk)

    try:
        ingest.validate_size(size)
        info = ingest.probe(tmp_path)
    except ingest.IngestionError as e:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(400, str(e))

    # Spec 3.8 / 8: plan limits + usage metering
    ws = workspaces.get_or_create_workspace(workspace_id)
    plan_id = ws.get("plan", "free_trial")
    prior_jobs = [j for j in store.list_jobs() if j.get("source_video", {}).get("workspace_id") == workspace_id]
    try:
        billing_usage.enforce_plan_limit(workspace_id, plan_id, info["duration"] / 60.0, video_count_this_trial=len(prior_jobs))
    except billing_usage.PlanLimitExceeded as e:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(402, str(e))

    dest_path = ingest.save_upload(tmp_path, file.filename, source_video_id)
    billing_usage.record_usage(workspace_id, info["duration"] / 60.0)

    source_video = SourceVideo(
        id=source_video_id, workspace_id=workspace_id, filename=file.filename,
        path=str(dest_path), upload_type="file", duration=info["duration"],
        status=JobStatus.QUEUED,
    )

    store.create_job(job_id, {
        "job_id": job_id,
        "source_video": source_video.to_dict(),
        "status": JobStatus.QUEUED.value,
        "stage_detail": "Queued...",
        "clips": [],
    })

    submit(
        job_id, source_video_id, str(dest_path),
        min_clips, max_clips, min_clip_seconds, max_clip_seconds, sensitivity,
        workspace_id=workspace_id, aspect_ratios=ratio_list,
        caption_style=caption_style, add_emoji=add_emoji, censor=censor,
    )

    return {"job_id": job_id, "source_video_id": source_video_id, "status": "queued"}


@app.get("/jobs")
def list_jobs():
    # Defensive .get()s: one malformed/partial job record used to raise
    # KeyError here (bracket access on "job_id"/"status") and take down the
    # WHOLE dashboard list for every job, not just the bad one. A job file
    # can legitimately be incomplete for a moment (e.g. a worker crashing
    # between file-create and the first status write), so this endpoint
    # skips anything unusable instead of 500ing the entire Dashboard.
    jobs = store.list_jobs()
    out = []
    for j in jobs:
        job_id = j.get("job_id")
        if not job_id:
            continue
        out.append({
            "job_id": job_id,
            "status": j.get("status", "unknown"),
            "stage_detail": j.get("stage_detail"),
            "filename": j.get("source_video", {}).get("filename"),
            "clip_count": len(j.get("clips", [])),
            "warning_count": len(j.get("warnings", [])),
        })
    return out


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = store.read_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return job


@app.get("/jobs/{job_id}/clips")
def get_job_clips(job_id: str):
    job = store.read_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return job.get("clips", [])


@app.patch("/jobs/{job_id}/clips/{clip_id}/status")
def set_clip_status(job_id: str, clip_id: str, status: str = Form(...)):
    """Clip Review Grid 'Finalize' action (spec 4.6 / 5.4): mark which
    clips the user is keeping."""
    from app.models import ClipStatus
    if status not in [s.value for s in ClipStatus]:
        raise HTTPException(400, f"status must be one of {[s.value for s in ClipStatus]}.")
    job = store.read_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    clips = job.get("clips", [])
    for c in clips:
        if c["id"] == clip_id:
            c["status"] = status
            store.update_job(job_id, clips=clips)
            return c
    raise HTTPException(404, "Clip not found.")


@app.post("/jobs/{job_id}/clips/{clip_id}/recut")
def recut_clip(job_id: str, clip_id: str, start: float = Form(...), end: float = Form(...),
                caption_style: str | None = Form(None), logo: bool = Form(True)):
    """Clip Editor detail view (spec 5.5): drag-trim in/out points and
    re-render. Runs synchronously since a single short clip re-cut is
    fast (seconds), unlike the full pipeline."""
    from app.pipeline import cut as cutting, reframe as reframing, captions as captioning
    from app.pipeline.score import CandidateClip
    from app import store as _store

    job = store.read_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    clips = job.get("clips", [])
    clip = next((c for c in clips if c["id"] == clip_id), None)
    if not clip:
        raise HTTPException(404, "Clip not found.")
    if end <= start:
        raise HTTPException(400, "end must be after start.")

    source_path = job.get("source_video", {}).get("path")
    if not source_path or not Path(source_path).exists():
        raise HTTPException(400, "Source video is no longer available for re-cutting.")

    transcript_id = job.get("transcript_id")
    words = []
    if transcript_id:
        tpath = TRANSCRIPTS_DIR / f"{transcript_id}.json"
        if tpath.exists():
            import json as _json
            from app.models import Word
            tdata = _json.loads(tpath.read_text())
            for seg in tdata.get("segments", []):
                for w in seg.get("words", []):
                    words.append(Word(word=w["word"], start=w["start"], end=w["end"]))

    candidate = CandidateClip(start=start, end=end, score=clip["score"], text="", reasons=clip["reason"].split(", ") if clip.get("reason") else [])
    ws = workspaces.get_or_create_workspace(job.get("source_video", {}).get("workspace_id", "default"))
    style = caption_style or clip.get("caption_style") or ws.get("default_caption_style")
    logo_path = ws.get("logo_path") if logo else None

    base_path = cutting.cut_clip(source_path, clip_id, candidate)
    aspect_paths = {"16:9": str(base_path)}
    for ratio in [r for r in clip.get("aspect_ratios", ["16:9"]) if r != "16:9"]:
        try:
            reframed = reframing.reframe_clip(str(base_path), clip_id, ratio)
            aspect_paths[ratio] = str(reframed)
        except Exception:
            pass

    final_paths = {}
    for ratio, path in aspect_paths.items():
        suffix = ratio.replace(":", "x")
        try:
            out = captioning.burn_captions(path, clip_id, suffix, words, start, end, style_name=style, logo_path=logo_path)
            final_paths[ratio] = str(out)
        except Exception:
            final_paths[ratio] = path

    clip.update({
        "start": start, "end": end, "caption_style": style,
        "logo_applied": bool(logo_path), "path": final_paths.get("16:9"),
        "aspect_paths": final_paths,
    })
    _store.update_job(job_id, clips=clips)
    return clip


@app.get("/clips/{job_id}/{clip_id}/download")
def download_clip(job_id: str, clip_id: str, aspect: str = "16:9"):
    job = store.read_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    clip = next((c for c in job.get("clips", []) if c["id"] == clip_id), None)
    if not clip:
        raise HTTPException(404, "Clip not found.")
    path = (clip.get("aspect_paths") or {}).get(aspect) or clip.get("path")
    if not path:
        raise HTTPException(404, f"No rendered file for aspect '{aspect}' on this clip.")
    return FileResponse(path, filename=Path(path).name)


@app.get("/clips/{job_id}/{clip_id}/thumbnail")
def download_thumbnail(job_id: str, clip_id: str):
    job = store.read_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    clip = next((c for c in job.get("clips", []) if c["id"] == clip_id), None)
    if not clip or not clip.get("thumbnail_path"):
        raise HTTPException(404, "Thumbnail not found.")
    return FileResponse(clip["thumbnail_path"], filename=Path(clip["thumbnail_path"]).name)


# --- Workspace / Brand settings (spec 3.6 / screen 9) --------------------

@app.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: str):
    return workspaces.get_or_create_workspace(workspace_id)


@app.put("/workspaces/{workspace_id}")
def update_workspace_settings(workspace_id: str, name: str | None = Form(None),
                               default_caption_style: str | None = Form(None)):
    fields = {}
    if name is not None:
        fields["name"] = name
    if default_caption_style is not None:
        if default_caption_style not in CAPTION_STYLES:
            raise HTTPException(400, f"default_caption_style must be one of {CAPTION_STYLES}.")
        fields["default_caption_style"] = default_caption_style
    return workspaces.update_workspace(workspace_id, **fields)


@app.post("/workspaces/{workspace_id}/logo")
async def upload_logo(workspace_id: str, file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower() or ".png"
    dest = LOGOS_DIR / f"{workspace_id}{ext}"
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
    workspaces.update_workspace(workspace_id, logo_path=str(dest))
    return {"logo_path": str(dest)}


@app.get("/jobs/{job_id}/download")
def download_all(job_id: str):
    job = store.read_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    clips = job.get("clips", [])
    if not clips:
        raise HTTPException(404, "No clips available for this job yet.")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for clip in clips:
            paths = list((clip.get("aspect_paths") or {}).values()) or [clip.get("path")]
            for raw in paths:
                if not raw:
                    continue
                p = Path(raw)
                if p.exists():
                    zf.write(p, arcname=p.name)
            if clip.get("thumbnail_path"):
                tp = Path(clip["thumbnail_path"])
                if tp.exists():
                    zf.write(tp, arcname=tp.name)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=clip_factory_{job_id}.zip"},
    )


# --- Publishing integrations (spec 3.5/3.6/6) -----------------------------

_oauth_state_workspace: dict[str, str] = {}  # state -> workspace_id, in-memory (short-lived)


@app.get("/workspaces/{workspace_id}/connect/{platform}/authorize")
def oauth_authorize(workspace_id: str, platform: str):
    try:
        client = get_client(platform)
    except ValueError as e:
        raise HTTPException(404, str(e))
    state = uuid.uuid4().hex
    _oauth_state_workspace[state] = workspace_id
    try:
        url = client.authorize_url(workspace_id, state)
    except NotConfiguredError as e:
        raise HTTPException(400, str(e))
    return RedirectResponse(url)


@app.get("/oauth/{platform}/callback")
def oauth_callback(platform: str, code: str, state: str):
    workspace_id = _oauth_state_workspace.pop(state, None)
    if not workspace_id:
        raise HTTPException(400, "Unknown or expired OAuth state.")
    try:
        client = get_client(platform)
        token_data = client.exchange_code(code)
    except (ValueError, PublishError) as e:
        raise HTTPException(400, str(e))
    workspaces.connect_account(workspace_id, platform, token_data)
    return {"connected": platform, "workspace_id": workspace_id}


@app.post("/clips/{job_id}/{clip_id}/publish")
def publish_clip(job_id: str, clip_id: str, platform: str = Form(...),
                  workspace_id: str = Form("default"), aspect: str = Form("9:16"),
                  title: str | None = Form(None), scheduled_time: str | None = Form(None),
                  user_id: str = Form("owner")):
    """Publish now (omit scheduled_time) or schedule for later (spec 3.5:
    'schedule/publish directly to connected platforms' + Content Calendar
    'drip' release). Requires 'publish' permission (spec 3.6: editors can
    generate/edit but not publish)."""
    try:
        workspaces.require_permission(workspace_id, user_id, "publish")
    except workspaces.PermissionDenied as e:
        raise HTTPException(403, str(e))

    plan_id = workspaces.get_or_create_workspace(workspace_id).get("plan", "free_trial")
    if not get_plan(plan_id).direct_publishing:
        raise HTTPException(402, f"Direct publishing requires the Pro plan or higher (current plan: {plan_id}).")

    job = store.read_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    clip = next((c for c in job.get("clips", []) if c["id"] == clip_id), None)
    if not clip:
        raise HTTPException(404, "Clip not found.")

    account = workspaces.get_account(workspace_id, platform)
    if not account:
        raise HTTPException(400, f"{platform} isn't connected for this workspace yet.")

    from datetime import datetime, timezone
    post = scheduler.create_post({
        "clip_id": clip_id,
        "workspace_id": workspace_id,
        "platform": platform,
        "scheduled_time": scheduled_time or datetime.now(timezone.utc).isoformat(),
        "status": PostStatus.SCHEDULED.value,
        "title": title or (clip.get("title_suggestions") or [""])[0],
        "hashtags": clip.get("hashtags", []),
        "aspect": aspect,
    })
    return post


@app.get("/workspaces/{workspace_id}/calendar")
def get_calendar(workspace_id: str):
    """Content Calendar screen (spec 5.7): scheduled + published posts."""
    return scheduler.list_posts(workspace_id)


@app.delete("/scheduled-posts/{post_id}")
def cancel_scheduled_post(post_id: str):
    post = scheduler.get_post(post_id)
    if not post:
        raise HTTPException(404, "Scheduled post not found.")
    if post.get("status") == PostStatus.PUBLISHED.value:
        raise HTTPException(400, "Can't cancel a post that's already published.")
    scheduler.delete_post(post_id)
    return {"cancelled": post_id}


def _resolve_clip_path(clip_id: str) -> str | None:
    for job in store.list_jobs():
        for clip in job.get("clips", []):
            if clip["id"] == clip_id:
                aspect = None
                for post in scheduler.list_posts():
                    if post["clip_id"] == clip_id:
                        aspect = post.get("aspect")
                paths = clip.get("aspect_paths") or {}
                return paths.get(aspect) or paths.get("9:16") or clip.get("path")
    return None


def _resolve_account(workspace_id: str, platform: str):
    return workspaces.get_account(workspace_id, platform)


@app.on_event("startup")
def _start_scheduler():
    scheduler.start_background_loop(_resolve_clip_path, _resolve_account)


# --- Analytics loop (spec 3.7) --------------------------------------------

@app.get("/workspaces/{workspace_id}/analytics")
def get_analytics(workspace_id: str):
    return analytics.dashboard(workspace_id)


@app.post("/workspaces/{workspace_id}/analytics/refresh")
def refresh_analytics(workspace_id: str):
    """Pulls fresh metrics from connected platforms for published posts,
    recomputes personalized scoring weights, returns the updated dashboard."""
    return analytics.refresh(workspace_id)


# --- Multi-workspace / team seats (spec 3.6) ------------------------------

@app.get("/workspaces")
def list_all_workspaces():
    return workspaces.list_workspaces()


@app.post("/workspaces/{workspace_id}/team")
def add_team_member(workspace_id: str, user_id: str = Form(...), role: str = Form(...)):
    try:
        return workspaces.add_team_member(workspace_id, user_id, role)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/workspaces/{workspace_id}/team/{user_id}")
def remove_team_member(workspace_id: str, user_id: str):
    return workspaces.remove_team_member(workspace_id, user_id)


@app.get("/workspaces/{workspace_id}/usage-report")
def usage_report(workspace_id: str):
    """Per-client usage reporting (spec 3.6): clips generated, published,
    and engagement pulled from connected platforms."""
    jobs = [j for j in store.list_jobs() if j.get("source_video", {}).get("workspace_id") == workspace_id]
    clips_generated = sum(len(j.get("clips", [])) for j in jobs)
    posts = scheduler.list_posts(workspace_id)
    published = [p for p in posts if p.get("status") == "published"]
    total_engagement = sum(analytics._primary_metric_value(p.get("published_metrics") or {}) for p in published)
    return {
        "workspace_id": workspace_id,
        "videos_processed": len(jobs),
        "clips_generated": clips_generated,
        "clips_published": len(published),
        "total_engagement": total_engagement,
        "current_usage": billing_usage.get_usage(workspace_id).to_dict(),
        "plan": workspaces.get_or_create_workspace(workspace_id).get("plan", "free_trial"),
    }


# --- Billing (spec 3.8) ----------------------------------------------------

@app.get("/billing/plans")
def list_plans():
    return {pid: p.__dict__ for pid, p in PLANS.items()}


@app.post("/billing/checkout")
def create_checkout(workspace_id: str = Form(...), plan_id: str = Form(...), email: str | None = Form(None)):
    try:
        get_plan(plan_id)
        url = stripe_client.create_checkout_session(workspace_id, plan_id, customer_email=email)
    except (ValueError, stripe_client.BillingNotConfigured) as e:
        raise HTTPException(400, str(e))
    return {"checkout_url": url}


@app.post("/billing/portal")
def billing_portal(workspace_id: str = Form(...)):
    ws = workspaces.get_or_create_workspace(workspace_id)
    customer_id = ws.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(400, "This workspace has no Stripe customer yet — subscribe first via /billing/checkout.")
    try:
        url = stripe_client.create_billing_portal_session(customer_id)
    except stripe_client.BillingNotConfigured as e:
        raise HTTPException(400, str(e))
    return {"portal_url": url}


@app.post("/billing/webhook")
async def billing_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()
    try:
        result = stripe_client.handle_webhook_event(payload, stripe_signature or "")
    except stripe_client.BillingNotConfigured as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001 — includes stripe.error.SignatureVerificationError
        raise HTTPException(400, f"Webhook verification failed: {e}")
    return result


# ── One thing to run: serve the built frontend from this same server ────────
# The React app is built with base "/ui/" (see frontend/vite.config.js) so its
# pages never collide with the API's own paths (both have /jobs/{id}). Root
# redirects there. Missing dist → the API still runs; only the UI is absent.
from fastapi.staticfiles import StaticFiles  # noqa: E402

_DIST = (BASE_DIR / "frontend" / "dist").resolve()


@app.get("/", include_in_schema=False)
async def _root():
    return RedirectResponse("/ui/")


if (_DIST / "index.html").is_file():
    if (_DIST / "assets").is_dir():
        app.mount("/ui/assets", StaticFiles(directory=_DIST / "assets"), name="ui-assets")

    @app.get("/ui", include_in_schema=False)
    @app.get("/ui/{full_path:path}", include_in_schema=False)
    async def _ui(full_path: str = ""):
        if full_path:
            candidate = (_DIST / full_path).resolve()
            if candidate.is_file() and str(candidate).startswith(str(_DIST) + "/"):
                return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
else:
    @app.get("/ui/{full_path:path}", include_in_schema=False)
    async def _ui_missing(full_path: str = ""):
        raise HTTPException(503, "The web app isn't built yet — run ./setup.sh first.")
