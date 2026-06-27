"""In-process async implementation of the Domino Cascade.

A single-process ``asyncio`` pub/sub. Zero infrastructure — the whole system
runs with ``python main.py`` — while preserving the exact Synapse broadcast
semantics. Swap this for Redis/NATS later behind the same ``MessageBus``
interface and no agent changes.

Every published message is first recorded to the Cascade Log (the Glass Box is
never bypassed), then delivered concurrently to all subscribers. A subscriber
that raises does not take down the bus or sibling subscribers; the error is
captured so the Diagnostician can later observe it.
"""

from __future__ import annotations

import asyncio
from typing import Any

from aletheia.bus.base import MessageBus, Subscriber, Subscription
from aletheia.log.cascade_log import CascadeLog
from aletheia.protocol.messages import SynapseMessage


class InProcessBus(MessageBus):
    def __init__(self, cascade_log: CascadeLog | None = None) -> None:
        self._subscribers: list[Subscriber] = []
        self._cascade_log = cascade_log or CascadeLog(path=None)
        # Surfaced for tests/observability; the Diagnostician will consume this.
        self.delivery_errors: list[tuple[str, BaseException]] = []

    @property
    def cascade_log(self) -> CascadeLog:
        return self._cascade_log

    def subscribe(self, subscriber: Subscriber) -> Subscription:
        self._subscribers.append(subscriber)
        return Subscription(self, subscriber)

    def unsubscribe(self, subscriber: Subscriber) -> None:
        try:
            self._subscribers.remove(subscriber)
        except ValueError:
            pass

    async def publish(self, message: SynapseMessage) -> None:
        # 1) Glass Box first: record before anyone reacts.
        self._cascade_log.record(message)

        # 2) Broadcast concurrently to every subscriber. Snapshot the list so a
        #    subscriber that (un)subscribes mid-delivery can't corrupt iteration.
        subscribers = list(self._subscribers)
        results: list[Any] = await asyncio.gather(
            *(sub(message) for sub in subscribers),
            return_exceptions=True,
        )
        for sub, result in zip(subscribers, results):
            if isinstance(result, BaseException):
                self.delivery_errors.append((getattr(sub, "__qualname__", repr(sub)), result))
