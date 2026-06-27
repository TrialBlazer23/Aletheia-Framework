"""The Archivist (0x00A1) — memory / ground truth.

Milestone 1 role: on a ``RETRIEVE_CONTEXT`` trigger it queries the vector store,
packages the grounded passages as a ``RetrievedContextAsset`` (stored in the
asset store, addressed by UID), and broadcasts ``EVENT: DATA_VALIDATED`` carrying
the asset pointer and a confidence score. It is the anti-hallucination anchor:
every passage keeps its source attribution.

The deterministic spaCy knowledge graph (the full neuro-symbolic Archivist)
arrives in Milestone 4; here retrieval is grounded but vector-only.
"""

from __future__ import annotations

from typing import Any

from aletheia.agents.family import ARCHIVIST_UID
from aletheia.agents.family_member import FamilyMember
from aletheia.bus.base import MessageBus
from aletheia.memory.asset_store import AssetStore
from aletheia.memory.vector_store import VectorStore
from aletheia.protocol.messages import SynapseMessage
from aletheia.sdr.primitives import (
    RetrievedContextAsset,
    SdrConfidenceScore,
    SdrMetadataBlock,
    SdrSourcePassage,
    SdrTextBlock,
)

TOP_K = 4


class Archivist(FamilyMember):
    def __init__(self, *, bus: MessageBus, vector_store: VectorStore, asset_store: AssetStore) -> None:
        super().__init__(name="Archivist", uid=ARCHIVIST_UID, bus=bus)
        self._vectors = vector_store
        self._assets = asset_store

    async def handle_action(
        self, action: str, data: dict[str, Any], message: SynapseMessage
    ) -> None:
        if action != "RETRIEVE_CONTEXT":
            return
        params = data.get("parameters", {})
        question = params.get("question", "")
        turn_id = params.get("turn_id", "")

        results = self._vectors.query(question, top_k=TOP_K)
        passages = [
            SdrSourcePassage(
                text=SdrTextBlock(text=r.text),
                data_source=r.metadata.get("source", "unknown"),
                confidence=SdrConfidenceScore(score=r.score),
            )
            for r in results
        ]
        # Confidence in the retrieval = the best passage's score (0 if nothing hit).
        top_score = results[0].score if results else 0.0

        asset = RetrievedContextAsset(
            turn_id=turn_id,
            question=question,
            passages=passages,
            metadata=SdrMetadataBlock(source_uid=self.uid, owning_model_uid=self.uid),
        )
        self._assets.put(asset.synapse_uid, asset)

        # (Step 4) broadcast the result; the Narrator's Listener is tuned to this.
        await self.broadcaster.broadcast_event(
            event_name="DATA_VALIDATED",
            data_asset_uid=asset.synapse_uid,
            description=f"Retrieved {len(passages)} grounded passage(s) for the query.",
            confidence_score=top_score,
        )
