"""Local configuration — load secrets from a ``.env`` file if present.

The owner stores their Claude API key in a ``.env`` file at the repo root (which
is git-ignored, so it never gets committed). This loads that file into the
process environment at startup so ``ANTHROPIC_API_KEY`` is available to the
provider — without any extra dependency.

Already-set environment variables always win: a key exported in the shell, or
one configured in a hosted/remote environment, is never overwritten by ``.env``.
"""

from __future__ import annotations

import os
from pathlib import Path

# Repo root = two levels up from this file (aletheia/config.py -> repo/).
_REPO_ROOT = Path(__file__).resolve().parents[1]


def load_local_env(path: str | Path | None = None) -> bool:
    """Load ``KEY=value`` lines from a ``.env`` file into ``os.environ``.

    Returns True if a file was found and read. Existing env vars are preserved.
    Supports ``#`` comments, blank lines, optional surrounding quotes, and an
    optional leading ``export``.
    """
    env_path = Path(path) if path is not None else _REPO_ROOT / ".env"
    if not env_path.is_file():
        return False

    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:  # never override an already-set var
            os.environ[key] = value
    return True
