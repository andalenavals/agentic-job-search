#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

EMAIL_ENV_FILE="${EMAIL_ENV_FILE:-data/email.env}"
OUTPUT_PATH="${OUTPUT_PATH:-reports/top-newest-email.md}"
ACTION_OUTPUT_PATH="${ACTION_OUTPUT_PATH:-${OUTPUT_PATH%.md}_action.md}"

if [[ -f "$EMAIL_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$EMAIL_ENV_FILE"
fi

mkdir -p "$(dirname "$OUTPUT_PATH")"
mkdir -p "$(dirname "$ACTION_OUTPUT_PATH")"

EMAIL_ARGS=()
if [[ -n "${EMAIL_TO:-}" ]] \
  && [[ "${EMAIL_TO:-}" != "recipient@example.com" ]] \
  && [[ "${JOB_SEARCH_SMTP_USER:-}" != "your-address@gmail.com" ]] \
  && [[ "${JOB_SEARCH_SMTP_PASSWORD:-}" != "your-google-app-password" ]] \
  && [[ "${JOB_SEARCH_EMAIL_FROM:-}" != "your-address@gmail.com" ]]; then
  EMAIL_ARGS=(
    --email-to "$EMAIL_TO"
    --email-top "${EMAIL_TOP:-5}"
    --email-sort newest
  )
else
  echo "warning: email env is not configured; skipping email notification." >&2
fi

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m job_searcher \
  --title "${JOB_TITLE:-Data}" \
  --location all \
  --source all \
  --include-unverified \
  --debug-links \
  --debug-limit "${DEBUG_LIMIT:-10}" \
  --debug-timeout "${DEBUG_TIMEOUT:-8}" \
  --action-output "$ACTION_OUTPUT_PATH" \
  "${EMAIL_ARGS[@]}" \
  --output "$OUTPUT_PATH"
