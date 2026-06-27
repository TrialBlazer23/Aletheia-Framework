#!/bin/bash
# Aletheia SessionStart hook — installs Python dependencies so the live Claude
# brain, tests, and tooling are available from the first prompt.
#
# Without this, a fresh Claude Code on the web container has no `anthropic` SDK
# installed, so the LLM factory silently degrades to the offline extractive
# provider (is_live=False) and `pytest` is missing — both easy to miss.
set -euo pipefail

# Only run in the remote (web) environment; local devs manage their own venv.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# Editable install with dev extras: pydantic, pyyaml, anthropic (live Claude),
# and pytest. Idempotent and cache-friendly — safe to re-run.
python -m pip install --quiet -e ".[dev]"

echo "[aletheia] SessionStart: dependencies installed (anthropic + pytest ready)."
