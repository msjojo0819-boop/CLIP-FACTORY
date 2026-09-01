"""
Moment scoring engine — spec section 3.2 (second half) + 3.3 (clip windowing).

Combines, per transcript segment:
  - audio energy (RMS spike relative to the video's own baseline) — proxy
    for laughter / raised volume / excitement
  - keyword/topic heuristics — hot-take phrasing, punchlines, advice,
    story structure cues
  - a lightweight lexicon-based sentiment/emotion score
  - silence is implicitly excluded because faster-whisper's VAD filter
    already drops dead air from the segment list

Segments are then grouped into candidate clip windows sized 15s-3min
(user-configurable), with cut points snapped to segment boundaries (i.e.
speech pauses) rather than mid-sentence, and ranked by aggregate score.
User "sensitivity" controls how many windows survive the cut.

This is a genuine, runnable heuristic engine — not a stub — but it is not
a trained ML model. Swapping in a real sentiment/emotion classifier or an
LLM-based "hot take" detector later is a drop-in replacement for
`_keyword_score` / `_lexicon_sentiment` without touching the windowing
logic below.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.config import DEFAULT_MIN_CLIP_SECONDS, DEFAULT_MAX_CLIP_SECONDS
from app.models import TranscriptSegment

# --- keyword heuristics -----------------------------------------------

HOT_TAKE_PATTERNS = [
    r"\bi think\b", r"\bhonestly\b", r"\bnobody talks about\b",
    r"\bunpopular opinion\b", r"\bthe truth is\b", r"\bhot take\b",
    r"\bcontroversial\b", r"\beveryone is wrong\b",
]
PUNCHLINE_MARKERS = [r"\bha+h+a+\b", r"\blol\b", r"\bliterally\b", r"\bno way\b", r"\bwait what\b"]
ADVICE_MARKERS = [r"\byou should\b", r"\bhere's how\b", r"\bthe key is\b", r"\bstep one\b", r"\bif you want to\b"]
STORY_MARKERS = [r"\bso one time\b", r"\bthis one time\b", r"\bi remember when\b", r"\bstory time\b", r"\bit started when\b"]

POSITIVE_WORDS = {
    "amazing", "incredible", "insane", "crazy", "love", "best", "awesome",
    "wow", "unbelievable", "epic", "hilarious", "genius", "wild",
}
NEGATIVE_WORDS = {
    "terrible", "worst", "hate", "awful", "disaster", "furious", "angry",
    "scared", "worried", "nightmare",
}


def _keyword_score(text: str) -> float:
    t = text.lower()
    score = 0.0
    for pat in HOT_TAKE_PATTERNS:
        if re.search(pat, t):
            score += 2.0
    for pat in PUNCHLINE_MARKERS:
        if re.search(pat, t):
            score += 1.5
    for pat in ADVICE_MARKERS:
        if re.search(pat, t):
            score += 1.2
    for pat in STORY_MARKERS:
        if re.search(pat, t):
            score += 1.5
    if text.strip().endswith("!") or text.count("!") > 0:
        score += 0.5 * text.count("!")
    if text.strip().endswith("?"):
        score += 0.3
    return score


def _lexicon_sentiment(text: str) -> float:
    words = re.findall(r"[a-z']+", text.lower())
    if not words:
        return 0.0
    pos = sum(1 for w in words if w in POSITIVE_WORDS)
    neg = sum(1 for w in words if w in NEGATIVE_WORDS)
    return (pos - neg) / max(len(words), 1) * 10.0


# --- audio energy -------------------------------------------------------

def _extract_rms_curve(source_video_path: str) -> tuple[np.ndarray, float]:
    """Extract a coarse RMS energy curve (one value per ~0.5s window) from
    the source audio via ffmpeg -> raw PCM -> numpy, using librosa for the
    RMS computation. Returns (rms_array, hop_seconds)."""
    import librosa

    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "audio.wav"
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(source_video_path),
                "-vn", "-ac", "1", "-ar", "16000", str(wav_path),
            ],
            capture_output=True, timeout=600,
        )
        if not wav_path.exists():
            return np.array([]), 0.5

        y, sr = librosa.load(str(wav_path), sr=16000, mono=True)
        hop_length = int(sr * 0.5)  # 0.5s windows
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        return rms, 0.5


def _energy_score_for_range(rms: np.ndarray, hop_seconds: float, start: float, end: float, baseline: float) -> float:
    if rms.size == 0 or baseline <= 0:
        return 0.0
    i0 = max(0, int(start / hop_seconds))
    i1 = min(rms.size, int(end / hop_seconds) + 1)
    if i0 >= i1:
        return 0.0
    window = rms[i0:i1]
    peak = float(np.max(window))
    return max(0.0, (peak - baseline) / baseline) * 3.0  # scaled contribution


@dataclass
class ScoredSegment:
    segment_index: int
    start: float
    end: float
    text: str
    score: float
    reasons: list[str]


DEFAULT_SCORING_WEIGHTS = {
    "keyword/topic cue": 1.0,
    "emotional language": 1.0,
    "audio energy spike": 1.0,
}


def score_segments(
    segments: list[TranscriptSegment],
    source_video_path: str,
    weights: dict[str, float] | None = None,
) -> list[ScoredSegment]:
    """`weights` lets analytics.py's personalization loop (spec 3.7) bias
    which signal matters most for a given workspace, based on what has
    actually performed well for that creator historically. Defaults to
    1.0 for every signal (no personalization yet / not enough data)."""
    w = {**DEFAULT_SCORING_WEIGHTS, **(weights or {})}
    rms, hop = _extract_rms_curve(source_video_path)
    baseline = float(np.median(rms)) if rms.size else 0.0

    scored = []
    for i, seg in enumerate(segments):
        reasons = []
        kw = _keyword_score(seg.text)
        if kw > 0:
            reasons.append("keyword/topic cue")
        sent = _lexicon_sentiment(seg.text)
        if abs(sent) > 0.5:
            reasons.append("emotional language")
        energy = _energy_score_for_range(rms, hop, seg.start, seg.end, baseline)
        if energy > 0.5:
            reasons.append("audio energy spike")

        total = (
            kw * w["keyword/topic cue"]
            + abs(sent) * w["emotional language"]
            + energy * w["audio energy spike"]
        )
        scored.append(ScoredSegment(
            segment_index=i, start=seg.start, end=seg.end, text=seg.text,
            score=round(total, 3), reasons=reasons,
        ))
    return scored


# --- windowing into candidate clips -------------------------------------

@dataclass
class CandidateClip:
    start: float
    end: float
    score: float
    text: str
    reasons: list[str]


def build_candidate_clips(
    scored_segments: list[ScoredSegment],
    min_clip_seconds: int = DEFAULT_MIN_CLIP_SECONDS,
    max_clip_seconds: int = DEFAULT_MAX_CLIP_SECONDS,
    max_candidates: int = 30,
    sensitivity: float = 0.5,
) -> list[CandidateClip]:
    """Greedily grow a window outward from each local score peak until it
    hits min/max clip length, snapping start/end to segment boundaries
    (never mid-sentence). `sensitivity` in [0,1]: higher = more, shorter
    clips pass the threshold; lower = fewer, higher-scoring clips only.
    """
    if not scored_segments:
        return []

    # threshold scales inversely with sensitivity: sensitivity=1 -> low bar
    scores = [s.score for s in scored_segments]
    if not scores:
        return []
    score_p50 = float(np.percentile(scores, 50))
    score_p90 = float(np.percentile(scores, 90))
    threshold = score_p90 - sensitivity * (score_p90 - score_p50)

    peak_indices = [i for i, s in enumerate(scored_segments) if s.score >= threshold and s.score > 0]

    candidates: list[CandidateClip] = []
    used_ranges: list[tuple[float, float]] = []

    for peak_i in sorted(peak_indices, key=lambda i: -scored_segments[i].score):
        peak = scored_segments[peak_i]
        if peak.end - peak.start > max_clip_seconds:
            continue

        lo, hi = peak_i, peak_i
        cur_start, cur_end = peak.start, peak.end
        cur_score = peak.score
        texts = [peak.text]
        reasons = set(peak.reasons)

        while (cur_end - cur_start) < min_clip_seconds and (lo > 0 or hi < len(scored_segments) - 1):
            grow_left = lo > 0
            grow_right = hi < len(scored_segments) - 1
            if grow_right and (not grow_left or scored_segments[hi + 1].score >= (scored_segments[lo - 1].score if grow_left else -1)):
                hi += 1
                if cur_end - cur_start + (scored_segments[hi].end - scored_segments[hi].start) > max_clip_seconds:
                    hi -= 1
                    break
                cur_end = scored_segments[hi].end
                cur_score += scored_segments[hi].score
                texts.append(scored_segments[hi].text)
                reasons.update(scored_segments[hi].reasons)
            elif grow_left:
                lo -= 1
                if cur_end - cur_start + (scored_segments[lo].end - scored_segments[lo].start) > max_clip_seconds:
                    lo += 1
                    break
                cur_start = scored_segments[lo].start
                cur_score += scored_segments[lo].score
                texts.insert(0, scored_segments[lo].text)
                reasons.update(scored_segments[lo].reasons)
            else:
                break

        if (cur_end - cur_start) < min_clip_seconds * 0.6:
            continue  # too short even after growing; skip

        # skip if this overlaps a already-selected higher-scored window
        if any(not (cur_end <= u0 or cur_start >= u1) for (u0, u1) in used_ranges):
            continue

        used_ranges.append((cur_start, cur_end))
        candidates.append(CandidateClip(
            start=round(cur_start, 2), end=round(cur_end, 2),
            score=round(cur_score, 3), text=" ".join(texts),
            reasons=sorted(reasons),
        ))

    candidates.sort(key=lambda c: -c.score)
    return candidates[:max_candidates]
