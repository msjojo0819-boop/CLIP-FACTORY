"""
Pipeline orchestrator — wires ingest -> transcribe -> score -> cut ->
reframe -> caption -> censor -> thumbnail/metadata, and reports live
status matching the spec's "Transcribing... Finding moments... Cutting
clips..." progress UI (section 4, step 3) and the resume-from-last-stage
requirement (section 9).

Phase 2 additions over Phase 1: every clip is rendered in all requested
aspect ratios (16:9 always available from the raw cut; 9:16/1:1 via
speaker-tracking reframe), captions are burned in using the workspace's
default style (or an override), a logo watermark is applied if the
workspace has one configured, profanity censoring is applied if
requested, and a thumbnail frame is picked.
"""
from __future__ import annotations

import json
import traceback
from pathlib import Path

from app.config import TRANSCRIPTS_DIR, DEFAULT_CAPTION_STYLE, DEFAULT_ASPECT_RATIOS
from app.models import JobStatus, Clip, ClipStatus, Word, new_id
from app.pipeline import ingest, score as scoring, cut as cutting, reframe as reframing
from app.pipeline import captions as captioning, censor as censoring, thumbnail as thumbnailing
from app.pipeline.metadata import suggest_titles, suggest_hashtags
from app.pipeline.transcribe import transcribe_video
from app import store, workspaces, analytics


def _save_transcript(transcript) -> Path:
    path = TRANSCRIPTS_DIR / f"{transcript.id}.json"
    path.write_text(json.dumps(transcript.to_dict(), indent=2, default=str))
    return path


def _flatten_words(segments) -> list[Word]:
    out = []
    for seg in segments:
        out.extend(seg.words if seg.words else [])
    return out


def run_pipeline(job_id: str, source_video_id: str, source_path: str,
                  min_clips: int, max_clips: int,
                  min_clip_seconds: int, max_clip_seconds: int,
                  sensitivity: float, workspace_id: str = "default",
                  aspect_ratios: list[str] | None = None,
                  caption_style: str | None = None,
                  add_emoji: bool = True,
                  censor: bool = False) -> None:
    aspect_ratios = aspect_ratios or DEFAULT_ASPECT_RATIOS
    ws = workspaces.get_or_create_workspace(workspace_id)
    caption_style = caption_style or ws.get("default_caption_style") or DEFAULT_CAPTION_STYLE
    logo_path = ws.get("logo_path")

    try:
        store.update_job(job_id, status=JobStatus.TRANSCRIBING.value, stage_detail="Transcribing...")
        transcript = transcribe_video(source_path, source_video_id)
        _save_transcript(transcript)
        all_words = _flatten_words(transcript.segments)
        store.update_job(
            job_id, transcript_id=transcript.id,
            segment_count=len(transcript.segments),
            low_confidence_count=len(transcript.low_confidence_segment_indices),
        )

        store.update_job(job_id, status=JobStatus.SCORING.value, stage_detail="Finding moments...")
        weights = analytics.get_scoring_weights(workspace_id)
        scored = scoring.score_segments(transcript.segments, source_path, weights=weights)
        candidates = scoring.build_candidate_clips(
            scored,
            min_clip_seconds=min_clip_seconds,
            max_clip_seconds=max_clip_seconds,
            max_candidates=max_clips,
            sensitivity=sensitivity,
        )

        store.update_job(job_id, status=JobStatus.CUTTING.value, stage_detail="Cutting clips...", candidate_count=len(candidates))

        clips: list[dict] = []
        # Stage failures inside the loop below used to only touch the transient
        # `stage_detail` field, which the next store.update_job() call overwrites
        # within seconds — so a broken stage (e.g. reframe) would silently
        # produce fewer aspect ratios than requested with zero trace of why.
        # job_warnings accumulates every non-fatal failure for this run and is
        # persisted on the final job record (and per-clip, on each Clip) so it
        # survives and shows up in the review UI instead of vanishing.
        job_warnings: list[str] = []
        for idx, c in enumerate(candidates):
            clip_id = new_id()
            clip_warnings: list[str] = []
            stage_note = f"Rendering clip {idx + 1}/{len(candidates)}..."
            store.update_job(job_id, stage_detail=stage_note, warnings=job_warnings)
            try:
                base_path = cutting.cut_clip(source_path, clip_id, c)  # 16:9 base
            except cutting.CutError as e:
                msg = f"Clip {idx + 1}/{len(candidates)}: failed to cut ({e}) — skipped entirely"
                job_warnings.append(msg)
                store.update_job(job_id, stage_detail=f"Warning: {msg}", warnings=job_warnings)
                continue

            aspect_paths = {"16:9": str(base_path)}

            # Phase 2: reframe to any additional requested aspect ratios
            for ratio in aspect_ratios:
                if ratio == "16:9":
                    continue
                try:
                    reframed_path = reframing.reframe_clip(str(base_path), clip_id, ratio)
                    aspect_paths[ratio] = str(reframed_path)
                except Exception as e:  # noqa: BLE001
                    msg = f"Clip {clip_id}: reframe to {ratio} failed ({e}) — that aspect ratio was skipped"
                    clip_warnings.append(msg)
                    job_warnings.append(msg)
                    store.update_job(job_id, stage_detail=f"Warning: {msg}", warnings=job_warnings)

            # Phase 2: burn captions into every rendered aspect ratio
            captioned_paths = {}
            for ratio, path in aspect_paths.items():
                suffix = ratio.replace(":", "x")
                try:
                    out = captioning.burn_captions(
                        path, clip_id, suffix, all_words, c.start, c.end,
                        style_name=caption_style, add_emoji=add_emoji,
                        censor_captions=censor, logo_path=logo_path,
                    )
                    captioned_paths[ratio] = str(out)
                except Exception as e:  # noqa: BLE001
                    msg = f"Clip {clip_id}: caption burn failed for {ratio} ({e}) — shipped without captions"
                    clip_warnings.append(msg)
                    job_warnings.append(msg)
                    store.update_job(job_id, stage_detail=f"Warning: {msg}", warnings=job_warnings)
                    captioned_paths[ratio] = path  # fall back to uncaptioned

            # Phase 2: audio bleep censor on top of the (already caption-blurred) clips
            final_paths = {}
            if censor:
                hits = censoring.find_profanity_hits(all_words, c.start, c.end)
                for ratio, path in captioned_paths.items():
                    suffix = ratio.replace(":", "x")
                    try:
                        out = censoring.bleep_audio(path, clip_id, suffix, hits)
                        final_paths[ratio] = str(out)
                    except Exception as e:  # noqa: BLE001
                        msg = f"Clip {clip_id}: profanity censor failed for {ratio} ({e}) — shipped uncensored, review before publishing"
                        clip_warnings.append(msg)
                        job_warnings.append(msg)
                        store.update_job(job_id, stage_detail=f"Warning: {msg}", warnings=job_warnings)
                        final_paths[ratio] = path
            else:
                final_paths = captioned_paths

            thumb = None
            try:
                primary = final_paths.get("9:16") or final_paths.get("16:9")
                thumb_path = thumbnailing.pick_thumbnail_frame(primary, clip_id)
                thumb = str(thumb_path) if thumb_path else None
            except Exception as e:  # noqa: BLE001
                msg = f"Clip {clip_id}: thumbnail generation failed ({e}) — no preview image"
                clip_warnings.append(msg)
                job_warnings.append(msg)

            clip = Clip(
                id=clip_id,
                source_video_id=source_video_id,
                start=c.start,
                end=c.end,
                score=c.score,
                reason=", ".join(c.reasons) if c.reasons else "moment score",
                aspect_ratios=list(final_paths.keys()),
                caption_style=caption_style,
                logo_applied=bool(logo_path),
                status=ClipStatus.DRAFT,
                path=final_paths.get("16:9"),
                aspect_paths=final_paths,
                thumbnail_path=thumb,
                censored=censor,
                title_suggestions=suggest_titles(c.text),
                hashtags=suggest_hashtags(c.text, c.reasons),
                warnings=clip_warnings,
            )
            clips.append(clip.to_dict())

        store.update_job(
            job_id, status=JobStatus.DONE.value,
            stage_detail=("Done." if not job_warnings else f"Done, with {len(job_warnings)} warning(s) — review before publishing."),
            clips=clips,
            warnings=job_warnings,
        )

    except Exception as e:  # noqa: BLE001
        store.update_job(
            job_id, status=JobStatus.FAILED.value,
            stage_detail="Failed.",
            error=f"{e}",
            traceback=traceback.format_exc(),
        )
