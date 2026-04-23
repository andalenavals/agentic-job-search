#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

EMAIL_ENV_FILE="${EMAIL_ENV_FILE:-data/email.env}"

if [[ -f "$EMAIL_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$EMAIL_ENV_FILE"
fi

if [[ -z "${EMAIL_TO:-}" ]]; then
  echo "EMAIL_TO is required. Set it in data/email.env or export it before running." >&2
  exit 1
fi

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m job_searcher \
  --title "${JOB_TITLE:-Data}" \
  --location all \
  --source all \
  --include-unverified \
  --debug-links \
  --debug-limit "${DEBUG_LIMIT:-10}" \
  --debug-timeout "${DEBUG_TIMEOUT:-8}" \
  --email-to "$EMAIL_TO" \
  --email-top "${EMAIL_TOP:-5}" \
  --email-sort newest \
  --output "${OUTPUT_PATH:-reports/top-newest-email.md}"
