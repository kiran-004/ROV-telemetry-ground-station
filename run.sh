#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "$project_dir/.venv312/bin/python" ]]; then
    exec "$project_dir/.venv312/bin/python" "$project_dir/main.py" "$@"
fi
exec "$project_dir/.venv/bin/python" "$project_dir/main.py" "$@"
