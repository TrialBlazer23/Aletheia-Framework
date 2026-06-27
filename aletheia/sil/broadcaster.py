"""The Broadcaster ("the Mouth" / Encoder) — NSAP-0002.

Required functions per the spec:

* ``receiveDataFromParent(output)`` — take the parent model's raw result.
* ``packagePayload(output)`` — summarize, assign new UIDs, attach metadata.
* ``constructEventMessage(payload)`` — build the formal Synapse EVENT.
* ``broadcast()`` — put it on the bus.

The Broadcaster also emits the two non-EVENT messages the handshake needs
(``acknowledge`` → STATE_CHANGE: TASK_ACCEPTED) and lets an agent send TRIGGERs
to command others. Everything goes out through the bus, so it all lands in the
Cascade Log.
"""

from __future__ import annotations

from typing import Any

from aletheia.bus.base import MessageBus
from aletheia.protocol.messages import (
    SynapseMessage,
    make_event,
    make_state_change,
    make_trigger,
)
from aletheia.protocol.uids import new_uid


class Broadcaster:
    def __init__(self, owner_uid: str, bus: MessageBus) -> None:
        self._owner_uid = owner_uid
        self._bus = bus

    async def broadcast_event(
        self,
        *,
        event_name: str,
        data_asset_uid: str | None = None,
        asset_category: str = "ASSET",
        asset_type: str = "RESULT",
        description: str = "",
        confidence_score: float | None = None,
    ) -> SynapseMessage:
        """Package the parent's output as an EVENT and broadcast it.

        If no ``data_asset_uid`` is supplied, a fresh one is minted — the
        Broadcaster "assigns new UIDs to the data assets created" per the spec.
        """
        if data_asset_uid is None:
            data_asset_uid = new_uid(asset_category, asset_type)
        msg = make_event(
            source_uid=self._owner_uid,
            event_name=event_name,
            data_asset_uid=data_asset_uid,
            description=description,
            confidence_score=confidence_score,
        )
        await self._bus.publish(msg)
        return msg

    async def acknowledge(self, *, originator_uid: str, reason: str = "") -> SynapseMessage:
        """Handshake step 2: low-priority STATE_CHANGE: TASK_ACCEPTED."""
        msg = make_state_change(
            source_uid=self._owner_uid,
            target_uid=originator_uid,
            status_code="TASK_ACCEPTED",
            reason=reason,
        )
        await self._bus.publish(msg)
        return msg

    async def report_state(
        self, *, target_uid: str, status_code: str, reason: str = ""
    ) -> SynapseMessage:
        """Emit an arbitrary STATE_CHANGE (e.g. TASK_COMPLETE, ERROR_*)."""
        msg = make_state_change(
            source_uid=self._owner_uid,
            target_uid=target_uid,
            status_code=status_code,
            reason=reason,
        )
        await self._bus.publish(msg)
        return msg

    async def send_trigger(
        self,
        *,
        target_uid: str,
        action_to_trigger: str,
        on_event: str = "IMMEDIATE",
        parameters: dict[str, Any] | None = None,
    ) -> SynapseMessage:
        """Command another agent via a TRIGGER."""
        msg = make_trigger(
            source_uid=self._owner_uid,
            target_uid=target_uid,
            action_to_trigger=action_to_trigger,
            on_event=on_event,
            parameters=parameters,
        )
        await self._bus.publish(msg)
        return msg
