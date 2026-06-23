#!/usr/bin/env bash
# Package the submission into submission.tar.gz with the required top-level
# layout: main.py + deck.csv + agent/ + cg/  (no __pycache__).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
SUB="$REPO/sample_submission"
OUT="$REPO/submission.tar.gz"

echo "==> Validating deck"
python3 "$HERE/validate_deck.py" "$SUB/deck.csv"

echo "==> Packaging $OUT"
rm -f "$OUT"
EXTRA=""
[ -f "$SUB/value.json" ] && EXTRA="value.json" && echo "    (including learned value.json)"
tar --exclude='__pycache__' --exclude='*.pyc' \
    -C "$SUB" -czf "$OUT" main.py deck.csv agent cg $EXTRA

echo "==> Contents:"
tar -tzf "$OUT"
echo "==> Done: $OUT"
