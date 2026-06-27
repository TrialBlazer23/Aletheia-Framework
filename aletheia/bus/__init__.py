"""The message bus — the Domino Cascade backbone.

Agents depend only on the ``MessageBus`` interface, never on a concrete
implementation. Today that's an in-process async pub/sub; tomorrow it can be
Redis/NATS — without touching a single agent (CLAUDE.md §10).
"""

from aletheia.bus.base import MessageBus, Subscription
from aletheia.bus.in_process import InProcessBus

__all__ = ["MessageBus", "Subscription", "InProcessBus"]
