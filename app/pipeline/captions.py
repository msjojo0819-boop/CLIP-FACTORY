"""
Captions — spec section 3.4.

Generates real .ass subtitle files with per-word karaoke highlighting
(the "word-by-word karaoke-style highlight" TikTok/Reels format) and
burns them into the video with ffmpeg's `subtitles` filter (libass).
Four style presets match the spec exactly: bold pop, minimal clean,
neon gaming, podcast-classic. Also handles optional auto-emoji insertion
and (when requested) blurring caption text for the profanity-censored
version.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.config import CLIPS_DIR
from app.models import Word

# --- style presets --------------------------------------------------
# ASS colors are &HAABBGGRR (alpha-blue-green-red, hex)

@dataclass
class CaptionStyle:
    name: str
    font: str
    font_size: int
    primary_color: str    # normal word color
    highlight_color: str  # active/spoken-word color
    outline_color: str
    back_color: str
    bold: bool
    outline: int
    shadow: int
    alignment: int = 2  # bottom-center
    margin_v: int = 90


STYLE_PRESETS: dict[str, CaptionStyle] = {
    "bold_pop": CaptionStyle(
        name="bold_pop", font="Arial Black", font_size=76,
        primary_color="&H00FFFFFF", highlight_color="&H0000D7FF",  # white -> gold
        outline_color="&H00000000", back_color="&H00000000",
        bold=True, outline=5, shadow=2,
    ),
    "minimal_clean": CaptionStyle(
        name="minimal_clean", font="Helvetica", font_size=58,
        primary_color="&H00FFFFFF", highlight_color="&H00CCCCCC",
        outline_color="&H00202020", back_color="&H00000000",
        bold=False, outline=2, shadow=0,
    ),
    "neon_gaming": CaptionStyle(
        name="neon_gaming", font="Impact", font_size=80,
        primary_color="&H00FF00FF", highlight_color="&H0000FFAA",  # magenta -> neon green
        outline_color="&H00330033", back_color="&H00000000",
        bold=True, outline=6, shadow=3,
    ),
    "podcast_classic": CaptionStyle(
        name="podcast_classic", font="Georgia", font_size=54,
        primary_color="&H00E6E6E6", highlight_color="&H0000A5FF",  # light gray -> amber
        outline_color="&H00101010", back_color="&H00000000",
        bold=False, outline=3, shadow=1,
    ),
}

DEFAULT_STYLE = "bold_pop"

EMOJI_KEYWORDS = {
    "money": "💰", "cash": "💰", "love": "❤️", "crazy": "🤯", "insane": "🤯",
    "fire": "🔥", "win": "🏆", "lose": "😭", "laugh": "😂", "funny": "😂",
    "shocked": "😱", "wow": "😱", "truth": "💯", "real": "💯", "idea": "💡",
    "warning": "⚠️", "danger": "⚠️", "secret": "🤫", "boom": "💥",
}

PROFANITY_WORDS = {
    "damn", "hell", "shit", "fuck", "fucking", "ass", "bitch", "bastard",
    "crap", "piss",
}


def _fmt_ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:01d}:{m:02d}:{s:05.2f}"


def _emoji_for_word(word: str) -> str | None:
    w = re.sub(r"[^a-zA-Z]", "", word).lower()
    return EMOJI_KEYWORDS.get(w)


def build_ass(
    words: list[Word],
    clip_start: float,
    clip_end: float,
    style_name: str = DEFAULT_STYLE,
    add_emoji: bool = True,
    censor: bool = False,
    play_res_x: int = 1080,
    play_res_y: int = 1920,
) -> str:
    """Builds an .ass file (as a string) with word-by-word karaoke
    highlighting, grouping words into short on-screen lines (~4-6 words)
    so text doesn't overflow a 9:16 frame.
    """
    style = STYLE_PRESETS.get(style_name, STYLE_PRESETS[DEFAULT_STYLE])

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font},{style.font_size},{style.primary_color},{style.highlight_color},{style.outline_color},{style.back_color},{-1 if style.bold else 0},0,0,0,100,100,0,0,1,{style.outline},{style.shadow},{style.alignment},40,40,{style.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # clip words to the clip window and rebase timestamps to clip-relative
    rel_words = [
        Word(word=w.word, start=max(0.0, w.start - clip_start), end=max(0.0, w.end - clip_start))
        for w in words
        if clip_start <= w.start < clip_end
    ]

    lines = []
    GROUP_SIZE = 5
    for i in range(0, len(rel_words), GROUP_SIZE):
        group = rel_words[i:i + GROUP_SIZE]
        if not group:
            continue
        line_start = group[0].start
        line_end = group[-1].end
        if line_end <= line_start:
            continue

        # one \k-karaoke event per word: highlight the active word while it's
        # being spoken, rest stay in primary color. We emit one dialogue
        # event per word-highlight-state for reliable rendering.
        for j, w in enumerate(group):
            seg_start = w.start
            seg_end = group[j + 1].start if j + 1 < len(group) else line_end
            if seg_end <= seg_start:
                seg_end = seg_start + 0.05

            parts = []
            for k, gw in enumerate(group):
                token = gw.word
                if censor and re.sub(r"[^a-zA-Z]", "", token).lower() in PROFANITY_WORDS:
                    token = "•" * max(3, len(token))
                emoji = _emoji_for_word(gw.word) if add_emoji else None
                if k == j:
                    parts.append(f"{{\\c{style.highlight_color}}}{token}{{\\c{style.primary_color}}}" + (f" {emoji}" if emoji else ""))
                else:
                    parts.append(token + (f" {emoji}" if emoji else ""))
            text = " ".join(parts)
            lines.append(
                f"Dialogue: 0,{_fmt_ts(seg_start)},{_fmt_ts(seg_end)},Default,,0,0,0,,{text}"
            )

    return header + "\n".join(lines) + "\n"


def burn_captions(
    source_clip_path: str,
    clip_id: str,
    aspect_suffix: str,  # "9x16" or "1x1" or "16x9"
    words: list[Word],
    clip_start: float,
    clip_end: float,
    style_name: str = DEFAULT_STYLE,
    add_emoji: bool = True,
    censor_captions: bool = False,
    logo_path: str | None = None,
) -> Path:
    """Burns karaoke captions (and optionally a logo overlay) into a clip.
    Writes a sibling .ass file next to the output for transparency/debugging.
    """
    import cv2
    cap = cv2.VideoCapture(str(source_clip_path))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1080
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1920
    cap.release()

    ass_content = build_ass(
        words, clip_start, clip_end, style_name=style_name,
        add_emoji=add_emoji, censor=censor_captions, play_res_x=w, play_res_y=h,
    )
    ass_path = CLIPS_DIR / f"{clip_id}_{aspect_suffix}.ass"
    ass_path.write_text(ass_content)

    out_path = CLIPS_DIR / f"{clip_id}_{aspect_suffix}_captioned.mp4"

    # libass needs the path escaped for the filtergraph
    escaped_ass = str(ass_path).replace("\\", "\\\\").replace(":", "\\:")

    vf_chain = [f"subtitles={escaped_ass}"]
    inputs = ["-i", str(source_clip_path)]
    filter_complex = None

    if logo_path and Path(logo_path).exists():
        # overlay logo bottom-right with a small margin, then burn captions
        filter_complex = (
            f"[0:v][1:v]overlay=W-w-30:30[bg];"
            f"[bg]subtitles={escaped_ass}[outv]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", str(source_clip_path), "-i", str(logo_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            str(out_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", str(source_clip_path),
            "-vf", ",".join(vf_chain),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            str(out_path),
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"ffmpeg caption burn-in failed for {clip_id}: {result.stderr[-1500:]}")
    return out_path
