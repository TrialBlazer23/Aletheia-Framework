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
    ConceptAsset,
    RetrievedContextAsset,
    SdrConfidenceScore,
    SdrMetadataBlock,
    SdrTextBlock,
)
from aletheia.sil.interest_profile import InterestProfile, InterestRule

_SYSTEM_PROMPT = (
    "You are the Narrator of the Aletheia system. Answer the user's question using ONLY "
    "the provided context — grounded facts from Aletheia's knowledge graph and passages "
    "from its design documents. Prefer the graph facts for relational questions (who does "
    "what). Cite the sources you used by their labels. If the context does not contain the "
    "answer, say so plainly rather than guessing. Be clear and concise."
)

_CONCEPT_PROMPT = (
    "You are the Narrator of the Aletheia system. Develop a vivid, original creative "
    "concept for the request below, *grounded in and consistent with* the provided context "
    "about Aletheia's world (treat it as canon — don't contradict it). Write 3-5 evocative "
    "sentences describing the concept (form, character, atmosphere). Generation only: do not "
    "judge or caveat — that is another agent's job."
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

        # Sources span both grounding channels: passages and cited graph facts.
        sources = [p.data_source for p in context.passages]
        sources += [f.data_source for f in context.facts]
        sources = list(dict.fromkeys(s for s in sources if s))  # dedupe, keep order

        # Creative cascade: the Narrator generates a *concept* (grounded in canon),
        # which the Visionary turns into design assets. Same retrieval, different
        # output and a different downstream event.
        if context.mode == "creative":
            await self._emit_concept(context, sources)
            return

        answer_text = self._compose_answer(context)
        # Confidence follows the best grounding we have, from either channel.
        confidence = max(
            [p.confidence.score for p in context.passages]
            + [f.confidence.score for f in context.facts],
            default=0.0,
        )

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

    # --- the creative path ------------------------------------------------- #
    async def _emit_concept(self, context: RetrievedContextAsset, sources: list[str]) -> None:
        confidence = max(
            [p.confidence.score for p in context.passages]
            + [f.confidence.score for f in context.facts],
            default=0.5,  # a creative concept isn't gated by retrieval strength
        )
        concept = ConceptAsset(
            turn_id=context.turn_id,
            request=context.question,
            concept=SdrTextBlock(text=self._compose_concept(context)),
            sources=sources,
            confidence=SdrConfidenceScore(score=max(confidence, 0.5)),
            metadata=SdrMetadataBlock(source_uid=self.uid, owning_model_uid=self.uid),
        )
        self._assets.put(concept.synapse_uid, concept)
        await self.broadcaster.broadcast_event(
            event_name="CONCEPT_READY",
            data_asset_uid=concept.synapse_uid,
            description="Creative concept synthesized from grounded context.",
            confidence_score=concept.confidence.score,
        )

    def _compose_concept(self, context: RetrievedContextAsset) -> str:
        if self._llm.is_live:
            try:
                user = f"Creative request: {context.question}\n\n{self._context_block(context)}"
                text = self._llm.generate(system=_CONCEPT_PROMPT, user=user, max_tokens=512)
                if text.strip():
                    return text.strip()
            except Exception as exc:  # noqa: BLE001 — degrade, never hang the cascade
                print(
                    f"[aletheia] Narrator: live concept generation failed "
                    f"({type(exc).__name__}); using a grounded template concept."
                )
        return self._template_concept(context)

    @staticmethod
    def _template_concept(context: RetrievedContextAsset) -> str:
        """A deterministic, grounded concept when no live model is available."""
        anchor = ""
        if context.facts:
            f = context.facts[0]
            anchor = f" It stays consistent with Aletheia's canon, where {f.subject} {f.predicate} {f.object} (source: {f.data_source})."
        elif context.passages:
            anchor = f" It draws on Aletheia's documented world (source: {context.passages[0].data_source})."
        return (
            f"[offline concept] A grounded creative concept for: \"{context.question}\". "
            "Envisioned to embody Aletheia's core theme of un-concealment — truth brought to "
            "light — rendered with deliberate form, atmosphere, and symbolic clarity." + anchor
        )

    def _compose_answer(self, context: RetrievedContextAsset) -> str:
        if not context.passages and not context.facts:
            return (
                "I couldn't find anything in Aletheia's documents that addresses that. "
                "Try rephrasing, or ask about the architecture, the agents, or the protocols."
            )
        if self._llm.is_live:
            user = f"Question: {context.question}\n\n{self._context_block(context)}"
            try:
                return self._llm.generate(system=_SYSTEM_PROMPT, user=user, max_tokens=1024)
            except Exception as exc:  # noqa: BLE001 — degrade, never hang the cascade
                # A live model failure (no credits, bad key, network) must not stall
                # the whole turn. Fall back to a grounded extractive answer.
                print(
                    f"[aletheia] Narrator: live model call failed ({type(exc).__name__}); "
                    "falling back to a grounded extract."
                )
                return self._extractive(context, live_failed=True)
        return self._extractive(context)

    @staticmethod
    def _context_block(context: RetrievedContextAsset) -> str:
        parts: list[str] = []
        if context.facts:
            facts = "\n".join(
                f"- {f.subject} {f.predicate} {f.object}. [Source: {f.data_source}]"
                for f in context.facts
            )
            parts.append(f"Knowledge-graph facts:\n{facts}")
        if context.passages:
            passages = "\n\n".join(
                f"[Source: {p.data_source}]\n{p.text.text}" for p in context.passages
            )
            parts.append(f"Document passages:\n{passages}")
        return "\n\n".join(parts)

    @staticmethod
    def _extractive(context: RetrievedContextAsset, *, live_failed: bool = False) -> str:
        """An honest answer built directly from the grounded evidence.

        Graph facts come first: even with no LLM, a traversed + cited fact is a
        real relational answer ("grounded memory, not vector vibes"). If there are
        no facts, fall back to the top retrieved passage.
        """
        prefix = (
            "[grounded extract — the live model was unavailable]"
            if live_failed
            else "[offline answer — no LLM configured]"
        )
        if context.facts:
            lines = [
                f"{f.subject} {f.predicate} {f.object} (source: {f.data_source})."
                for f in context.facts[:3]
            ]
            return (
                f"{prefix} From Aletheia's knowledge graph:\n\n" + "\n".join(lines)
            )
        top = context.passages[0]
        return (
            f"{prefix} The most relevant passage in Aletheia's documents "
            f"(source: {top.data_source}) says:\n\n{top.text.text}"
        )
