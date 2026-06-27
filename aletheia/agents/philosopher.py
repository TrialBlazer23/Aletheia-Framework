"""The Philosopher (0x00C3) — safety kernel / conscience.

Its Listener is tuned to the Narrator's ``DRAFT_READY`` event. On firing it
validates the draft answer against the Prime Directives (rule-based first, as
the design and ANALYSIS.md both require), writes an ``SDR_Ethical_Analysis_Report``
citing any violated directive + evidence, and broadcasts its verdict:

* ``APPROVED`` — no CRITICAL/HIGH violation; the answer may reach the user.
* ``REJECTED`` — **veto.** A CRITICAL/HIGH violation; the answer is withheld.

This inserts the Philosopher into the cascade *before the user*, which is the
whole point of the "Glass Box": generation (Narrator) is separated from judgment
(Philosopher), and every verdict is auditable.

Rule-based is the hard floor. An LLM-assisted pass over the subtler directives
(flawed motivation, manipulation) layers on top later — it never replaces this.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aletheia.agents.family import NARRATOR_UID, PHILOSOPHER_UID
from aletheia.agents.family_member import FamilyMember
from aletheia.bus.base import MessageBus
from aletheia.memory.asset_store import AssetStore
from aletheia.protocol.messages import MessageType, SynapseMessage
from aletheia.safety.prime_directives import PrimeDirectives
from aletheia.safety.validator import RuleBasedValidator, Violation
from aletheia.sdr.primitives import (
    AnswerAsset,
    SdrConfidenceScore,
    SdrDirectiveViolation,
    SdrEthicalAnalysisReport,
    SdrMetadataBlock,
    SdrPolicyModificationProposal,
    SdrTextBlock,
    SdrVerificationResult,
)
from aletheia.sil.interest_profile import InterestProfile, InterestRule

if TYPE_CHECKING:  # avoid an import cycle: resonance imports the Philosopher
    from aletheia.resonance.sandbox import SandboxResult

# Directive #1 — the one a careless self-modification is most likely to breach.
_SANCTITY_OF_INFORMATION = "The Sanctity of Information Flow"

# Severities that trigger a veto (everything else is a non-blocking flag).
_VETO_SEVERITIES = {"CRITICAL", "HIGH"}


def _philosopher_profile() -> InterestProfile:
    return InterestProfile(
        [
            InterestRule(
                action_to_trigger="VALIDATE_OUTPUT",
                source_model_uid=NARRATOR_UID,
                message_type=MessageType.EVENT,
                event_name="DRAFT_READY",
            )
        ]
    )


class Philosopher(FamilyMember):
    def __init__(
        self,
        *,
        bus: MessageBus,
        asset_store: AssetStore,
        directives: PrimeDirectives | None = None,
    ) -> None:
        super().__init__(
            name="Philosopher",
            uid=PHILOSOPHER_UID,
            bus=bus,
            interest_profile=_philosopher_profile(),
        )
        self._assets = asset_store
        self.directives = directives or PrimeDirectives.load()
        self._validator = RuleBasedValidator(self.directives)

    async def handle_action(
        self, action: str, data: dict[str, Any], message: SynapseMessage
    ) -> None:
        if action != "VALIDATE_OUTPUT":
            return
        answer: AnswerAsset = self._assets.get(data["data_asset_uid"])

        all_findings = self._validator.validate(answer.answer.text)
        vetoes = [v for v in all_findings if v.severity in _VETO_SEVERITIES]
        flags = [v for v in all_findings if v.severity not in _VETO_SEVERITIES]
        approved = not vetoes

        report = SdrEthicalAnalysisReport(
            turn_id=answer.turn_id,
            subject_asset_uid=answer.synapse_uid,
            verdict="APPROVED" if approved else "REJECTED",
            violations=[self._to_sdr(v) for v in vetoes],
            flags=[self._to_sdr(v) for v in flags],
            reasoning=SdrTextBlock(text=self._reasoning(approved, vetoes, flags)),
            confidence=SdrConfidenceScore(score=1.0),  # deterministic rules → full certainty
            escalate_to_human=any(v.severity == "CRITICAL" for v in vetoes),
            metadata=SdrMetadataBlock(source_uid=self.uid, owning_model_uid=self.uid),
        )
        self._assets.put(report.synapse_uid, report)

        # (Step 4) broadcast the verdict. APPROVED points at the answer (so the
        # Nexus-Mind can release it); REJECTED points at the report (the reason).
        if approved:
            await self.broadcaster.broadcast_event(
                event_name="APPROVED",
                data_asset_uid=answer.synapse_uid,
                description="Output cleared against the Prime Directives.",
                confidence_score=answer.confidence.score,
            )
        else:
            await self.broadcaster.broadcast_event(
                event_name="REJECTED",
                data_asset_uid=report.synapse_uid,
                description=f"VETO — violates {vetoes[0].directive_name}.",
                confidence_score=1.0,
            )

    # --- Runtime Safety Kernel: verify a Resonance policy proposal --------- #
    def verify_policy_proposal(
        self,
        proposal: SdrPolicyModificationProposal,
        sandbox_result: "SandboxResult",
    ) -> SdrVerificationResult:
        """Gate a self-improvement proposal (RFC-001 §3.3, NSAP-ARCH-003 §4).

        The Philosopher is the Runtime Safety Kernel: no policy change reaches the
        Human Gavel without passing here. Two hard gates, rule-based (the floor):

        * **Soundness** — the sandbox must show the change actually fixes the
          fault. An ineffective change is rejected (don't mutate behaviour for
          nothing).
        * **Sanctity of Information Flow (Directive #1)** — if the sandbox shows
          the change also suppresses *legitimate* sources, it is censorship by
          another name and is vetoed, citing the directive.
        """
        if not sandbox_result.fix_effective:
            return self._verification(
                proposal,
                status="REJECTED",
                cited=None,
                reasoning=(
                    "Rejected: the sandbox shows the proposed change does not remove the "
                    "flagged content, so it would alter behaviour without fixing the fault."
                ),
                sandbox=sandbox_result,
            )
        if sandbox_result.collateral_damage:
            return self._verification(
                proposal,
                status="REJECTED",
                cited=_SANCTITY_OF_INFORMATION,
                reasoning=(
                    "Rejected: the change is over-broad — the sandbox shows it would also "
                    f"suppress legitimate sources ({', '.join(sandbox_result.suppressed_sources)}). "
                    "Distrusting truthful information violates the Sanctity of Information Flow."
                ),
                sandbox=sandbox_result,
            )
        return self._verification(
            proposal,
            status="VERIFIED",
            cited=None,
            reasoning=(
                "Verified: the change cleanly removes the flagged source from factual "
                "grounding with no collateral suppression, preserving information integrity. "
                "Cleared against the Prime Directives."
            ),
            sandbox=sandbox_result,
        )

    def _verification(
        self,
        proposal: SdrPolicyModificationProposal,
        *,
        status: str,
        cited: str | None,
        reasoning: str,
        sandbox: "SandboxResult",
    ) -> SdrVerificationResult:
        return SdrVerificationResult(
            turn_id=proposal.turn_id,
            proposal_uid=proposal.synapse_uid,
            status=status,
            cited_directive=cited,
            reasoning=SdrTextBlock(text=reasoning),
            sandbox_summary=sandbox.summary,
            confidence=SdrConfidenceScore(score=1.0),  # deterministic rule layer
            metadata=SdrMetadataBlock(source_uid=self.uid, owning_model_uid=self.uid),
        )

    @staticmethod
    def _to_sdr(v: Violation) -> SdrDirectiveViolation:
        return SdrDirectiveViolation(
            rule_name=v.rule_name,
            directive_id=v.directive_id,
            directive_name=v.directive_name,
            severity=v.severity,
            evidence=v.evidence,
        )

    @staticmethod
    def _reasoning(approved: bool, vetoes: list[Violation], flags: list[Violation]) -> str:
        if approved and not flags:
            return "No Prime-Directive violations detected by the rule layer; output approved."
        parts: list[str] = []
        if vetoes:
            v = vetoes[0]
            parts.append(
                f"Vetoed: rule '{v.rule_name}' ({v.severity}) violates "
                f"{v.directive_id} — {v.directive_name}. Evidence: {v.evidence}."
            )
        for f in flags:
            parts.append(
                f"Flagged (non-blocking): rule '{f.rule_name}' ({f.severity}) under "
                f"{f.directive_id}. Evidence: {f.evidence}."
            )
        return " ".join(parts)
