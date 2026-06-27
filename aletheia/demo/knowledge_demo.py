"""Milestone 4 proof: grounded memory — the knowledge-graph Archivist.

Shows the neuro-symbolic core in action: Aletheia ingests its own design docs,
the Archivist deterministically parses them (spaCy) into a knowledge graph of
entities + relations, and a **relational** question is answered by *traversing*
that graph — with every fact traceable to the document it came from.

For each question we print:
  1. the facts the Archivist retrieved by graph traversal (subject–predicate–
     object), each with its source and the evidence sentence it was parsed from;
  2. the answer the cascade returns (Claude if a key is set, else a grounded
     offline answer built straight from those facts — "grounded memory, not
     vector vibes").

Run with ``python main.py --knowledge`` (or ``python -m
aletheia.demo.knowledge_demo``).
"""

from __future__ import annotations

import asyncio

from aletheia.app.qa_system import QASystem
from aletheia.log.cascade_log import CascadeLog

_QUESTIONS = [
    "What does the Philosopher enforce?",
    "What does the Diagnostician monitor?",
    "What does the Archivist build?",
]


async def run() -> QASystem:
    system = QASystem(cascade_log=CascadeLog(path=None))
    n = system.ingest_own_docs()

    print("\n=== Milestone 4 — Ground Truth (the knowledge-graph Archivist) ===")
    print(f"\nIngested {n} passages from Aletheia's own docs.")
    if system.graph is None:
        print("  (knowledge graph unavailable — install networkx + en_core_web_sm)")
        return system
    print(
        f"Archivist extractor : {system.extractor.name}"
        if system.extractor
        else "Archivist extractor : none"
    )
    print(
        f"Knowledge graph     : {system.graph.num_entities} entities, "
        f"{system.graph.num_facts} facts (each with a source)."
    )
    print(f"Narrator brain      : {system.llm.name}\n")

    for question in _QUESTIONS:
        print("─" * 78)
        print(f"Q: {question}")
        # 1) The graph traversal itself — the facts, with provenance + evidence.
        facts = system.graph.find_facts(question, limit=3)
        print("  graph traversal → facts (each traceable to a source):")
        for f in facts:
            print(f"    • {f.subject} —[{f.predicate}]→ {f.object}")
            print(f"        source: {f.source}")
            print(f'        evidence: "{_trim(f.evidence)}"')
        # 2) The synthesized, safety-checked answer from the full cascade.
        result = await system.ask(question)
        verdict = "✓ approved" if result.approved else f"⛔ vetoed ({result.directive})"
        print(f"  answer [{verdict}]:\n    {result.answer.strip()}\n")

    return system


def _trim(text: str, limit: int = 110) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def main() -> None:
    asyncio.run(run())
    print("─" * 78)
    print(
        "Every fact above was parsed deterministically from the docs and carries "
        "its source — the anti-hallucination core of the design.\n"
    )


if __name__ == "__main__":
    main()
