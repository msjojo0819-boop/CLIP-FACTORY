"""
Clip Factory — configuration.

Phase 1 scope (per build roadmap): upload -> transcribe -> moment scoring ->
basic 16:9 clip cutting. No captions, no reframe, no publishing yet — those
are Phase 2+.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "app" / "storage"
SOURCES_DIR = STORAGE_DIR / "sources"
CLIPS_DIR = STORAGE_DIR / "clips"
TRANSCRIPTS_DIR = STORAGE_DIR / "transcripts"
JOBS_DIR = STORAGE_DIR / "jobs"

for d in (SOURCES_DIR, CLIPS_DIR, TRANSCRIPTS_DIR, JOBS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Spec 3.1: MP4, MOV, MKV up to 4 hours / 20GB
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024 * 1024  # 20GB
MAX_DURATION_SECONDS = 4 * 60 * 60  # 4 hours

# Spec 3.3: 5-30 candidate clips per video, each 15s-3min (user-configurable)
DEFAULT_MIN_CLIPS = 5
DEFAULT_MAX_CLIPS = 15
ABSOLUTE_MAX_CLIPS = 30
DEFAULT_MIN_CLIP_SECONDS = 15
DEFAULT_MAX_CLIP_SECONDS = 180

# Whisper model size. "base" is a good CPU-friendly default; can be
# overridden via env var for better accuracy on GPU boxes.
WHISPER_MODEL_SIZE = os.environ.get("CLIP_FACTORY_WHISPER_MODEL", "base")
WHISPER_COMPUTE_TYPE = os.environ.get("CLIP_FACTORY_WHISPER_COMPUTE", "int8")

# Spec 3.4: caption style presets
CAPTION_STYLES = ["bold_pop", "minimal_clean", "neon_gaming", "podcast_classic"]
DEFAULT_CAPTION_STYLE = "bold_pop"

# Spec 3.3: which aspect ratios to render per clip by default
DEFAULT_ASPECT_RATIOS = ["16:9", "9:16", "1:1"]

WORKSPACES_DIR = STORAGE_DIR / "workspaces"
LOGOS_DIR = STORAGE_DIR / "logos"
for d in (WORKSPACES_DIR, LOGOS_DIR):
    d.mkdir(parents=True, exist_ok=True)
