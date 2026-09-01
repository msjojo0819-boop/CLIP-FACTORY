#!/usr/bin/env bash
# Clip Factory — start it. Run:  ./start.sh   (Ctrl+C to stop)
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || { echo "Run ./setup.sh first."; exit 1; }
[ -f frontend/dist/index.html ] || { echo "The web app isn't built. Run ./setup.sh first."; exit 1; }
# shellcheck disable=SC1091
. .venv/bin/activate
# Speech model size: tiny (fastest) / base (default) / small (more accurate, slower)
export CLIP_FACTORY_WHISPER_MODEL="${CLIP_FACTORY_WHISPER_MODEL:-base}"
PORT="${PORT:-8000}"
URL="http://127.0.0.1:$PORT/ui/"
( sleep 3; command -v open >/dev/null && open "$URL" || { command -v xdg-open >/dev/null && xdg-open "$URL"; } ) >/dev/null 2>&1 &
echo "Clip Factory is starting at  $URL"
echo "Leave this window open while you use it. Press Ctrl+C to stop."
# 127.0.0.1 only: this app has no login, so it must never be exposed beyond this computer.
exec uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
