"""
Ingestion — spec section 3.1.

Phase 1 covers direct file upload with validation (format, size) and
duration/stream probing so we can reject corrupted files with a clear
error instead of failing deep inside the pipeline. Link-paste ingestion
(YouTube/Twitch/Rumble) is stubbed with a clear NotImplemented error —
it needs a server-side downloader (yt-dlp) which is a Phase 1.x add-on,
not core pipeline logic.
"""
import json
import shutil
import subprocess
from pathlib import Path

from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, MAX_DURATION_SECONDS, SOURCES_DIR


class IngestionError(Exception):
    """Raised with a user-facing message per spec: 'reject corrupted files
    with clear error messaging'."""


def validate_extension(filename: str) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise IngestionError(
            f"Unsupported file type '{ext}'. Accepted formats: "
            f"{', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )


def validate_size(size_bytes: int) -> None:
    if size_bytes > MAX_UPLOAD_BYTES:
        raise IngestionError(
            f"File is too large ({size_bytes / (1024**3):.1f}GB). "
            f"Max upload size is {MAX_UPLOAD_BYTES / (1024**3):.0f}GB."
        )
    if size_bytes == 0:
        raise IngestionError("Uploaded file is empty.")


def probe(path: Path) -> dict:
    """Run ffprobe to pull duration + stream info. Raises IngestionError on
    anything ffprobe can't parse, which is our proxy for 'corrupted file'.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-print_format", "json",
                "-show_format", "-show_streams", str(path),
            ],
            capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError as e:
        raise IngestionError("ffprobe is not installed on the server.") from e
    except subprocess.TimeoutExpired as e:
        raise IngestionError("Timed out reading video metadata — file may be corrupted.") from e

    if result.returncode != 0 or not result.stdout.strip():
        raise IngestionError(
            "Could not read this video — it appears to be corrupted or is not "
            "a valid media file."
        )

    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise IngestionError("Could not parse video metadata (corrupted file).") from e

    streams = info.get("streams", [])
    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    if not has_audio:
        raise IngestionError(
            "No audio track detected. Clip Factory needs audio to transcribe "
            "and score moments."
        )

    duration = float(info.get("format", {}).get("duration", 0.0))
    if duration <= 0:
        raise IngestionError("Video has zero or unknown duration (corrupted file).")
    if duration > MAX_DURATION_SECONDS:
        raise IngestionError(
            f"Video is {duration/3600:.1f} hours long. Max supported length is "
            f"{MAX_DURATION_SECONDS/3600:.0f} hours."
        )

    return {
        "duration": duration,
        "has_video": has_video,
        "has_audio": has_audio,
        "audio_only": has_audio and not has_video,
    }


def save_upload(tmp_path: Path, filename: str, source_video_id: str) -> Path:
    """Move a validated upload into permanent storage."""
    ext = Path(filename).suffix.lower()
    dest = SOURCES_DIR / f"{source_video_id}{ext}"
    shutil.move(str(tmp_path), str(dest))
    return dest


def ingest_link(url: str) -> Path:
    """Phase 1.x: pull a YouTube/Twitch/Rumble VOD server-side (spec 3.1).
    Not part of the Phase-1 core pipeline build — raise clearly instead of
    silently no-op'ing.
    """
    raise NotImplementedError(
        "Link ingestion (YouTube/Twitch/Rumble) is a Phase 1.x add-on built on "
        "yt-dlp; not wired up yet. Use direct file upload for now."
    )
