"""``FamilyMember`` — the base every Aletheia agent inherits.

It wraps an agent's core logic in a Synapse Interface Layer (a Listener + a
Broadcaster) and enforces the canonical 4-step handshake from NSAP-0002 so every
cascade is resilient and fully traceable:

    1. RECEIVE   — the Listener catches a relevant TRIGGER/EVENT.
    2. ACKNOWLEDGE — immediately broadcast STATE_CHANGE: TASK_ACCEPTED, so the
                   Diagnostician can track the flow.
    3. EXECUTE   — run the agent's core function (``handle_action``).
    4. COMPLETE & BROADCAST — the agent's handler emits its result EVENT, which
                   may trip downstream Listeners and continue the cascade.

Subclasses implement ``handle_action(action, data, message)``. Inside it they
use ``self.broadcaster`` to emit EVENTs / TRIGGERs / STATE_CHANGEs.
"""

from __future__ import annotations

from typing import Any

from aletheia.bus.base import MessageBus, Subscription
from aletheia.protocol.messages import SynapseMessage
from aletheia.sil.broadcaster import Broadcaster
from aletheia.sil.interest_profile import InterestProfile
from aletheia.sil.listener import Listener, RelevantMessage


class FamilyMember:
    """Base agent: SIL wiring + the Synapse handshake.

    Parameters
    ----------
    name:
        Human-readable role name (e.g. ``"Archivist"``).
    uid:
        Canonical Synapse UID for this agent (e.g. ``"MODEL:Archivist:0x00A1"``).
    bus:
        The message bus to attach to.
    interest_profile:
        What EVENT/STATE_CHANGE messages this agent reacts to. TRIGGERs addressed
        to this agent's UID are always handled regardless of the profile.
    """

    def __init__(
        self,
        *,
        name: str,
        uid: str,
        bus: MessageBus,
        interest_profile: InterestProfile | None = None,
    ) -> None:
        self.name = name
        self.uid = uid
        self._bus = bus
        self.listener = Listener(uid, interest_profile or InterestProfile())
        self.broadcaster = Broadcaster(uid, bus)
        self._subscription: Subscription | None = None

    # --- lifecycle --------------------------------------------------------- #
    def connect(self) -> None:
        """Attach the Listener to the bus (``scanNetwork``)."""
        if self._subscription is None:
            self._subscription = self._bus.subscribe(self._on_message)

    def disconnect(self) -> None:
        if self._subscription is not None:
            self._subscription.unsubscribe()
            self._subscription = None

    # --- the handshake ----------------------------------------------------- #
    async def _on_message(self, message: SynapseMessage) -> None:
        """Bus delivers every message here; we keep only the relevant ones."""
        relevant = self.listener.filter_relevant_messages(message)  # steps: scan+filter
        if relevant is None:
            return

        # Step 2 — ACKNOWLEDGE (so the Diagnostician sees the cascade advance).
        await self.broadcaster.acknowledge(
            originator_uid=message.source,
            reason=f"Listener received {message.type.value} -> action {relevant.action}.",
        )

        # Step 3 — EXECUTE the core function. Step 4 (broadcast the result) is the
        # handler's responsibility, since only the agent knows what it produced.
        await self.handle_action(relevant.action, relevant.data, relevant.message)

    # --- to be implemented by each concrete agent -------------------------- #
    async def handle_action(
        self, action: str, data: dict[str, Any], message: SynapseMessage
    ) -> None:
        """Run the agent's core logic for ``action``.

        Default is a no-op so a bare FamilyMember is inert. Concrete agents
        override this and call ``self.broadcaster.*`` to continue the cascade.
        """
        return None
