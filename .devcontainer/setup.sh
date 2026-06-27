#!/usr/bin/env bash
# Aletheia — Codespaces / dev-container setup.
# Installs the package and all extras, and makes sure the spaCy knowledge-graph
# model genuinely LOADS (not just that the package is present). spaCy's CLI pulls
# in transitive deps like `click` (via typer) that are sometimes missing from
# pre-baked images — which leaves the model installed but `import spacy` raising
# ModuleNotFoundError, silently dropping the Archivist to its rule-based
# extractor. We repair that here so the Codespace gets the full graph.
set -u

echo "[aletheia] Installing dependencies (this takes a couple of minutes the first time)…"
python -m pip install --upgrade pip -q
python -m pip install -e ".[dev,graph,web]"

# Verify spaCy can actually load the model; repair the install if not.
if ! python -c "import spacy; spacy.load('en_core_web_sm')" >/dev/null 2>&1; then
  echo "[aletheia] Repairing spaCy (installing click/typer, ensuring the model)…"
  python -m pip install -q "click>=8.0" "typer>=0.9" || true
  python -c "import en_core_web_sm" >/dev/null 2>&1 \
    || python -m spacy download en_core_web_sm --quiet >/dev/null 2>&1 || true
fi

echo ""
if python -c "import spacy; spacy.load('en_core_web_sm')" >/dev/null 2>&1; then
  echo "✅ Aletheia is ready — full spaCy knowledge graph active."
else
  echo "✅ Aletheia is ready — using the rule-based extractor (spaCy model unavailable; the system still runs)."
fi
echo "   Try:  python main.py        (terminal console)"
echo "    or:  python main.py --web  (browser interface)"
