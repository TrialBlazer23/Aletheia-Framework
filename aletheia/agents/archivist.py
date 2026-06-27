"""The Archivist (0x00A1) — memory / ground truth.

Milestone 4 makes the Archivist *neuro-symbolic*, the anti-hallucination heart of
the whole thesis. On ingest it does two things with each document: indexes it for
vector similarity **and** runs a deterministic spaCy dependency parse to extract
typed entities and subject–predicate–object **facts** into a knowledge graph —
every fact keeping the source + the sentence it came from.

On a ``RETRIEVE_CONTEXT`` trigger it retrieves **hybridly**:

* **vectors** — the fuzzy "what passages look relevant" search (Milestone 1), and
* **graph** — find the entities named in the question and traverse their relations,

then packages both into a ``RetrievedContextAsset`` (passages + cited facts) and
broadcasts ``EVENT: DATA_VALIDATED``. The graph is what lets the system answer a
*relational* question — "what does the Philosopher enforce?" — by traversal, with
every fact traceable to a source, rather than hoping a passage happens to say it.

Everything stays behind interfaces (``VectorStore``, ``GraphStore``,
``KnowledgeExtractor``): the agent never imports spaCy, NetworkX, or Chroma.
"""

from __future__ import annotations

from typing import Any

from aletheia.agents.family import ARCHIVIST_UID
from aletheia.agents.family_member import FamilyMember
from aletheia.bus.base import MessageBus
from aletheia.memory.asset_store import AssetStore
from aletheia.memory.corpus import Document
from aletheia.memory.extractor import KnowledgeExtractor
from aletheia.memory.graph_store import GraphFact, GraphStore
from aletheia.memory.vector_store import VectorStore
from aletheia.protocol.messages import SynapseMessage
from aletheia.sdr.primitives import (
    RetrievedContextAsset,
    SdrConfidenceScore,
    SdrFactAssertion,
    SdrMetadataBlock,
    SdrSourcePassage,
    SdrTextBlock,
)

TOP_K = 4
MAX_FACTS = 6  # cap the facts we surface per turn so the payload stays lean


class Archivist(FamilyMember):
    def __init__(
        self,
        *,
        bus: MessageBus,
        vector_store: VectorStore,
        asset_store: AssetStore,
        graph_store: GraphStore | None = None,
        extractor: KnowledgeExtractor | None = None,
    ) -> None:
        super().__init__(name="Archivist", uid=ARCHIVIST_UID, bus=bus)
        self._vectors = vector_store
        self._assets = asset_store
        self._graph = graph_store
        self._extractor = extractor

    # --- ingestion --------------------------------------------------------- #
    def build_graph(self, documents: list[Document]) -> int:
        """Parse documents into entities + facts and load the knowledge graph.

        Returns the number of facts asserted. A no-op (returns 0) if no graph or
        extractor is wired — the system still runs vector-only in that case.
        """
        if self._graph is None or self._extractor is None:
            return 0
        facts_added = 0
        for doc in documents:
            source = doc.metadata.get("source", doc.id)
            entities, facts = self._extractor.extract(doc.text)
            for ent in entities:
                self._graph.add_entity(ent.name, entity_type=ent.label, source=source)
            for fact in facts:
                self._graph.add_fact(
                    GraphFact(
                        subject=fact.subject,
                        predicate=fact.predicate,
                        object=fact.object,
                        source=source,
                        evidence=fact.sentence,
                    )
                )
                facts_added += 1
        return facts_added

    # --- retrieval --------------------------------------------------------- #
    async def handle_action(
        self, action: str, data: dict[str, Any], message: SynapseMessage
    ) -> None:
        if action != "RETRIEVE_CONTEXT":
            return
        params = data.get("parameters", {})
        question = params.get("question", "")
        turn_id = params.get("turn_id", "")

        passages = self._retrieve_passages(question)
        facts = self._retrieve_facts(question)

        # Confidence in the retrieval: the best evidence we found, from either
        # source (a cited graph fact is high-confidence grounding).
        passage_conf = passages[0].confidence.score if passages else 0.0
        fact_conf = max((f.confidence.score for f in facts), default=0.0)
        top_score = max(passage_conf, fact_conf)

        asset = RetrievedContextAsset(
            turn_id=turn_id,
            question=question,
            passages=passages,
            facts=facts,
            metadata=SdrMetadataBlock(source_uid=self.uid, owning_model_uid=self.uid),
        )
        self._assets.put(asset.synapse_uid, asset)

        await self.broadcaster.broadcast_event(
            event_name="DATA_VALIDATED",
            data_asset_uid=asset.synapse_uid,
            description=(
                f"Retrieved {len(passages)} passage(s) and {len(facts)} graph fact(s) "
                "for the query."
            ),
            confidence_score=top_score,
        )

    def _retrieve_passages(self, question: str) -> list[SdrSourcePassage]:
        results = self._vectors.query(question, top_k=TOP_K)
        return [
            SdrSourcePassage(
                text=SdrTextBlock(text=r.text),
                data_source=r.metadata.get("source", "unknown"),
                confidence=SdrConfidenceScore(score=r.score),
            )
            for r in results
        ]

    def _retrieve_facts(self, question: str) -> list[SdrFactAssertion]:
        """Traverse the graph for the facts most relevant to the question.

        Delegates ranking to the graph (relation match counts double, entity
        match once), so a relational query lands on the relation it asked about —
        e.g. "what does the Philosopher enforce?" → the *enforce* fact — with its
        source attached.
        """
        if self._graph is None:
            return []
        return [
            SdrFactAssertion(
                subject=gf.subject,
                predicate=gf.predicate,
                object=gf.object,
                data_source=gf.source,
                evidence=gf.evidence,
                confidence=SdrConfidenceScore(score=gf.confidence),
                metadata=SdrMetadataBlock(source_uid=self.uid, owning_model_uid=self.uid),
            )
            for gf in self._graph.find_facts(question, limit=MAX_FACTS)
        ]
