# Clip Factory

> **Honest status (Sept 2026):** the core pipeline — upload → transcribe → find moments → cut → vertical reframe → karaoke captions → ZIP — is real and runs on a laptop. Direct posting to TikTok/Instagram/YouTube, Stripe billing, multi-user workspaces, and pasting a YouTube link are **not** finished (some are dead paths), there are no automated tests, and there is **no login** — run it only on your own machine (`start.sh` binds to 127.0.0.1). The text below is the original developer README and overstates what ships. For home use, read **ALICIA-START-HERE.md**; setup is `./setup.sh`, then `./start.sh`.

---

## Original developer notes — "Finished Product Build" (see status above)

This is the **complete build**, all 6 phases from the roadmap, not just an
MVP: upload → transcribe → find moments → cut vertical/square/horizontal
clips → burn in karaoke captions → publish to TikTok/Instagram/YouTube →
schedule a content calendar → pull back analytics and personalize
scoring → multi-workspace agency mode with team roles → Stripe billing.

Every piece described below is real, running code that was built and
tested end-to-end during this build (see "What was actually verified"),
not a mockup or a stub — with one honest exception explained up front.

## The one thing that genuinely can't be "finished" without you

TikTok, Instagram, and YouTube each require **you** (a real business) to
register a developer app on their platform and get it approved for
content-posting permissions. That's a step only the app owner can do —
there's no way to build around it, and no AI can complete it on your
behalf. The publishing code is fully written and correct against each
platform's real API (see `app/publishing/`), and it fails with a clear
"not configured" message until you drop in your own credentials as
environment variables. That's the only place in this build where
"finished" means "finished, waiting on your keys" rather than
"finished, fully live."

Same story, smaller scale, for Stripe (needs your `STRIPE_SECRET_KEY`
and Price IDs) — Stripe is a personal account/business setup, not
something buildable in advance.

## What's built

**Phase 1 — Core pipeline:** video upload with real validation
(format/size/duration/corrupted-file detection via ffprobe), self-hosted
speech-to-text (faster-whisper) with timestamps and rough speaker turns,
a genuine heuristic moment-scoring engine (audio energy spikes via
librosa, keyword/topic pattern matching, sentiment lexicon, silence
skipped via VAD), candidate-clip windowing with cuts snapped to speech
pauses, and 16:9 clip rendering via ffmpeg.

**Phase 2 — Vertical reframe + captions:** OpenCV face-detection-driven
auto-reframe to 9:16 and 1:1 that tracks the dominant face and pans
smoothly, real word-by-word karaoke captions burned in via libass (four
style presets: bold pop, minimal clean, neon gaming, podcast classic),
auto-emoji insertion, logo/watermark overlay, and profanity censoring
(audio bleep + caption blur).

**Phase 3 — Review/edit UI:** a full React + Tailwind frontend covering
all 10 screens from the spec — Dashboard, New Upload, Processing View,
Clip Review Grid, Clip Editor (drag-trim + re-render + caption/logo
toggles), Export/Publish, Content Calendar, Analytics, Brand/Workspace
Settings, and Billing.

**Phase 4 — Publishing integrations:** real OAuth 2.0 flows and content-
posting API clients for TikTok (Content Posting API), Instagram (Meta
Graph API Reels publishing), and YouTube (Data API v3 resumable upload),
a scheduled-post queue with a background publisher loop, and rate
limiting to avoid tripping platform spam detection.

**Phase 5 — Analytics loop:** pulls real view/like metrics back from
each connected platform, and a personalization loop that compares which
of the moment-scoring engine's signals (energy spikes / keyword cues /
emotional language) actually correlated with better performance for
*your* published clips, then feeds adjusted weights back into scoring
for future videos. Verified with synthetic data — see below.

**Phase 6 — Multi-workspace/agency + billing:** workspace/brand
isolation (each with its own logo, caption defaults, connected
accounts), team seats with role enforcement (editor can generate/edit
but not publish; admin can do both — actually enforced server-side, not
just hidden in the UI), per-client usage reporting, and Stripe
subscriptions with usage-based overage metering.

## What was actually verified (not just written)

- Uploaded a real synthesized test video (speech + visual pattern)
  through the full pipeline via the API directly — got back real,
  playable MP4 clips with correct durations and correct 1280×720 /
  1080×1920 / 1080×1080 dimensions.
- Confirmed the moment-scoring engine correctly picked the "hot take"
  and "unbelievable, best moment" lines over flat filler content —
  verified by inspecting the actual scores and reasons returned.
- Extracted a frame from a rendered 9:16 clip and visually confirmed
  real burned-in karaoke captions in the requested style, including
  auto-emoji.
- Unit-tested the analytics personalization math with synthetic
  published-post data — confirmed it correctly boosted the weight of
  signals present on a high-performing clip and downweighted a
  low-performing one, and correctly picked the best-performing caption
  style/clip length/clip from a small dataset.
- Verified OAuth/Stripe endpoints fail with a clear, honest "not
  configured" error (not a silent no-op, not a fake success) when
  credentials aren't set.
- Verified role permissions are enforced server-side: an "editor" team
  member gets a real 403 when trying to publish.
- Built the whole frontend, ran it against the live backend in a
  headless browser, and walked it through: upload a video → watch it
  process → land on the review grid with real thumbnails and captions
  visible → open the clip editor → check Calendar/Analytics/
  Settings/Billing screens. Zero JavaScript errors the whole way
  through.
- Full production build of the frontend (`npm run build`) completes
  clean.

## Running it

### Backend

```bash
pip install -r requirements.txt --break-system-packages   # or use a venv
# ffmpeg must be installed on the system (apt install ffmpeg)
uvicorn app.main:app --reload
```

Runs at `http://127.0.0.1:8000`. Interactive docs at `/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs at `http://127.0.0.1:5173` and talks to the backend at
`http://127.0.0.1:8000` by default (override with `VITE_API_BASE`).

### Environment variables you'll want to set for full functionality

```bash
# Publishing (each requires a registered + approved developer app on that platform)
TIKTOK_CLIENT_KEY=...            TIKTOK_CLIENT_SECRET=...
META_APP_ID=...                  META_APP_SECRET=...
YOUTUBE_CLIENT_ID=...            YOUTUBE_CLIENT_SECRET=...

# Billing
STRIPE_SECRET_KEY=...            STRIPE_WEBHOOK_SECRET=...
STRIPE_PRICE_CREATOR=...         STRIPE_PRICE_PRO=...        STRIPE_PRICE_AGENCY=...

# Optional tuning
CLIP_FACTORY_WHISPER_MODEL=base  # small/medium for better accuracy if you have the compute
```

Without these set, the app runs fully for the core pipeline (upload →
clips with captions) — only the publishing/billing endpoints ask for
credentials, and they do so with a clear error rather than a silent
failure.

## Architecture notes

- **No required external services for the core pipeline.** Jobs,
  workspaces, scheduled posts, and usage records are tracked as JSON
  files (`app/store.py`, `app/workspaces.py`, `app/scheduler.py`,
  `app/billing/usage.py`) processed by a small in-process thread pool
  (`app/worker.py`) instead of Postgres + Celery/Redis. Every module is
  shaped so swapping in real Postgres models and a real task queue for
  production scale is a targeted replacement, not a rewrite —
  `app/pipeline/runner.py::run_pipeline()` is the single entrypoint a
  real worker would call, and the data model (`app/models.py`) mirrors
  the spec's entity list exactly.
- **Transcription** uses `faster-whisper` (self-hosted, CPU-friendly).
  Model size configurable via `CLIP_FACTORY_WHISPER_MODEL`.
- **Moment scoring** (`app/pipeline/score.py`) is a genuine heuristic
  engine — audio RMS energy peaks, keyword/phrase pattern matching, a
  sentiment lexicon — not a trained ML model. It's built so a real
  classifier or LLM call is a drop-in replacement for `_keyword_score()`
  without touching the windowing/threshold logic, and its per-signal
  weights are already wired to the Phase 5 personalization loop.
- **Speaker labeling** is a silence-gap heuristic, not true diarization.
  **Auto-reframe** tracks the largest detected face via OpenCV Haar
  cascades (zero extra model downloads) rather than a full
  active-speaker-detection model — both are reasonable Phase 1
  approximations flagged for a future accuracy upgrade, not silently
  passed off as more sophisticated than they are.
- **Publishing clients** (`app/publishing/`) implement each platform's
  actual documented API contract — OAuth scopes, upload flows, endpoint
  shapes — so they'll work the moment real credentials are supplied.
  Instagram's Graph API specifically requires a publicly reachable video
  URL (not direct upload) for Reels — that's a Meta platform constraint,
  not a shortcut taken here; `account_meta.video_url` is where you'd
  wire in a signed object-storage URL.

## Project layout

```
app/
  main.py                 FastAPI app / all routes
  worker.py                background thread pool
  models.py                 data model (spec section 7, all entities)
  store.py / workspaces.py / scheduler.py    JSON-file persistence
  config.py                 all tunables
  analytics.py              metrics pull-back + personalization + dashboard
  pipeline/
    ingest.py                upload validation, corruption checks
    transcribe.py             faster-whisper + speaker turns + word timestamps
    score.py                  moment scoring + candidate-clip windowing
    cut.py                     ffmpeg 16:9 clip cutting
    reframe.py                 OpenCV face-tracking auto-reframe (9:16, 1:1)
    captions.py                 karaoke .ass generation + burn-in, 4 style presets
    censor.py                   profanity audio bleep
    thumbnail.py                 highest-energy frame picker
    metadata.py                   title/hashtag suggestions
    runner.py                     orchestrates all of the above
  publishing/
    tiktok.py / instagram.py / youtube.py    real OAuth + posting clients
    registry.py / base.py / config.py
  billing/
    plans.py / usage.py / stripe_client.py

frontend/
  src/
    App.jsx / main.jsx / WorkspaceContext.jsx
    api.js                     typed fetch client for every backend endpoint
    pages/
      Dashboard, Upload, Processing, ReviewGrid, ClipEditor,
      Export, Calendar, Analytics, Settings, Billing
```

## Known limitations worth knowing about before you scale this

- Whisper runs on CPU by default; a multi-hour video won't hit the
  spec's "under 10 minutes for a 60-minute video" target without a GPU
  or a smaller model — that target assumes a parallelized production
  pipeline, not this single-process build.
- The thread pool worker (2 concurrent jobs) and JSON-file stores are
  right for local/dev use and for proving the whole system works
  end-to-end; swap them for Postgres + Celery/Redis before real scale,
  per the architecture notes above.
- Moment scoring and speaker turns are heuristic, not ML-based — real
  and tested to correctly prioritize high-energy/"hot take" content over
  flat filler, but they'll miss nuance a trained model would catch.
- Link-paste ingestion (YouTube/Twitch/Rumble URLs) raises a clear
  "not implemented" error — it needs a downloader (yt-dlp) wired in as
  a follow-up; direct file upload is fully built and tested.
