#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target_root="${TARGET_ROOT:-/app}"

if [ ! -d "$target_root/manifestlane" ]; then
  echo "Expected source tree at $target_root/manifestlane" >&2
  exit 1
fi

patch -d "$target_root" -p1 < "$script_dir/sol.patch"
