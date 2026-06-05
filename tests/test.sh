#!/usr/bin/env bash
set -euo pipefail

mkdir -p /logs/verifier

if PYTHONPATH="${PYTHONPATH:-}:/app" python3 -m pytest /tests/test_outputs.py -q; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
