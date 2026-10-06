#!/usr/bin/env bash
# Thin wrapper around run_review.py
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$ROOT/scripts/run_review.py" "$@"
