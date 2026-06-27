"""The Aletheia Q&A console — talk to the living 3-agent cascade.

Run with ``python -m aletheia.app.console`` (or ``python main.py``). Ask
questions about Aletheia's own design; watch the answer come back grounded in
the docs, with its sources and a confidence score. Type ``/log`` to see the
Domino Cascade for the last question, ``/health`` for the Diagnostician's view
of cascade health, ``/quit`` to exit.
"""

from __future__ import annotations

import asyncio

from aletheia.app.qa_system import QASystem
from aletheia.resonance.engine import ConsoleGavel


async def _run() -> None:
    print("Booting Aletheia (Nexus-Mind → Archivist → Narrator → Philosopher) ...")
    # A real Human Gavel: a policy change proposed by the Resonance Cycle prompts
    # you at the terminal before anything is applied.
    system = QASystem(gavel=ConsoleGavel())
    n = system.ingest_own_docs()
    print(f"  · Archivist ingested {n} passages from Aletheia's own documents.")
    if system.graph is not None:
        print(
            f"  · Knowledge graph: {system.graph.num_entities} entities, "
            f"{system.graph.num_facts} facts ({system.extractor.name})."
        )
    print(f"  · Narrator brain: {system.llm.name}")
    print(
        f"  · Philosopher enforcing {len(system.philosopher.directives.directives)} "
        f"Prime Directives ({len(system.philosopher.directives.rules)} rules)."
    )
    print("  · Diagnostician monitoring the bus (loops / stalls / circuit breaker).")
    print(f"  · Resonance Cycle ready (operational_policy v{system.policy.version}).")
    print(
        "\nAsk a question about Aletheia. Commands: "
        "/log  /health  /graph  /feedback  /policy  /quit\n"
    )

    last_turn: tuple[str, str] | None = None  # (turn_id, question) of the last answer
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
        if question == "/health":
            print("Diagnostician — cascade health:")
            print(system.diagnostician.pretty_health())
            print()
            continue
        if question == "/graph":
            if system.graph is None:
                print("  (knowledge graph unavailable)\n")
                continue
            print(
                f"Knowledge graph: {system.graph.num_entities} entities, "
                f"{system.graph.num_facts} facts. Top facts for your next question "
                "are shown with sources when you ask.\n"
            )
            continue
        if question == "/policy":
            pol = system.policy.current
            print(f"operational_policy v{pol.version}")
            print(f"  distrusted sources: {pol.distrusted_sources or '(none)'}")
            if system.policy.history:
                print("  history:")
                for e in system.policy.history:
                    print(f"    {e['event']} v{e['from_version']}→v{e['to_version']}: {e['reason']}")
            print()
            continue
        if question == "/feedback":
            # Flag the last answer as incorrect and let the Resonance Cycle engage.
            if last_turn is None:
                print("  (ask a question first, then /feedback flags that answer as incorrect)\n")
                continue
            turn_id, asked = last_turn
            print("Resonance Cycle — flagging the last answer as INCORRECT ...")
            outcome = await system.submit_feedback(
                turn_id=turn_id, question=asked, rating="INCORRECT",
                note="Flagged incorrect by the operator at the console.",
            )
            print(f"  outcome: {outcome.status} — {outcome.message}")
            if outcome.rca is not None:
                print(f"  root cause: {outcome.rca.recommended_action}")
            if outcome.verification is not None:
                print(f"  verification: {outcome.verification.status} — {outcome.verification.sandbox_summary}")
            print()
            continue

        result = await system.ask(question)
        last_turn = (result.turn_id, question)

        print(f"\naletheia › {result.answer}\n")
        if result.approved:
            if result.sources:
                unique = list(dict.fromkeys(result.sources))
                print("  sources: " + "; ".join(unique))
            print(
                f"  ✓ approved by the Philosopher   confidence: {result.confidence:.2f}"
                "   (type /log to see the cascade)\n"
            )
        else:
            print(f"  ⛔ vetoed — Directive: {result.directive}")
            print(f"  reason: {result.reason}   (type /log to see the cascade)\n")

    print("Goodbye.")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
