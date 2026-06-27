"""The Resonance Sandbox — isolated simulation of a proposed policy change.

RFC-001 §3: "All simulations MUST occur in an isolated ``Resonance Sandbox`` that
mirrors production but has no external outputs." This is that sandbox.

It answers two questions about a candidate policy, *without touching the live
system*:

1. **Does the fix work?** — under the candidate policy, does the flagged content
   stop surfacing for the failing question?
2. **Is there collateral damage?** — does the candidate policy also suppress
   legitimate content for known-good ("control") questions? An over-broad fix
   that censors truthful sources violates the Sanctity of Information Flow, so
   this is exactly what the Philosopher needs to know.

The sandbox is pure: it operates through a read-only ``retrieve_sources`` probe
(candidate policy → the sources that would surface) and never mutates anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from aletheia.resonance.policy import OperationalPolicy

# probe(policy, question) -> the source labels that would ground an answer.
RetrieveProbe = Callable[[OperationalPolicy, str], list[str]]


@dataclass(frozen=True)
class SandboxResult:
    fix_effective: bool
    collateral_damage: bool
    suppressed_sources: list[str] = field(default_factory=list)
    summary: str = ""


class ResonanceSandbox:
    def __init__(self, retrieve_sources: RetrieveProbe) -> None:
        self._retrieve = retrieve_sources

    def simulate(
        self,
        *,
        current_policy: OperationalPolicy,
        candidate_policy: OperationalPolicy,
        failing_question: str,
        offending_source: str,
        control_questions: list[str] | None = None,
    ) -> SandboxResult:
        before = set(self._retrieve(current_policy, failing_question))
        after = set(self._retrieve(candidate_policy, failing_question))
        # The fix works if the offending source grounded the failing answer and
        # no longer does under the candidate policy.
        fix_effective = (offending_source in before) and (offending_source not in after)

        # Collateral check: does the candidate suppress sources that legitimate,
        # known-good questions rely on? Anything lost there is over-blocking.
        suppressed: set[str] = set()
        for question in control_questions or []:
            lost = set(self._retrieve(current_policy, question)) - set(
                self._retrieve(candidate_policy, question)
            )
            suppressed |= lost
        collateral_damage = bool(suppressed)

        if not fix_effective:
            summary = (
                f"Simulation: the change did NOT remove '{offending_source}' from the "
                "failing answer's grounding."
            )
        elif collateral_damage:
            summary = (
                f"Simulation: the change removed '{offending_source}' but also suppressed "
                f"legitimate sources ({', '.join(sorted(suppressed))}) — over-broad."
            )
        else:
            summary = (
                f"Simulation: the change cleanly removed '{offending_source}' from factual "
                "grounding with no collateral suppression of legitimate sources."
            )
        return SandboxResult(
            fix_effective=fix_effective,
            collateral_damage=collateral_damage,
            suppressed_sources=sorted(suppressed),
            summary=summary,
        )
