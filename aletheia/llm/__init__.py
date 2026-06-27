"""The ``LLMProvider`` interface — the brains behind the agents.

Agents never import a specific model SDK. They depend only on ``LLMProvider``,
so today's default (Anthropic Claude) can become any other provider — or a local
model — without touching agent code (CLAUDE.md §10). An offline fallback keeps
the whole system runnable before an API key is configured.
"""

from aletheia.llm.base import LLMProvider
from aletheia.llm.factory import get_default_provider

__all__ = ["LLMProvider", "get_default_provider"]
