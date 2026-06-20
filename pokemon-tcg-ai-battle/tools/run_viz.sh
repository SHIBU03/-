#!/usr/bin/env bash
# Launch the local visualizer server (default http://127.0.0.1:8000).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
PORT="${1:-8000}"
exec python3 "$REPO/viz/server.py" --port "$PORT"
