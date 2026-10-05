#!/usr/bin/env bash
set -euo pipefail
task_source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$task_source_dir/scripts/install.py" "$@"
