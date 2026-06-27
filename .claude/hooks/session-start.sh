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

# Editable install with dev + graph extras: pydantic, pyyaml, anthropic (live
# Claude), pytest, plus spaCy + networkx and the en_core_web_sm model (the
# Archivist's knowledge graph). Idempotent and cache-friendly — safe to re-run.
python -m pip install --quiet -e ".[dev,graph]"

# Belt-and-suspenders: ensure spaCy genuinely *loads the model*, not just that
# the package is present. `import spacy` pulls in spaCy's CLI, which needs
# transitive deps like `click` (via typer) that have been seen missing from
# pre-baked images — leaving the model installed but `import spacy` raising
# ModuleNotFoundError, which silently drops the Archivist to its rule-based
# extractor. So: try a real load; if it fails, repair the install (click/typer),
# then fall back to the downloader; if all of that fails, the system still runs
# on the rule-based extractor.
if ! python -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null; then
  python -m pip install --quiet "click>=8.0" "typer>=0.9" 2>/dev/null || true
  python -c "import en_core_web_sm" 2>/dev/null \
    || python -m spacy download en_core_web_sm --quiet 2>/dev/null || true
  python -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null \
    || echo "[aletheia] note: spaCy unavailable; Archivist will use the rule-based extractor."
fi

echo "[aletheia] SessionStart: dependencies installed (anthropic + pytest + knowledge graph ready)."
