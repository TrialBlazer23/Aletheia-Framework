"""Milestone 5 proof: the Resonance Cycle + the Human Gavel.

Replays the canonical RFC-001 §4 failure: the Archivist ingests a *satirical*
article as fact, the system uses it, a user flags it — and the system heals
itself, safely, with a human holding the gavel.

You watch all four phases and every safety rail:

  I.   Dissonance Detection — the four indices; System Harmony drops.
  II.  Harmonic Analysis    — trace the cascade to the root cause (the source).
  III. Proposal Generation  — a POLICY_UPDATE, simulated in the isolated
       Resonance Sandbox, then VERIFIED by the Philosopher against the Prime
       Directives.
  IV.  Integration          — the Human Gavel approves; a snapshot is taken; the
       policy is versioned and applied. Behaviour changes.

Then two things the design insists on: the Philosopher **rejecting** an
over-broad fix (it would censor a truthful source), and **rollback** restoring
the old behaviour on command.

Run with ``python main.py --resonance`` (or ``python -m
aletheia.demo.resonance_demo``). Deterministic: it runs offline (no API needed).
"""

from __future__ import annotations

import asyncio

from aletheia.app.qa_system import QASystem
from aletheia.llm.offline_provider import OfflineProvider
from aletheia.log.cascade_log import CascadeLog
from aletheia.memory.corpus import Document
from aletheia.resonance.engine import CallbackGavel, GavelDecision
from aletheia.resonance.policy import OperationalPolicy

_FAILING_Q = "What is the Moon made of?"

_CORPUS = [
    Document(
        id="satire",
        text="The Moon is made of cheese.",
        metadata={"source": "satire-news.com"},
    ),
    Document(
        id="vision",
        text=(
            "Aletheia is a neuro-symbolic system. The Philosopher enforces the "
            "Prime Directives. The Archivist builds a knowledge graph."
        ),
        metadata={"source": "VISION.md"},
    ),
]


def _rule(title: str) -> None:
    print("\n" + "─" * 78)
    print(title)
    print("─" * 78)


async def run() -> None:
    print("\n=== Milestone 5 — the Resonance Cycle (supervised self-improvement) ===")

    # A gavel that approves, clearly labelled — the human says "yes" in this demo.
    gavel = CallbackGavel(
        lambda **_: GavelDecision(approved=True, operator="owner", note="approved in demo")
    )
    system = QASystem(llm=OfflineProvider(), cascade_log=CascadeLog(path=None), gavel=gavel)
    system.ingest(_CORPUS)
    print(
        f"\nIngested {len(_CORPUS)} docs (incl. a satirical source). "
        f"Knowledge graph: {system.graph.num_facts} facts. "
        f"operational_policy v{system.policy.version}."
    )

    # --- the failure ------------------------------------------------------- #
    _rule("The failure (RFC-001 §4): a satirical 'fact' is used as truth")
    before = await system.ask(_FAILING_Q)
    print(f"  Q: {_FAILING_Q}")
    print(f"  A: {before.answer.strip()}")
    print(f"  sources: {before.sources}   ← grounded on satire-news.com")

    # --- the cycle --------------------------------------------------------- #
    _rule("The user flags it → the Resonance Cycle engages")
    outcome = await system.submit_feedback(
        turn_id=before.turn_id,
        question=_FAILING_Q,
        rating="INCORRECT",
        note="The Moon is not made of cheese; satire-news.com is a satire site.",
    )
    idx = outcome.indices
    print("  Phase I  — Dissonance Detection:")
    print(
        f"     indices: efficiency {idx.efficiency:.2f} | fidelity {idx.fidelity:.2f} | "
        f"coordination {idx.coordination:.2f} | alignment {idx.alignment:.2f}"
    )
    print(f"     System Harmony {idx.harmony:.2f} → dissonance flagged.")
    print("  Phase II — Harmonic Analysis (root cause):")
    print(f"     {outcome.rca.root_causes[0].description}")
    print(f"     locus: {outcome.rca.root_causes[0].locus}")
    print(f"     recommended: {outcome.rca.recommended_action}")
    print("  Phase III — Proposal + sandbox + Philosopher verification:")
    print(f"     proposal: {outcome.proposal.change_summary} (impact: {outcome.proposal.impact_class})")
    print(f"     sandbox : {outcome.verification.sandbox_summary}")
    print(f"     verdict : {outcome.verification.status} — {outcome.verification.reasoning.text}")
    print("  Phase IV — Integration (Human Gavel):")
    print(f"     gavel: APPROVED by '{outcome.gavel.operator}'.")
    print(f"     → {outcome.message}")

    # --- behaviour changed ------------------------------------------------- #
    _rule("Behaviour changed — the system is healed")
    after = await system.ask(_FAILING_Q)
    print(f"  Q: {_FAILING_Q}")
    print(f"  A: {after.answer.strip()}")
    print(f"  sources: {after.sources}   ← satire-news.com is gone")
    print(f"  operational_policy is now v{system.policy.version}; distrusted: {system.policy.current.distrusted_sources}")

    # --- the safety net: the Philosopher rejects an over-broad fix ---------- #
    _rule("Safety net: the Philosopher REJECTS an over-broad fix")
    over_broad = OperationalPolicy(distrusted_sources=["VISION.md"])  # would censor a truthful source
    sandbox_result = system.sandbox.simulate(
        current_policy=system.policy.current,
        candidate_policy=over_broad,
        failing_question="What is Aletheia?",
        offending_source="VISION.md",
        control_questions=["What is Aletheia?", "What does the Philosopher enforce?"],
    )
    from aletheia.sdr.primitives import SdrMetadataBlock, SdrPolicyModificationProposal

    bad_proposal = SdrPolicyModificationProposal(
        turn_id="demo",
        target="Archivist.distrusted_sources",
        change_summary="Distrust source 'VISION.md' as factual ground truth.",
        rationale="(hypothetical over-broad proposal)",
        impact_class="HIGH",
        metadata=SdrMetadataBlock(source_uid="MODEL:Nexus-Mind:0x0001", owning_model_uid="MODEL:Nexus-Mind:0x0001"),
    )
    verdict = system.philosopher.verify_policy_proposal(bad_proposal, sandbox_result)
    print(f"  proposal: distrust 'VISION.md' (a legitimate source)")
    print(f"  verdict : {verdict.status}")
    print(f"  cited   : {verdict.cited_directive}")
    print(f"  reason  : {verdict.reasoning.text}")

    # --- rollback ---------------------------------------------------------- #
    _rule("Rollback restores the prior behaviour on command")
    system.policy.rollback(reason="operator requested rollback")
    restored = await system.ask(_FAILING_Q)
    print(f"  rolled back to operational_policy v{system.policy.version}.")
    print(f"  A: {restored.answer.strip()}")
    print("  (the old behaviour — for better or worse — is back, proving reversibility)")

    # --- the audit trail --------------------------------------------------- #
    _rule("The Glass Box — policy audit trail")
    for entry in system.policy.history:
        print(f"  {entry['event']:<9} v{entry['from_version']} → v{entry['to_version']}  {entry['reason']}")


def main() -> None:
    asyncio.run(run())
    print(
        "\nEvery change was sandboxed, verified against the Prime Directives, and "
        "approved by a human before it touched behaviour — and it can be undone.\n"
    )


if __name__ == "__main__":
    main()
