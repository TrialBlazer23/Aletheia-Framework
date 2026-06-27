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
from aletheia.sdr.primitives import CreativeAsset, SdrEthicalAnalysisReport
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
    turn_id: str = ""  # threads the turn's asset chain; used to give feedback


@dataclass
class CreativeResult:
    """The outcome of a creative turn: the Visionary's package + the verdict."""

    request: str
    approved: bool
    title: str = ""
    asset: CreativeAsset | None = None  # the full creative package, when approved
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.0
    directive: str | None = None  # the directive cited on a veto
    reason: str | None = None  # human-readable veto reason
    report_uid: str | None = None
    turn_id: str = ""


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
        self._pending: dict[str, asyncio.Future] = {}
        self._modes: dict[str, str] = {}  # turn_id -> "qa" | "creative"

    async def ask(self, question: str, *, timeout: float = 60.0) -> QAResult:
        """Run one Q&A cascade and return the result (answer + verdict)."""
        return await self._run_turn(question, mode="qa", uid_type="QA", timeout=timeout)

    async def create(self, request: str, *, timeout: float = 60.0) -> CreativeResult:
        """Run one creative cascade (Archivist → Narrator → Visionary → Philosopher)."""
        return await self._run_turn(request, mode="creative", uid_type="CREATE", timeout=timeout)

    async def _run_turn(self, request: str, *, mode: str, uid_type: str, timeout: float):
        turn_id = new_uid("TURN", uid_type)
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[turn_id] = future
        self._modes[turn_id] = mode

        await self.broadcaster.send_trigger(
            target_uid=ARCHIVIST_UID,
            action_to_trigger="RETRIEVE_CONTEXT",
            parameters={"question": request, "turn_id": turn_id, "mode": mode},
        )
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop(turn_id, None)
            self._modes.pop(turn_id, None)

    async def handle_action(
        self, action: str, data: dict[str, Any], message: SynapseMessage
    ) -> None:
        if action == "RELEASE_ANSWER":
            subject = self._assets.get(data["data_asset_uid"])
            if isinstance(subject, CreativeAsset):
                self._resolve(
                    subject.turn_id,
                    CreativeResult(
                        request=subject.request,
                        approved=True,
                        title=subject.title,
                        asset=subject,
                        sources=list(subject.sources),
                        confidence=subject.confidence.score,
                        turn_id=subject.turn_id,
                    ),
                )
            else:  # AnswerAsset — the Q&A path
                self._resolve(
                    subject.turn_id,
                    QAResult(
                        question=subject.question,
                        answer=subject.answer.text,
                        approved=True,
                        sources=list(subject.sources),
                        confidence=subject.confidence.score,
                        turn_id=subject.turn_id,
                    ),
                )
        elif action == "HANDLE_VETO":
            report: SdrEthicalAnalysisReport = self._assets.get(data["data_asset_uid"])
            top = report.violations[0] if report.violations else None
            reason = report.reasoning.text
            directive = top.directive_name if top else None
            if self._modes.get(report.turn_id) == "creative":
                self._resolve(
                    report.turn_id,
                    CreativeResult(
                        request="",
                        approved=False,
                        directive=directive,
                        reason=reason,
                        report_uid=report.synapse_uid,
                        turn_id=report.turn_id,
                    ),
                )
            else:
                self._resolve(
                    report.turn_id,
                    QAResult(
                        question="",  # the question isn't echoed in the report
                        answer=(
                            "⛔ This response was withheld by the Philosopher because it would "
                            f"violate a Prime Directive ({directive or 'unknown'})."
                        ),
                        approved=False,
                        directive=directive,
                        reason=reason,
                        report_uid=report.synapse_uid,
                        turn_id=report.turn_id,
                    ),
                )

    def _resolve(self, turn_id: str, result: QAResult) -> None:
        future = self._pending.get(turn_id)
        if future is not None and not future.done():
            future.set_result(result)
