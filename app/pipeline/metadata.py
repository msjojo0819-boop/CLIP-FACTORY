"""
Metadata assist — spec section 3.5 (title/hashtag portion only; thumbnail
frame picking and publishing integrations are Phase 2/4).

Heuristic, template-based generation from the clip's transcript text and
detected reasons. Good enough to ship real, non-empty suggestions in
Phase 1; swapping in an LLM call here later is a drop-in replacement.
"""
from __future__ import annotations

import re

TITLE_TEMPLATES = [
    "{hook}",
    "This is why {topic}...",
    "Wait for it 👀",
    "You won't believe what happens here",
    "The moment everything changed",
]

STOPWORDS = {
    "the", "a", "an", "is", "was", "were", "and", "or", "but", "to", "of",
    "in", "on", "for", "with", "that", "this", "it", "i", "you", "we",
    "they", "he", "she", "so", "just", "like", "know", "really", "im",
}


def _top_keywords(text: str, n: int = 3) -> list[str]:
    words = re.findall(r"[a-zA-Z']+", text.lower())
    words = [w for w in words if w not in STOPWORDS and len(w) > 3]
    seen = []
    for w in words:
        if w not in seen:
            seen.append(w)
    return seen[:n]


def suggest_titles(clip_text: str) -> list[str]:
    hook = clip_text.strip().split(".")[0][:70].strip()
    if not hook:
        hook = clip_text[:70].strip()
    keywords = _top_keywords(clip_text)
    topic = keywords[0] if keywords else "this happened"

    titles = [
        hook.rstrip(",") + ("..." if len(clip_text) > len(hook) else ""),
        f"This is why {topic}...",
        "Wait for it 👀" if "?" not in clip_text else "You need to hear this",
    ]
    # de-dupe, keep order, always return exactly 3 per spec
    out = []
    for t in titles:
        if t and t not in out:
            out.append(t)
    while len(out) < 3:
        out.append("You won't believe this clip")
    return out[:3]


def suggest_hashtags(clip_text: str, reasons: list[str]) -> list[str]:
    keywords = _top_keywords(clip_text, n=5)
    tags = [f"#{w}" for w in keywords]

    if "keyword/topic cue" in reasons:
        tags.append("#hottake")
    if "emotional language" in reasons:
        tags.append("#unfiltered")
    if "audio energy spike" in reasons:
        tags.append("#viral")

    tags += ["#fyp", "#shorts", "#clips"]

    out = []
    for t in tags:
        if t not in out:
            out.append(t)
    return out[:8]
