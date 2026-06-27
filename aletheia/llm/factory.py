"""Pick the LLM provider from the environment.

Default order: if ``ANTHROPIC_API_KEY`` is set and the SDK imports, use Claude;
otherwise fall back to the offline provider so the system still runs. This is
what lets a non-coder owner run ``python main.py`` before wiring up a key.
"""

from __future__ import annotations

import os

from aletheia.config import load_local_env
from aletheia.llm.base import LLMProvider
from aletheia.llm.offline_provider import OfflineProvider


def get_default_provider() -> LLMProvider:
    # Pick up a key from a local .env file if one exists (no-op otherwise).
    load_local_env()
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            from aletheia.llm.anthropic_provider import AnthropicProvider

            return AnthropicProvider()
        except Exception as exc:  # SDK missing, bad key shape, etc. — degrade, don't crash.
            print(f"[aletheia] Claude unavailable ({exc!r}); using offline provider.")
    return OfflineProvider()
