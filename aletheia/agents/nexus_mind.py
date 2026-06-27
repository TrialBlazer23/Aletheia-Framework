"""The Nexus-Mind (0x0001) — orchestrator ("System 2").

It does not process raw data itself. For a Q&A turn it decomposes the request
into the cascade "retrieve, then narrate": it TRIGGERs the Archivist, then waits
for the Narrator's ``DRAFT_READY`` (its Listener is tuned to that event),
resolves the answer asset, and returns it to the caller.

Each turn carries a ``turn_id`` threaded through the asset chain so the answer is
matched back to the question — turns stay correct even if several run at once.
"""

from __future__ import annotations

import asyncio
from typing import Any

from aletheia.agents.family import ARCHIVIST_UID, NARRATOR_UID, NEXUS_MIND_UID
from aletheia.agents.family_member import FamilyMember
from aletheia.bus.base import MessageBus
from aletheia.memory.asset_store import AssetStore
from aletheia.protocol.messages import MessageType, SynapseMessage
from aletheia.protocol.uids import new_uid
from aletheia.sdr.primitives import AnswerAsset
from aletheia.sil.interest_profile import InterestProfile, InterestRule


def _nexus_profile() -> InterestProfile:
    return InterestProfile(
        [
            InterestRule(
                action_to_trigger="FINALIZE_ANSWER",
                source_model_uid=NARRATOR_UID,
                message_type=MessageType.EVENT,
                event_name="DRAFT_READY",
            )
        ]
    )


class NexusMind(FamilyMember):
    def __init__(self, *, bus: MessageBus, asset_store: AssetStore) -> None:
        super().__init__(
            name="Nexus-Mind", uid=NEXUS_MIND_UID, bus=bus, interest_profile=_nexus_profile()
        )
        self._assets = asset_store
        self._pending: dict[str, asyncio.Future[AnswerAsset]] = {}

    async def ask(self, question: str, *, timeout: float = 60.0) -> AnswerAsset:
        """Run one Q&A cascade and return the grounded answer asset."""
        turn_id = new_uid("TURN", "QA")
        loop = asyncio.get_event_loop()
        future: asyncio.Future[AnswerAsset] = loop.create_future()
        self._pending[turn_id] = future

        # Decompose: command the Archivist to retrieve context for this turn.
        await self.broadcaster.send_trigger(
            target_uid=ARCHIVIST_UID,
            action_to_trigger="RETRIEVE_CONTEXT",
            parameters={"question": question, "turn_id": turn_id},
        )

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop(turn_id, None)

    async def handle_action(
        self, action: str, data: dict[str, Any], message: SynapseMessage
    ) -> None:
        if action != "FINALIZE_ANSWER":
            return
        answer: AnswerAsset = self._assets.get(data["data_asset_uid"])
        future = self._pending.get(answer.turn_id)
        if future is not None and not future.done():
            future.set_result(answer)
