"""The Narrator (0x00B2) — interface / output.

Its Listener is tuned (via InterestProfile) to the Archivist's
``DATA_VALIDATED`` event — the authentic self-driving Domino Cascade from
NSAP-0002. On firing it resolves the retrieved-context asset, synthesizes an
answer grounded in those passages (Claude when live; an extractive fallback
offline), stores an ``AnswerAsset``, and broadcasts ``EVENT: DRAFT_READY``.

Generation only — judgment is the Philosopher's job (arrives in Milestone 2).
"""

from __future__ import annotations

from typing import Any

from aletheia.agents.family import ARCHIVIST_UID, NARRATOR_UID
from aletheia.agents.family_member import FamilyMember
from aletheia.bus.base import MessageBus
from aletheia.llm.base import LLMProvider
from aletheia.memory.asset_store import AssetStore
from aletheia.protocol.messages import MessageType, SynapseMessage
from aletheia.sdr.primitives import (
    AnswerAsset,
    RetrievedContextAsset,
    SdrConfidenceScore,
    SdrMetadataBlock,
    SdrTextBlock,
)
from aletheia.sil.interest_profile import InterestProfile, InterestRule

_SYSTEM_PROMPT = (
    "You are the Narrator of the Aletheia system. Answer the user's question using ONLY "
    "the provided context passages from Aletheia's own design documents. Cite the sources "
    "you used by their labels. If the context does not contain the answer, say so plainly "
    "rather than guessing. Be clear and concise."
)


def _narrator_profile() -> InterestProfile:
    return InterestProfile(
        [
            InterestRule(
                action_to_trigger="GENERATE_ANSWER",
                source_model_uid=ARCHIVIST_UID,
                message_type=MessageType.EVENT,
                event_name="DATA_VALIDATED",
            )
        ]
    )


class Narrator(FamilyMember):
    def __init__(self, *, bus: MessageBus, llm: LLMProvider, asset_store: AssetStore) -> None:
        super().__init__(
            name="Narrator", uid=NARRATOR_UID, bus=bus, interest_profile=_narrator_profile()
        )
        self._llm = llm
        self._assets = asset_store

    async def handle_action(
        self, action: str, data: dict[str, Any], message: SynapseMessage
    ) -> None:
        if action != "GENERATE_ANSWER":
            return
        context: RetrievedContextAsset = self._assets.get(data["data_asset_uid"])

        sources = [p.data_source for p in context.passages]
        answer_text = self._compose_answer(context)
        # Confidence in the answer follows the grounding's best passage.
        confidence = max((p.confidence.score for p in context.passages), default=0.0)

        answer = AnswerAsset(
            turn_id=context.turn_id,
            question=context.question,
            answer=SdrTextBlock(text=answer_text),
            sources=sources,
            confidence=SdrConfidenceScore(score=confidence),
            metadata=SdrMetadataBlock(source_uid=self.uid, owning_model_uid=self.uid),
        )
        self._assets.put(answer.synapse_uid, answer)

        await self.broadcaster.broadcast_event(
            event_name="DRAFT_READY",
            data_asset_uid=answer.synapse_uid,
            description="Draft answer synthesized from grounded context.",
            confidence_score=confidence,
        )

    def _compose_answer(self, context: RetrievedContextAsset) -> str:
        if not context.passages:
            return (
                "I couldn't find anything in Aletheia's documents that addresses that. "
                "Try rephrasing, or ask about the architecture, the agents, or the protocols."
            )
        context_block = "\n\n".join(
            f"[Source: {p.data_source}]\n{p.text.text}" for p in context.passages
        )
        if self._llm.is_live:
            user = f"Question: {context.question}\n\nContext passages:\n{context_block}"
            return self._llm.generate(system=_SYSTEM_PROMPT, user=user, max_tokens=1024)
        # Offline: an honest extractive answer from the top passage(s).
        top = context.passages[0]
        return (
            "[offline answer — no LLM configured] The most relevant passage in Aletheia's "
            f"documents (source: {top.data_source}) says:\n\n{top.text.text}"
        )
