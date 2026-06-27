"""The Aletheia Q&A console — talk to the living 3-agent cascade.

Run with ``python -m aletheia.app.console`` (or ``python main.py``). Ask
questions about Aletheia's own design; watch the answer come back grounded in
the docs, with its sources and a confidence score. Type ``/log`` to see the
Domino Cascade for the last question, ``/quit`` to exit.
"""

from __future__ import annotations

import asyncio

from aletheia.app.qa_system import QASystem


async def _run() -> None:
    print("Booting Aletheia (Milestone 1: Nexus-Mind → Archivist → Narrator) ...")
    system = QASystem()
    n = system.ingest_own_docs()
    print(f"  · Archivist ingested {n} passages from Aletheia's own documents.")
    print(f"  · Narrator brain: {system.llm.name}")
    print("\nAsk a question about Aletheia. Commands: /log  /quit\n")

    last_seq = 0
    while True:
        try:
            question = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question in ("/quit", "/exit"):
            break
        if question == "/log":
            print(system.cascade_log.pretty() or "  (cascade log is empty)")
            continue

        before = len(system.cascade_log.entries)
        answer = await system.ask(question)
        last_seq = before  # noqa: F841 — reserved for future "since last turn" view

        print(f"\naletheia › {answer.answer.text}\n")
        if answer.sources:
            unique = list(dict.fromkeys(answer.sources))
            print("  sources: " + "; ".join(unique))
        print(f"  confidence: {answer.confidence.score:.2f}   (type /log to see the cascade)\n")

    print("Goodbye.")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
