#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier

cd /

if env -i PATH="/usr/local/bin:/usr/bin:/bin" HOME="/tmp" APP_UNDER_TEST="/app/manifestlane" \
  python3 -I -B -m pytest -p no:cacheprovider /tests/test_outputs.py -q; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
