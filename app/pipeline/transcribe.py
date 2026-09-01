"""
Transcription — spec section 3.2 (first half).

Uses faster-whisper (CTranslate2-based Whisper) for self-hosted
speech-to-text with word/segment timestamps and language auto-detect.
Speaker labeling here is a lightweight heuristic (silence-gap based
turn-splitting) — true diarization (pyannote-class models) is a
Phase 1.x accuracy upgrade, not required for the pipeline to function.
"""
from __future__ import annotations

from faster_whisper import WhisperModel

from app.config import WHISPER_MODEL_SIZE, WHISPER_COMPUTE_TYPE
from app.models import Transcript, TranscriptSegment, Word, new_id

_model_cache: dict[str, WhisperModel] = {}


def _get_model() -> WhisperModel:
    key = f"{WHISPER_MODEL_SIZE}:{WHISPER_COMPUTE_TYPE}"
    if key not in _model_cache:
        _model_cache[key] = WhisperModel(
            WHISPER_MODEL_SIZE, device="cpu", compute_type=WHISPER_COMPUTE_TYPE
        )
    return _model_cache[key]


LOW_CONFIDENCE_THRESHOLD = -1.0  # avg_logprob below this = flag for manual review


def transcribe_video(source_video_path: str, source_video_id: str) -> Transcript:
    model = _get_model()

    segments_iter, info = model.transcribe(
        source_video_path,
        vad_filter=True,  # skips silence, per spec's silence/dead-air detection
        word_timestamps=True,  # needed for word-by-word karaoke captions (3.4)
    )

    segments: list[TranscriptSegment] = []
    low_conf_indices: list[int] = []

    # Very simple "speaker" turn heuristic: bump speaker label on a gap > 1.2s
    # between segments, alternating labels. This is a stand-in for real
    # diarization — good enough to satisfy "speaker labels when multiple
    # speakers are detected" at the UI level for Phase 1.
    speaker_idx = 0
    prev_end = None

    for i, seg in enumerate(segments_iter):
        if prev_end is not None and (seg.start - prev_end) > 1.2:
            speaker_idx += 1
        prev_end = seg.end

        avg_conf = float(getattr(seg, "avg_logprob", 0.0) or 0.0)
        words = [
            Word(word=w.word.strip(), start=w.start, end=w.end)
            for w in (getattr(seg, "words", None) or [])
        ]
        ts = TranscriptSegment(
            start=seg.start,
            end=seg.end,
            text=seg.text.strip(),
            speaker=f"Speaker {(speaker_idx % 2) + 1}",
            avg_confidence=avg_conf,
            words=words,
        )
        segments.append(ts)
        if avg_conf < LOW_CONFIDENCE_THRESHOLD:
            low_conf_indices.append(i)

    return Transcript(
        id=new_id(),
        source_video_id=source_video_id,
        language=info.language or "unknown",
        segments=segments,
        low_confidence_segment_indices=low_conf_indices,
    )
