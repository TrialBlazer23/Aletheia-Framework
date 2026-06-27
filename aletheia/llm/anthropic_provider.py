"""Anthropic Claude provider — the default brain (CLAUDE.md §10).

The ``anthropic`` SDK is imported lazily inside ``__init__`` so the package
installs and runs without it; the factory falls back to the offline provider if
the SDK or an API key is missing.

Model defaults follow the build conventions: a strong model for the reasoning /
generation step, overridable via env. Routine steps elsewhere can pass a cheaper
model id explicitly.
"""

from __future__ import annotations

import os

from aletheia.llm.base import LLMProvider

# Strong default for user-facing generation. Override with ALETHEIA_LLM_MODEL.
DEFAULT_MODEL = "claude-opus-4-8"


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        # Lazy import: keeps `anthropic` an optional dependency.
        import anthropic  # noqa: PLC0415

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = model or os.getenv("ALETHEIA_LLM_MODEL", DEFAULT_MODEL)
        self.name = f"Anthropic Claude ({self.model})"
        self.is_live = True

    def generate(self, *, system: str, user: str, max_tokens: int = 2048) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # response.content is a list of blocks; collect the text blocks.
        return "".join(b.text for b in response.content if b.type == "text").strip()
