"""The ``VectorStore`` interface + a dependency-free TF-IDF implementation.

The Archivist depends only on ``VectorStore``. Milestone 1 ships
``TfidfVectorStore`` — a pure-Python TF-IDF + cosine retriever that needs no
model download, no API, and no native deps, so the whole system runs offline on
the owner's machine. Later milestones can drop in an embedding-backed store
(Chroma, etc.) behind this same interface without touching the Archivist
(CLAUDE.md §10). Milestone 4 adds the spaCy knowledge graph alongside it.

Cosine similarity over non-negative TF-IDF vectors lands in [0, 1], which we use
directly as the retrieval confidence score.
"""

from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from aletheia.memory.corpus import Document

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class VectorQueryResult:
    text: str
    metadata: dict[str, Any]
    score: float  # 0.0–1.0 cosine similarity


class VectorStore(ABC):
    @abstractmethod
    def add_documents(self, documents: list[Document]) -> None:
        ...

    @abstractmethod
    def query(self, text: str, top_k: int = 5) -> list[VectorQueryResult]:
        ...


@dataclass
class _IndexedDoc:
    document: Document
    tf: Counter
    weights: dict[str, float] = field(default_factory=dict)
    norm: float = 0.0


class TfidfVectorStore(VectorStore):
    def __init__(self) -> None:
        self._docs: list[_IndexedDoc] = []
        self._idf: dict[str, float] = {}

    def add_documents(self, documents: list[Document]) -> None:
        for doc in documents:
            self._docs.append(_IndexedDoc(document=doc, tf=Counter(_tokenize(doc.text))))
        self._reindex()

    def _reindex(self) -> None:
        n = len(self._docs)
        if n == 0:
            return
        df: Counter = Counter()
        for d in self._docs:
            df.update(d.tf.keys())
        # Smoothed idf keeps weights positive so cosine stays in [0, 1].
        self._idf = {term: math.log((1 + n) / (1 + freq)) + 1.0 for term, freq in df.items()}
        for d in self._docs:
            d.weights = {term: count * self._idf[term] for term, count in d.tf.items()}
            d.norm = math.sqrt(sum(w * w for w in d.weights.values())) or 1.0

    def query(self, text: str, top_k: int = 5) -> list[VectorQueryResult]:
        if not self._docs:
            return []
        q_tf = Counter(_tokenize(text))
        q_weights = {t: c * self._idf.get(t, 0.0) for t, c in q_tf.items()}
        q_norm = math.sqrt(sum(w * w for w in q_weights.values())) or 1.0

        scored: list[VectorQueryResult] = []
        for d in self._docs:
            # Dot product over the smaller term set.
            terms = q_weights.keys() if len(q_weights) < len(d.weights) else d.weights.keys()
            dot = sum(q_weights.get(t, 0.0) * d.weights.get(t, 0.0) for t in terms)
            score = dot / (q_norm * d.norm)
            if score > 0.0:
                scored.append(
                    VectorQueryResult(
                        text=d.document.text,
                        metadata=dict(d.document.metadata),
                        score=round(score, 4),
                    )
                )
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]
