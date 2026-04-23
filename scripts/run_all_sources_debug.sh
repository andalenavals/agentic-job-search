#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m job_searcher \
  --title "${JOB_TITLE:-Data}" \
  --location all \
  --source all \
  --include-unverified \
  --debug-links \
  --debug-limit "${DEBUG_LIMIT:-5}" \
  --debug-timeout "${DEBUG_TIMEOUT:-8}" \
  --output "${OUTPUT_PATH:-reports/gold-test-data.md}"
