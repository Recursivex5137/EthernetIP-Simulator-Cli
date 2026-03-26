#!/usr/bin/env bash
set -euo pipefail

# Run from repo root. Creates .venv and installs headless dependencies only.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements-headless.txt

cat <<'EOF'

Headless setup complete.

Next steps:
  1) (Optional) Seed tags:
     ./.venv/bin/python sim_cli.py tags import --file examples/tags-sample.json

  2) Start simulator:
     ./.venv/bin/python sim_cli.py serve --host 0.0.0.0 --port 44818

EOF
