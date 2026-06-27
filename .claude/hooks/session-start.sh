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

# Editable install with dev + graph + web extras: pydantic, pyyaml, anthropic
# (live Claude), pytest, spaCy + networkx and the en_core_web_sm model (the
# Archivist's knowledge graph), and FastAPI/uvicorn (the browser UI). Idempotent
# and cache-friendly — safe to re-run.
python -m pip install --quiet -e ".[dev,graph,web]"

# Belt-and-suspenders: ensure the spaCy model is importable. If the [graph]
# wheel URL is ever unreachable, fall back to the spaCy downloader; if that also
# fails, the Archivist degrades to its rule-based extractor (system still runs).
python -c "import en_core_web_sm" 2>/dev/null \
  || python -m spacy download en_core_web_sm --quiet 2>/dev/null \
  || echo "[aletheia] note: spaCy model unavailable; Archivist will use the rule-based extractor."

echo "[aletheia] SessionStart: dependencies installed (anthropic + pytest + knowledge graph ready)."
