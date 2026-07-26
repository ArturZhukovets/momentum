#!/usr/bin/env bash
set -euo pipefail

# Always run from the project root (directory of this script).
cd "$(dirname "$0")"

exec uv run python -m momentum
