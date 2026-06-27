"""Milestone 4: the knowledge-graph Archivist (grounded, neuro-symbolic memory).

We prove the anti-hallucination core: documents are parsed into a graph of
entities + relations, a *relational* question is answered by traversing that
graph, and every fact carries the source it was parsed from.

The graph-store and ranking tests are deterministic (they build facts directly).
The extraction tests use whichever extractor is installed; the clean
subject–verb–object sentence is handled by both spaCy and the rule-based floor.
"""

import asyncio

import pytest

from aletheia.agents.family import ARCHIVIST_UID
from aletheia.app.qa_system import QASystem
from aletheia.llm.offline_provider import OfflineProvider
from aletheia.log.cascade_log import CascadeLog
from aletheia.memory.corpus import Document
from aletheia.memory.extractor import RuleBasedExtractor, get_default_extractor
from aletheia.memory.graph_store import (
    GraphFact,
    NetworkXGraphStore,
    get_default_graph_store,
    normalize,
)
from aletheia.sdr.primitives import SdrFactAssertion, SdrKnowledgeGraphElement


# --------------------------------------------------------------------------- #
# The graph store (deterministic — no spaCy needed)
# --------------------------------------------------------------------------- #
def _loaded_graph() -> NetworkXGraphStore:
    g = NetworkXGraphStore()
    g.add_fact(GraphFact("Philosopher", "enforce", "Prime Directives", "CLAUDE.md", "ev1"))
    g.add_fact(GraphFact("Archivist", "build", "knowledge graph", "CLAUDE.md", "ev2"))
    g.add_fact(GraphFact("Diagnostician", "monitor", "the bus", "CLAUDE.md", "ev3"))
    g.add_fact(GraphFact("Philosopher", "validate", "outputs", "ANALYSIS.md", "ev4"))
    return g


def test_graph_stores_entities_and_facts():
    g = _loaded_graph()
    assert g.num_facts == 4
    # subject + object of each distinct fact become entities
    assert g.num_entities >= 5


def test_graph_dedupes_identical_facts_from_the_same_source():
    g = NetworkXGraphStore()
    f = GraphFact("Philosopher", "enforce", "Prime Directives", "CLAUDE.md", "ev")
    g.add_fact(f)
    g.add_fact(f)  # identical (same source) — must not double up
    assert g.num_facts == 1


def test_same_fact_from_two_sources_is_kept_for_corroboration():
    g = NetworkXGraphStore()
    g.add_fact(GraphFact("Philosopher", "enforce", "Prime Directives", "CLAUDE.md", "a"))
    g.add_fact(GraphFact("Philosopher", "enforce", "Prime Directives", "ROADMAP.md", "b"))
    assert g.num_facts == 2  # corroborating evidence from two docs


def test_facts_with_subject_traverses_outgoing_relations():
    g = _loaded_graph()
    facts = g.facts_with_subject("Philosopher")
    rels = {(f.predicate, f.object) for f in facts}
    assert ("enforce", "Prime Directives") in rels
    assert ("validate", "outputs") in rels


def test_find_entities_prefers_precise_names():
    g = NetworkXGraphStore()
    g.add_entity("Philosopher")
    g.add_entity("Philosopher safety kernel guidance notes")  # noisy long name
    hits = g.find_entities("What does the Philosopher enforce?")
    assert hits[0].name == "Philosopher"  # the tight match wins on precision


def test_find_facts_lands_on_the_asked_relation():
    """The crux of M4: a relational query returns the relation it asked about."""
    g = _loaded_graph()
    facts = g.find_facts("What does the Philosopher enforce?", limit=3)
    top = facts[0]
    assert top.subject == "Philosopher"
    assert top.predicate == "enforce"
    assert top.object == "Prime Directives"
    assert top.source == "CLAUDE.md"  # every fact is traceable to a source


def test_find_facts_requires_the_question_to_name_the_entity():
    g = _loaded_graph()
    # Nothing about "weather" is in the graph.
    assert g.find_facts("What is the weather today?") == []


def test_normalize_is_case_and_whitespace_insensitive():
    assert normalize("  The   PHILOSOPHER ") == "the philosopher"


# --------------------------------------------------------------------------- #
# Extraction (deterministic spaCy parse, with a rule-based floor)
# --------------------------------------------------------------------------- #
def test_extractor_pulls_a_subject_verb_object_fact():
    ext = get_default_extractor()
    _, facts = ext.extract("The Philosopher enforces the Prime Directives.")
    triples = {(f.subject.lower().replace("the ", ""), f.predicate, f.object.lower()) for f in facts}
    assert ("philosopher", "enforce", "prime directives") in triples


def test_rule_based_extractor_is_a_working_floor():
    ext = RuleBasedExtractor()
    _, facts = ext.extract("The Diagnostician monitors the bus.")
    assert any(f.predicate == "monitor" and "bus" in f.object.lower() for f in facts)


def test_extractor_rejects_markdown_junk_objects():
    """spaCy path: a table/markup-laden 'sentence' must not yield junk facts."""
    ext = get_default_extractor()
    if isinstance(ext, RuleBasedExtractor):
        pytest.skip("junk filtering is the spaCy path")
    _, facts = ext.extract("| The Philosopher | enforces | **the** `Prime` | Directives |")
    assert all("|" not in f.object and "*" not in f.object for f in facts)


# --------------------------------------------------------------------------- #
# The Archivist v2 — hybrid retrieval over a live cascade
# --------------------------------------------------------------------------- #
def _qa_offline(docs: list[Document]) -> QASystem:
    system = QASystem(llm=OfflineProvider(), cascade_log=CascadeLog(path=None))
    system.ingest(docs)
    return system


def test_ingest_builds_the_knowledge_graph():
    if get_default_graph_store() is None:
        pytest.skip("networkx not installed")
    system = _qa_offline(
        [Document(id="d", text="The Philosopher enforces the Prime Directives.", metadata={"source": "CLAUDE.md"})]
    )
    assert system.graph is not None
    assert system.graph.num_facts >= 1


def test_relational_question_answered_by_graph_traversal_with_a_source():
    """The Milestone 4 'Done when': answer a relational question from the graph,
    every fact traceable to a source — even with no LLM."""
    if get_default_graph_store() is None:
        pytest.skip("networkx not installed")
    system = _qa_offline(
        [
            Document(
                id="d",
                text="The Philosopher enforces the Prime Directives.",
                metadata={"source": "CLAUDE.md"},
            )
        ]
    )
    result = asyncio.run(system.ask("What does the Philosopher enforce?"))
    assert result.approved is True
    assert "Prime Directives" in result.answer
    assert "CLAUDE.md" in result.answer  # the citation travels with the answer
    assert "CLAUDE.md" in result.sources


def test_retrieved_context_carries_cited_facts():
    if get_default_graph_store() is None:
        pytest.skip("networkx not installed")
    system = _qa_offline(
        [Document(id="d", text="The Diagnostician monitors the bus.", metadata={"source": "CLAUDE.md"})]
    )
    asyncio.run(system.ask("What does the Diagnostician monitor?"))
    # The Archivist's retrieved-context asset should contain a fact with provenance.
    facts = [
        a
        for a in system.assets._assets.values()  # type: ignore[attr-defined]
        if isinstance(a, object) and hasattr(a, "facts")
    ]
    contexts = [a for a in facts if type(a).__name__ == "RetrievedContextAsset"]
    assert contexts and any(c.facts for c in contexts)
    fact = next(c.facts[0] for c in contexts if c.facts)
    assert fact.data_source == "CLAUDE.md"
    assert fact.evidence  # the source sentence is retained


def test_system_runs_vector_only_when_graph_is_disabled():
    """Graceful degradation: with no graph, the system still answers (vectors)."""
    system = QASystem(llm=OfflineProvider(), cascade_log=CascadeLog(path=None), use_graph=False)
    system.ingest([Document(id="d", text="Aletheia is a neuro-symbolic system.", metadata={"source": "VISION.md"})])
    assert system.graph is None
    result = asyncio.run(system.ask("What is Aletheia?"))
    assert result.approved is True
    assert result.answer  # an answer still comes back, grounded in passages


# --------------------------------------------------------------------------- #
# SDR shapes
# --------------------------------------------------------------------------- #
def test_fact_assertion_serializes_to_canonical_sdr_names():
    from aletheia.sdr.primitives import SdrConfidenceScore, SdrMetadataBlock

    fact = SdrFactAssertion(
        subject="Philosopher",
        predicate="enforce",
        object="Prime Directives",
        data_source="CLAUDE.md",
        evidence="The Philosopher enforces the Prime Directives.",
        confidence=SdrConfidenceScore(score=1.0),
        metadata=SdrMetadataBlock(source_uid=ARCHIVIST_UID, owning_model_uid=ARCHIVIST_UID),
    )
    wire = fact.model_dump(by_alias=True)
    for key in ("Subject", "Predicate", "Object", "Data_Source", "Evidence", "Confidence"):
        assert key in wire


def test_knowledge_graph_element_shape():
    from aletheia.sdr.primitives import SdrMetadataBlock

    el = SdrKnowledgeGraphElement(
        name="Philosopher",
        entity_type="MODEL",
        sources=["CLAUDE.md"],
        metadata=SdrMetadataBlock(source_uid=ARCHIVIST_UID, owning_model_uid=ARCHIVIST_UID),
    )
    wire = el.model_dump(by_alias=True)
    assert wire["Name"] == "Philosopher" and wire["Entity_Type"] == "MODEL"
