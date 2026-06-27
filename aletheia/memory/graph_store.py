"""The ``GraphStore`` interface + a NetworkX implementation (Milestone 4).

The Archivist's grounded memory has two halves: vectors (fuzzy similarity, the
``VectorStore``) and a **knowledge graph** of typed entities and the relations
between them. The graph is the neuro-symbolic, anti-hallucination core of the
whole thesis — facts the system can *traverse* and *cite*, not just passages it
found nearby.

As with every other dependency in Aletheia, the agent depends only on the
``GraphStore`` interface (CLAUDE.md §10). Milestone 4 ships an in-process
``NetworkXGraphStore``; a server-backed graph (Neo4j / embedded Kùzu) can drop in
later behind the same interface without touching the Archivist.

Every relation is a :class:`GraphFact` that keeps its ``source`` and the
``evidence`` sentence it was parsed from — so any answer built from the graph is
traceable to a citation, which is the point of the Glass Box.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

_WORD_RE = re.compile(r"[a-z0-9]+")
# Tokens too generic to identify an entity by (so "the system" doesn't match
# every node). Kept tiny on purpose — this is a stop-list, not NLP.
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "of", "to", "and", "or", "is", "are", "was", "were",
        "it", "its", "this", "that", "these", "those", "what", "which", "who",
        "does", "do", "did", "how", "for", "in", "on", "by", "with", "as",
        "system", "data", "thing",
    }
)


def normalize(name: str) -> str:
    """Canonical key for an entity: lowercase, collapsed whitespace."""
    return " ".join(_WORD_RE.findall(name.lower()))


def _content_tokens(text: str) -> set[str]:
    return {t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS}


@dataclass(frozen=True)
class GraphFact:
    """A directed relation: ``subject --predicate--> object``, with provenance."""

    subject: str
    predicate: str
    object: str
    source: str  # the document/section the fact came from
    evidence: str  # the sentence it was parsed from (the receipt)
    confidence: float = 1.0  # deterministic parse → high certainty by default


@dataclass
class GraphEntity:
    """A node: a named entity, its type, and the sources that mention it."""

    name: str
    entity_type: str = "CONCEPT"
    sources: set[str] = field(default_factory=set)


class GraphStore(ABC):
    @abstractmethod
    def add_entity(self, name: str, *, entity_type: str = "CONCEPT", source: str = "") -> None:
        ...

    @abstractmethod
    def add_fact(self, fact: GraphFact) -> None:
        ...

    @abstractmethod
    def find_entities(self, query: str) -> list[GraphEntity]:
        """Entities whose name overlaps the query's content words, best first."""

    @abstractmethod
    def facts_with_subject(self, name: str) -> list[GraphFact]:
        """Outgoing relations whose subject matches ``name``."""

    @abstractmethod
    def facts_about(self, name: str) -> list[GraphFact]:
        """Relations where ``name`` is either the subject or the object."""

    @abstractmethod
    def find_facts(self, query: str, *, limit: int = 6) -> list[GraphFact]:
        """Facts most relevant to a (relational) question, best first.

        Scores each fact by how well it matches the question — the relation
        (predicate) it asks about counts double, the entity (subject/object) it
        names counts once — so "what does X *enforce*?" lands on the *enforce*
        relation about X even when X sits inside a longer subject phrase.
        """

    @property
    @abstractmethod
    def num_entities(self) -> int:
        ...

    @property
    @abstractmethod
    def num_facts(self) -> int:
        ...


class NetworkXGraphStore(GraphStore):
    """An in-process knowledge graph over a NetworkX directed multigraph.

    Nodes are entities (keyed by their normalized name); edges are facts, each
    carrying its predicate, source, evidence sentence, and confidence. NetworkX
    is a pure-Python dependency — no server, no native build — so the graph runs
    anywhere ``python main.py`` does.
    """

    def __init__(self) -> None:
        import networkx as nx  # local import: keeps the dep optional at import time

        self._g = nx.MultiDiGraph()
        self._fact_keys: set[tuple[str, str, str, str]] = set()  # de-dup identical facts

    # --- ingestion --------------------------------------------------------- #
    def add_entity(self, name: str, *, entity_type: str = "CONCEPT", source: str = "") -> None:
        key = normalize(name)
        if not key:
            return
        if self._g.has_node(key):
            node = self._g.nodes[key]
            node["sources"].add(source) if source else None
            # Prefer a more specific type than the default if one arrives.
            if node.get("entity_type", "CONCEPT") == "CONCEPT" and entity_type != "CONCEPT":
                node["entity_type"] = entity_type
        else:
            self._g.add_node(
                key,
                display=name.strip(),
                entity_type=entity_type,
                sources={source} if source else set(),
            )

    def add_fact(self, fact: GraphFact) -> None:
        subj_key, obj_key = normalize(fact.subject), normalize(fact.object)
        if not subj_key or not obj_key:
            return
        self.add_entity(fact.subject, source=fact.source)
        self.add_entity(fact.object, source=fact.source)
        dedup = (subj_key, normalize(fact.predicate), obj_key, fact.source)
        if dedup in self._fact_keys:
            return
        self._fact_keys.add(dedup)
        self._g.add_edge(
            subj_key,
            obj_key,
            predicate=fact.predicate,
            source=fact.source,
            evidence=fact.evidence,
            confidence=fact.confidence,
        )

    # --- retrieval --------------------------------------------------------- #
    def find_entities(self, query: str) -> list[GraphEntity]:
        q_tokens = _content_tokens(query)
        if not q_tokens:
            return []
        scored: list[tuple[float, int, int, GraphEntity]] = []
        for key, attrs in self._g.nodes(data=True):
            name_tokens = _content_tokens(attrs.get("display", key))
            if not name_tokens:
                continue
            overlap = len(name_tokens & q_tokens)
            if overlap == 0:
                continue
            entity = GraphEntity(
                name=attrs.get("display", key),
                entity_type=attrs.get("entity_type", "CONCEPT"),
                sources=set(attrs.get("sources", set())),
            )
            # Rank by *precision* first — what fraction of the entity's own name
            # the query covers — so a tight "Philosopher" beats a sprawling noun
            # chunk that merely happens to contain the word. Then more overlap,
            # then the shorter name.
            precision = overlap / len(name_tokens)
            scored.append((precision, overlap, -len(name_tokens), entity))
        scored.sort(key=lambda s: (s[0], s[1], s[2]), reverse=True)
        return [s[3] for s in scored]

    def facts_with_subject(self, name: str) -> list[GraphFact]:
        key = normalize(name)
        if not self._g.has_node(key):
            return []
        out: list[GraphFact] = []
        for _, obj_key, data in self._g.out_edges(key, data=True):
            out.append(self._to_fact(key, obj_key, data))
        return out

    def facts_about(self, name: str) -> list[GraphFact]:
        key = normalize(name)
        if not self._g.has_node(key):
            return []
        out: list[GraphFact] = []
        for _, obj_key, data in self._g.out_edges(key, data=True):
            out.append(self._to_fact(key, obj_key, data))
        for subj_key, _, data in self._g.in_edges(key, data=True):
            out.append(self._to_fact(subj_key, key, data))
        return out

    def find_facts(self, query: str, *, limit: int = 6) -> list[GraphFact]:
        q_tokens = _content_tokens(query)
        if not q_tokens:
            return []
        scored: list[tuple[int, int, GraphFact]] = []
        for subj_key, obj_key, data in self._g.edges(data=True):
            subj_disp = self._g.nodes[subj_key].get("display", subj_key)
            obj_disp = self._g.nodes[obj_key].get("display", obj_key)
            entity_overlap = len(
                (_content_tokens(subj_disp) | _content_tokens(obj_disp)) & q_tokens
            )
            if entity_overlap == 0:
                continue  # the fact must mention something the question named
            pred_overlap = len(_content_tokens(data["predicate"]) & q_tokens)
            score = pred_overlap * 2 + entity_overlap
            # Tiebreak toward tighter subjects (a cleaner, more precise fact).
            scored.append((score, -len(_content_tokens(subj_disp)), self._to_fact(subj_key, obj_key, data)))
        scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
        return [fact for _, _, fact in scored[:limit]]

    def _to_fact(self, subj_key: str, obj_key: str, data: dict) -> GraphFact:
        return GraphFact(
            subject=self._g.nodes[subj_key].get("display", subj_key),
            predicate=data["predicate"],
            object=self._g.nodes[obj_key].get("display", obj_key),
            source=data.get("source", ""),
            evidence=data.get("evidence", ""),
            confidence=data.get("confidence", 1.0),
        )

    # --- stats ------------------------------------------------------------- #
    @property
    def num_entities(self) -> int:
        return self._g.number_of_nodes()

    @property
    def num_facts(self) -> int:
        return self._g.number_of_edges()


def get_default_graph_store() -> GraphStore | None:
    """A NetworkX graph store, or ``None`` if NetworkX isn't installed.

    Returning ``None`` lets the Archivist run vector-only (no graph) rather than
    crash — the same graceful-degradation posture as the LLM provider.
    """
    try:
        return NetworkXGraphStore()
    except Exception as exc:  # noqa: BLE001 — NetworkX missing
        print(
            f"[aletheia] knowledge graph unavailable ({type(exc).__name__}); "
            "Archivist running vector-only (install networkx for the graph)."
        )
        return None
