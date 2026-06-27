"""The ``LLMProvider`` interface.

A deliberately tiny surface: ``generate(system, user)`` returns text. That's all
an agent needs, and keeping it minimal is what lets any backend slot in.

``is_live`` tells an agent whether a real model is available, so it can degrade
gracefully (e.g. the Narrator falls back to an extractive answer offline rather
than failing).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    #: Human-readable provider name (e.g. "Anthropic Claude (claude-opus-4-8)").
    name: str = "LLMProvider"
    #: True when a real model backs this provider; False for the offline stub.
    is_live: bool = False

    @abstractmethod
    def generate(self, *, system: str, user: str, max_tokens: int = 2048) -> str:
        """Return the model's text completion for a system + user prompt."""
