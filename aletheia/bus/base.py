"""The ``MessageBus`` interface — what every agent depends on.

The Domino Cascade is a broadcast medium: an agent publishes a Synapse message
and *any* agent whose Interest Profile matches reacts. The bus itself stays
deliberately dumb — it broadcasts and it records to the Cascade Log. All the
"who cares about this message" logic lives in each agent's Listener, exactly as
the design intends (the cascade is self-driving, not centrally routed).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable

from aletheia.protocol.messages import SynapseMessage

# A subscriber is any async callable that receives a broadcast message.
Subscriber = Callable[[SynapseMessage], Awaitable[None]]


class Subscription:
    """Handle returned by ``subscribe``; call ``unsubscribe`` to detach."""

    def __init__(self, bus: "MessageBus", subscriber: Subscriber) -> None:
        self._bus = bus
        self._subscriber = subscriber

    def unsubscribe(self) -> None:
        self._bus.unsubscribe(self._subscriber)


class MessageBus(ABC):
    """Abstract broadcast bus. Concrete buses must record to the Cascade Log."""

    @abstractmethod
    def subscribe(self, subscriber: Subscriber) -> Subscription:
        """Register an async subscriber for every broadcast message."""

    @abstractmethod
    def unsubscribe(self, subscriber: Subscriber) -> None:
        """Remove a previously registered subscriber."""

    @abstractmethod
    async def publish(self, message: SynapseMessage) -> None:
        """Record the message to the Cascade Log, then broadcast it."""
