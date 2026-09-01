#!/usr/bin/env bash
# Clip Factory — one-time setup (Mac or Linux). Run:  ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"
need() { command -v "$1" >/dev/null 2>&1; }
echo "== Clip Factory setup =="
case "$(uname -s)" in
  Darwin)
    if ! need brew; then
      echo "Homebrew isn't installed. Install it from https://brew.sh (one command), then run ./setup.sh again."; exit 1
    fi
    need ffmpeg  || { echo "Installing ffmpeg…";  brew install ffmpeg; }
    need python3 || { echo "Installing Python…";  brew install python; }
    need node    || { echo "Installing Node…";    brew install node; }
    ;;
  *)
    if ! need ffmpeg || ! need python3 || ! need node; then
      echo "This needs ffmpeg, python3 and node. On Ubuntu/Debian:"
      echo "  sudo apt install -y ffmpeg python3 python3-venv nodejs npm"
      exit 1
    fi
    ;;
esac
need ffprobe || { echo "ffprobe is missing (it ships with ffmpeg). Reinstall ffmpeg and try again."; exit 1; }

echo "-- Python packages (this takes a few minutes the first time)"
[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "-- Building the web app"
( cd frontend && npm ci --no-audit --no-fund && npm run build )

echo
echo "Setup done. Start it any time with:   ./start.sh"
