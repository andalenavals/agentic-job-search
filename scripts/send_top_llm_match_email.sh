#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PROFILE_FILE="${PROFILE_FILE:-data/profile.txt}"
EMAIL_ENV_FILE="${EMAIL_ENV_FILE:-data/email.env}"
OUTPUT_PATH="${OUTPUT_PATH:-reports/top-llm-match-email.md}"

if [[ -f "$EMAIL_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$EMAIL_ENV_FILE"
fi

if [[ -z "${EMAIL_TO:-}" ]]; then
  echo "EMAIL_TO is required. Set it in data/email.env or export it before running." >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT_PATH")"

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m job_searcher \
  --title "${JOB_TITLE:-Data}" \
  --location all \
  --source all \
  --include-unverified \
  --debug-links \
  --debug-limit "${DEBUG_LIMIT:-10}" \
  --debug-timeout "${DEBUG_TIMEOUT:-8}" \
  --profile-file "$PROFILE_FILE" \
  --ollama-model "${OLLAMA_MODEL:-deepseek-r1:latest}" \
  --email-to "$EMAIL_TO" \
  --email-top "${EMAIL_TOP:-5}" \
  --email-sort match \
  --output "$OUTPUT_PATH"
