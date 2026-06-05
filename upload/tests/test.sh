#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
TEST_ROOT="${TEST_ROOT:-/tests}"
REWARD_FILE="${REWARD_FILE:-/logs/verifier/reward.txt}"
APP_PARENT="$(dirname "${APP_UNDER_TEST:-/app/manifestlane}")"

mkdir -p "$(dirname "$REWARD_FILE")"

if PYTHONPATH="${PYTHONPATH:-}:$APP_PARENT:/app" "$PYTHON_BIN" -m pytest "$TEST_ROOT/test_outputs.py" -q; then
  echo 1 > "$REWARD_FILE"
else
  echo 0 > "$REWARD_FILE"
fi
