"""The Resonance Engine — orchestrates the four-phase cycle (RFC-001 §2).

This is where supervised self-improvement actually happens, with every
non-negotiable safety rail wired in:

    Phase I   Dissonance Detection  — compute the four indices; engage only if
                                      System Harmony fell below threshold.
    Phase II  Harmonic Analysis     — trace the cascade to a root cause
                                      (the FAILURE_REPORT).
    Phase III Proposal Generation   — formulate a POLICY_UPDATE, then have the
                                      Philosopher verify it against the Prime
                                      Directives **after simulating it in an
                                      isolated Resonance Sandbox**.
    Phase IV  Integration           — rate-limit, snapshot, and apply ONLY after
                                      the Human Gavel approves; auto-roll-back if
                                      dissonance got worse after deploy.

The Nexus-Mind drives this cycle in the design; the engine carries that logic
and emits a Synapse message at every phase so the whole thing is in the Glass
Box. Nothing here can change behaviour without (a) a clean sandbox simulation,
(b) the Philosopher's verification, and (c) a human approval — in that order.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from aletheia.agents.family import NEXUS_MIND_UID
from aletheia.agents.philosopher import Philosopher
from aletheia.bus.base import MessageBus
from aletheia.memory.asset_store import AssetStore
from aletheia.protocol.messages import make_event, make_state_change
from aletheia.resonance.analytics import Feedback, PerformanceAnalyzer
from aletheia.resonance.policy import PolicyStore
from aletheia.resonance.sandbox import ResonanceSandbox
from aletheia.sdr.primitives import (
    AnswerAsset,
    RetrievedContextAsset,
    SdrChoreographyLog,
    SdrEthicalAnalysisReport,
    SdrMetadataBlock,
    SdrPerformanceIndices,
    SdrPolicyModificationProposal,
    SdrRootCauseAnalysis,
    SdrVerificationResult,
)

# Outcome statuses (also the audit vocabulary for a cycle).
NO_DISSONANCE = "NO_DISSONANCE"
NO_ATTRIBUTION = "NO_ATTRIBUTION"
REJECTED_BY_PHILOSOPHER = "REJECTED_BY_PHILOSOPHER"
RATE_LIMITED = "RATE_LIMITED"
GAVEL_REJECTED = "GAVEL_REJECTED"
APPLIED = "APPLIED"
AUTO_ROLLED_BACK = "AUTO_ROLLED_BACK"


@dataclass
class GavelDecision:
    """The human operator's ruling at the Integration gate."""

    approved: bool
    operator: str = "human"
    note: str = ""


# A post-deploy evaluator re-measures harmony after a change is applied, so the
# engine can auto-roll-back if dissonance got *worse*.
PostDeployEvaluator = Callable[[], SdrPerformanceIndices]


@dataclass
class ResonanceOutcome:
    """The full, auditable result of one turn of the cycle."""

    status: str
    message: str
    indices: SdrPerformanceIndices | None = None
    rca: SdrRootCauseAnalysis | None = None
    proposal: SdrPolicyModificationProposal | None = None
    verification: SdrVerificationResult | None = None
    gavel: GavelDecision | None = None
    applied_version: int | None = None

    @property
    def changed_behaviour(self) -> bool:
        return self.status == APPLIED


# --------------------------------------------------------------------------- #
# The Human Gavel (Integration gate) — the owner's "Human Gavel forever" default
# --------------------------------------------------------------------------- #
class HumanGavel(ABC):
    @abstractmethod
    def review(
        self,
        *,
        proposal: SdrPolicyModificationProposal,
        verification: SdrVerificationResult,
        rca: SdrRootCauseAnalysis,
        indices: SdrPerformanceIndices,
    ) -> GavelDecision:
        ...


class CallbackGavel(HumanGavel):
    """Drive the gavel from a callable — for tests/demos and any custom UI.

    The callback may return a ``GavelDecision`` or a plain bool (approve/reject).
    """

    def __init__(self, decide: Callable[..., GavelDecision | bool]) -> None:
        self._decide = decide

    def review(self, **kwargs) -> GavelDecision:
        result = self._decide(**kwargs)
        if isinstance(result, GavelDecision):
            return result
        return GavelDecision(approved=bool(result))


class ConsoleGavel(HumanGavel):
    """Prompt the human operator at the terminal (the real gavel)."""

    def review(self, *, proposal, verification, rca, indices) -> GavelDecision:
        print("\n  ⚖️  HUMAN GAVEL — a policy change needs your approval:")
        print(f"     proposal : {proposal.change_summary} (impact: {proposal.impact_class})")
        print(f"     why      : {rca.recommended_action}")
        print(f"     verified : {verification.status} — {verification.sandbox_summary}")
        try:
            answer = input("     approve this change? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"
        approved = answer in ("y", "yes")
        return GavelDecision(approved=approved, note="approved at console" if approved else "rejected at console")


# --------------------------------------------------------------------------- #
# Rate limiter — RFC-001 §3: prevent "cascading over-optimization"
# --------------------------------------------------------------------------- #
class RateLimiter:
    def __init__(
        self,
        *,
        max_changes: int = 3,
        per_seconds: float = 3600.0,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.max_changes = max_changes
        self.per_seconds = per_seconds
        self._now = now or time.monotonic
        self._applied_at: list[float] = []

    def allow(self) -> bool:
        self._prune()
        return len(self._applied_at) < self.max_changes

    def record(self) -> None:
        self._applied_at.append(self._now())

    def _prune(self) -> None:
        cutoff = self._now() - self.per_seconds
        self._applied_at = [t for t in self._applied_at if t >= cutoff]


# --------------------------------------------------------------------------- #
# The engine
# --------------------------------------------------------------------------- #
class ResonanceEngine:
    def __init__(
        self,
        *,
        policy_store: PolicyStore,
        philosopher: Philosopher,
        sandbox: ResonanceSandbox,
        gavel: HumanGavel,
        analyzer: PerformanceAnalyzer | None = None,
        rate_limiter: RateLimiter | None = None,
        bus: MessageBus | None = None,
        asset_store: AssetStore | None = None,
        control_questions: list[str] | None = None,
        source_uid: str = NEXUS_MIND_UID,
    ) -> None:
        self.policy_store = policy_store
        self.philosopher = philosopher
        self.sandbox = sandbox
        self.gavel = gavel
        self.analyzer = analyzer or PerformanceAnalyzer()
        self.rate_limiter = rate_limiter or RateLimiter()
        self._bus = bus
        self._assets = asset_store
        self._control_questions = control_questions or []
        self._source = source_uid

    async def run_cycle(
        self,
        *,
        feedback: Feedback,
        failing_question: str,
        answer: AnswerAsset | None = None,
        context: RetrievedContextAsset | None = None,
        choreography: SdrChoreographyLog | None = None,
        ethical_report: SdrEthicalAnalysisReport | None = None,
        post_deploy_evaluator: PostDeployEvaluator | None = None,
    ) -> ResonanceOutcome:
        turn_id = feedback.turn_id

        # --- Phase I: Dissonance Detection --------------------------------- #
        indices = self.analyzer.compute_indices(
            choreography=choreography,
            ethical_report=ethical_report,
            answer=answer,
            feedback=feedback,
            turn_id=turn_id,
        )
        await self._put_and_emit_event(indices, "PERFORMANCE_INDICES", indices.synapse_uid,
                                       f"System Harmony {indices.harmony:.2f}.")
        dissonance = self.analyzer.detect_dissonance(indices, turn_id=turn_id)
        if dissonance is None:
            return ResonanceOutcome(
                status=NO_DISSONANCE, message="System Harmony within tolerance; no action.",
                indices=indices,
            )
        await self._emit_state("DISSONANCE_DETECTED", turn_id, dissonance.summary)

        # --- Phase II: Harmonic Analysis ----------------------------------- #
        offending = self.analyzer.offending_source(answer, context)
        rca = self.analyzer.root_cause(
            turn_id=turn_id, answer=answer, context=context, feedback=feedback,
            offending_source=offending,
        )
        await self._put_and_emit_event(rca, "FAILURE_REPORT", rca.synapse_uid, rca.recommended_action)
        if offending is None:
            return ResonanceOutcome(
                status=NO_ATTRIBUTION, message="No single source could be attributed; manual review.",
                indices=indices, rca=rca,
            )

        # --- Phase III: Proposal Generation -------------------------------- #
        candidate = self.policy_store.current.model_copy(deep=True)
        if offending not in candidate.distrusted_sources:
            candidate.distrusted_sources = [*candidate.distrusted_sources, offending]
        proposal = SdrPolicyModificationProposal(
            turn_id=turn_id,
            target="Archivist.distrusted_sources",
            change_summary=f"Distrust source '{offending}' as factual ground truth.",
            rationale=rca.recommended_action,
            impact_class=self._classify_impact(offending),
            metadata=SdrMetadataBlock(source_uid=self._source, owning_model_uid=self._source),
        )
        await self._put_and_emit_event(proposal, "POLICY_UPDATE_PROPOSED", proposal.synapse_uid,
                                       proposal.change_summary)

        # --- Phase III: Verification (sandbox + Philosopher) --------------- #
        sandbox_result = self.sandbox.simulate(
            current_policy=self.policy_store.current,
            candidate_policy=candidate,
            failing_question=failing_question,
            offending_source=offending,
            control_questions=self._control_questions,
        )
        verification = self.philosopher.verify_policy_proposal(proposal, sandbox_result)
        await self._put_and_emit_event(
            verification,
            "POLICY_VERIFIED" if verification.status == "VERIFIED" else "POLICY_REJECTED",
            verification.synapse_uid, verification.reasoning.text,
        )
        if verification.status != "VERIFIED":
            return ResonanceOutcome(
                status=REJECTED_BY_PHILOSOPHER,
                message=f"Philosopher vetoed the proposal: {verification.reasoning.text}",
                indices=indices, rca=rca, proposal=proposal, verification=verification,
            )

        # --- Phase IV: Integration (rate-limit → gavel → snapshot+apply) --- #
        if not self.rate_limiter.allow():
            await self._emit_state("RATE_LIMITED", turn_id,
                                   "Resonance rate limit hit; deferring to avoid over-optimization.")
            return ResonanceOutcome(
                status=RATE_LIMITED, message="Rate-limited to prevent cascading over-optimization.",
                indices=indices, rca=rca, proposal=proposal, verification=verification,
            )

        decision = self.gavel.review(
            proposal=proposal, verification=verification, rca=rca, indices=indices
        )
        if not decision.approved:
            await self._emit_state("HUMAN_GAVEL_REJECTED", turn_id,
                                   f"Operator '{decision.operator}' rejected the change.")
            return ResonanceOutcome(
                status=GAVEL_REJECTED, message="Human Gavel rejected the change.",
                indices=indices, rca=rca, proposal=proposal, verification=verification, gavel=decision,
            )
        await self._emit_state("HUMAN_GAVEL_APPROVED", turn_id,
                               f"Operator '{decision.operator}' approved the change.")

        # Snapshot is implicit in PolicyStore.apply (it always snapshots first).
        # record() only *after* a successful apply, so a failed apply never
        # consumes the rate-limit budget.
        applied = self.policy_store.apply(candidate, reason=proposal.change_summary)
        self.rate_limiter.record()
        await self._emit_state("POLICY_APPLIED", turn_id,
                               f"operational_policy v{applied.version}: {proposal.change_summary}")

        # --- Auto-rollback rail: if dissonance got worse, undo it ---------- #
        if post_deploy_evaluator is not None:
            # Fail safe: if we cannot measure the post-deploy state, we cannot
            # confirm the change helped — so roll it back rather than leave an
            # unverified self-modification in place.
            try:
                post = post_deploy_evaluator()
                worsened = post.harmony < indices.harmony
                reason = f"Auto-rollback: harmony fell {indices.harmony:.2f} → {post.harmony:.2f}."
            except Exception as exc:  # noqa: BLE001 — fail safe toward rollback
                worsened = True
                reason = f"Auto-rollback: post-deploy check failed ({type(exc).__name__}); cannot confirm the fix."
            if worsened:
                self.policy_store.rollback(reason=reason)
                await self._emit_state("POLICY_ROLLED_BACK", turn_id, reason)
                return ResonanceOutcome(
                    status=AUTO_ROLLED_BACK,
                    message="Deploy was not confirmed safe; automatically rolled back.",
                    indices=indices, rca=rca, proposal=proposal, verification=verification,
                    gavel=decision, applied_version=applied.version,
                )

        return ResonanceOutcome(
            status=APPLIED,
            message=f"Change verified, approved, and applied as policy v{applied.version}.",
            indices=indices, rca=rca, proposal=proposal, verification=verification,
            gavel=decision, applied_version=applied.version,
        )

    # --- impact classification (RFC-001 §3.3.3) ---------------------------- #
    @staticmethod
    def _classify_impact(offending_source: str) -> str:
        # Distrusting a single source is a behavioural heuristic change → MEDIUM.
        # (The owner's standing decision is "Human Gavel forever", so every class
        # still requires approval; impact only informs the human.)
        return "MEDIUM"

    # --- Glass Box emission ------------------------------------------------ #
    async def _put_and_emit_event(self, asset, event_name: str, asset_uid: str, description: str) -> None:
        if self._assets is not None:
            self._assets.put(asset_uid, asset)
        if self._bus is None:
            return
        await self._bus.publish(
            make_event(
                source_uid=self._source,
                event_name=event_name,
                data_asset_uid=asset_uid,
                description=description,
                confidence_score=1.0,
            )
        )

    async def _emit_state(self, status_code: str, turn_id: str, reason: str) -> None:
        if self._bus is None:
            return
        await self._bus.publish(
            make_state_change(
                source_uid=self._source,
                target_uid=turn_id,
                status_code=status_code,
                reason=reason,
            )
        )
