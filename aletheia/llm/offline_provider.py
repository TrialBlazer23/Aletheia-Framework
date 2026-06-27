"""Offline provider — keeps Aletheia runnable with no API key.

It performs no real language modeling. When the system runs without a live
provider, agents that can degrade gracefully (notably the Narrator) detect
``is_live == False`` and produce a simple extractive answer from retrieved
context instead of calling this. If ``generate`` is called directly, it returns
a clearly-marked stub so behavior is never silently wrong.
"""

from __future__ import annotations

from aletheia.llm.base import LLMProvider


class OfflineProvider(LLMProvider):
    name = "Offline (no LLM — extractive fallback)"
    is_live = False

    def generate(self, *, system: str, user: str, max_tokens: int = 2048) -> str:
        return (
            "[offline mode] No language model is configured, so I can't compose a "
            "free-form answer. Set ANTHROPIC_API_KEY to enable Claude."
        )
