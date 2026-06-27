"""The Nexus-Mind (0x0001) — orchestrator ("System 2").

It does not process raw data itself. For a Q&A turn it decomposes the request
into the cascade "retrieve → narrate → judge": it TRIGGERs the Archivist, then
waits for the **Philosopher's** verdict (its Listener is tuned to ``APPROVED`` /
``REJECTED``), and returns a ``QAResult`` that carries both the answer and the
verdict.

If the Philosopher vetoes, the Narrator's draft never reaches the user — the
Nexus-Mind returns a withheld result citing the directive instead. Each turn
carries a ``turn_id`` threaded through the asset chain so the verdict is matched
back to the question.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from aletheia.agents.family import ARCHIVIST_UID, NEXUS_MIND_UID, PHILOSOPHER_UID
from aletheia.agents.family_member import FamilyMember
from aletheia.bus.base import MessageBus
from aletheia.memory.asset_store import AssetStore
from aletheia.protocol.messages import MessageType, SynapseMessage
from aletheia.protocol.uids import new_uid
from aletheia.sdr.primitives import AnswerAsset, SdrEthicalAnalysisReport
from aletheia.sil.interest_profile import InterestProfile, InterestRule


@dataclass
class QAResult:
    """The final outcome of a Q&A turn: the answer plus the Philosopher's verdict."""

    question: str
    answer: str
    approved: bool
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.0
    directive: str | None = None  # the directive cited on a veto
    reason: str | None = None  # human-readable veto reason
    report_uid: str | None = None  # the SDR_Ethical_Analysis_Report, for audit


def _nexus_profile() -> InterestProfile:
    return InterestProfile(
        [
            InterestRule(
                action_to_trigger="RELEASE_ANSWER",
                source_model_uid=PHILOSOPHER_UID,
                message_type=MessageType.EVENT,
                event_name="APPROVED",
            ),
            InterestRule(
                action_to_trigger="HANDLE_VETO",
                source_model_uid=PHILOSOPHER_UID,
                message_type=MessageType.EVENT,
                event_name="REJECTED",
            ),
        ]
    )


class NexusMind(FamilyMember):
    def __init__(self, *, bus: MessageBus, asset_store: AssetStore) -> None:
        super().__init__(
            name="Nexus-Mind", uid=NEXUS_MIND_UID, bus=bus, interest_profile=_nexus_profile()
        )
        self._assets = asset_store
        self._pending: dict[str, asyncio.Future[QAResult]] = {}

    async def ask(self, question: str, *, timeout: float = 60.0) -> QAResult:
        """Run one Q&A cascade and return the result (answer + verdict)."""
        turn_id = new_uid("TURN", "QA")
        loop = asyncio.get_event_loop()
        future: asyncio.Future[QAResult] = loop.create_future()
        self._pending[turn_id] = future

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
        if action == "RELEASE_ANSWER":
            answer: AnswerAsset = self._assets.get(data["data_asset_uid"])
            self._resolve(
                answer.turn_id,
                QAResult(
                    question=answer.question,
                    answer=answer.answer.text,
                    approved=True,
                    sources=list(answer.sources),
                    confidence=answer.confidence.score,
                ),
            )
        elif action == "HANDLE_VETO":
            report: SdrEthicalAnalysisReport = self._assets.get(data["data_asset_uid"])
            top = report.violations[0] if report.violations else None
            reason = report.reasoning.text
            self._resolve(
                report.turn_id,
                QAResult(
                    question="",  # the question isn't echoed in the report
                    answer=(
                        "⛔ This response was withheld by the Philosopher because it would "
                        f"violate a Prime Directive ({top.directive_name if top else 'unknown'})."
                    ),
                    approved=False,
                    directive=top.directive_name if top else None,
                    reason=reason,
                    report_uid=report.synapse_uid,
                ),
            )

    def _resolve(self, turn_id: str, result: QAResult) -> None:
        future = self._pending.get(turn_id)
        if future is not None and not future.done():
            future.set_result(result)
