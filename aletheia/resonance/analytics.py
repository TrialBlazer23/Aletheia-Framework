"""Performance analytics — Phase I (Dissonance Detection) + Phase II (Harmonic
Analysis) of the Resonance Cycle.

RFC-001 §3.2 defines four normalized indices whose weighted sum is "System
Harmony". A **Dissonance Event** fires when harmony drops below a threshold —
classically when a user flags an answer as incorrect. Harmonic Analysis then
traces the cascade backward to the data point that caused it, producing the
FAILURE_REPORT (`SDR_Root_Cause_Analysis`).

These computations are deliberately transparent and deterministic (the Glass
Box): each index is a simple, explainable function of the turn's telemetry,
verdict, and user feedback — not a black box.
"""

from __future__ import annotations

from dataclasses import dataclass

from aletheia.agents.family import NEXUS_MIND_UID
from aletheia.sdr.primitives import (
    AnswerAsset,
    RetrievedContextAsset,
    SdrCausalFactor,
    SdrChoreographyLog,
    SdrConfidenceScore,
    SdrEthicalAnalysisReport,
    SdrMetadataBlock,
    SdrPerformanceIndices,
    SdrRootCauseAnalysis,
)

# RFC-001 §3.2 weights.
_W_EFFICIENCY = 0.20
_W_FIDELITY = 0.30
_W_COORDINATION = 0.20
_W_ALIGNMENT = 0.30

# A clean Q&A turn is ~9 hops; we use that as the efficiency baseline.
_BASELINE_HOPS = 9
_UNHEALTHY_STATUSES = {"LOOPED", "STALLED", "ABORTED"}


@dataclass(frozen=True)
class Feedback:
    """A user's verdict on an answer — the canonical dissonance trigger."""

    turn_id: str
    rating: str  # "CORRECT" | "INCORRECT"
    note: str = ""

    @property
    def is_negative(self) -> bool:
        return self.rating.upper() == "INCORRECT"


@dataclass(frozen=True)
class DissonanceEvent:
    """System Harmony fell below threshold — the cycle should engage."""

    turn_id: str
    indices: SdrPerformanceIndices
    summary: str


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


class PerformanceAnalyzer:
    def __init__(self, *, harmony_threshold: float = 0.75) -> None:
        self.harmony_threshold = harmony_threshold

    # --- Phase I: indices + dissonance ------------------------------------- #
    def compute_indices(
        self,
        *,
        choreography: SdrChoreographyLog | None = None,
        ethical_report: SdrEthicalAnalysisReport | None = None,
        answer: AnswerAsset | None = None,
        feedback: Feedback | None = None,
        turn_id: str = "",
    ) -> SdrPerformanceIndices:
        efficiency = self._efficiency(choreography)
        fidelity = self._fidelity(answer, feedback)
        coordination = self._coordination(choreography)
        alignment = self._alignment(ethical_report)
        harmony = _clamp(
            _W_EFFICIENCY * efficiency
            + _W_FIDELITY * fidelity
            + _W_COORDINATION * coordination
            + _W_ALIGNMENT * alignment
        )
        return SdrPerformanceIndices(
            turn_id=turn_id or (feedback.turn_id if feedback else ""),
            efficiency=round(efficiency, 4),
            fidelity=round(fidelity, 4),
            coordination=round(coordination, 4),
            alignment=round(alignment, 4),
            harmony=round(harmony, 4),
            metadata=SdrMetadataBlock(source_uid=NEXUS_MIND_UID, owning_model_uid=NEXUS_MIND_UID),
        )

    def detect_dissonance(
        self, indices: SdrPerformanceIndices, *, turn_id: str
    ) -> DissonanceEvent | None:
        if indices.harmony >= self.harmony_threshold:
            return None
        weakest = min(
            ("efficiency", indices.efficiency),
            ("fidelity", indices.fidelity),
            ("coordination", indices.coordination),
            ("alignment", indices.alignment),
            key=lambda kv: kv[1],
        )
        return DissonanceEvent(
            turn_id=turn_id,
            indices=indices,
            summary=(
                f"System Harmony {indices.harmony:.2f} < {self.harmony_threshold:.2f} "
                f"(weakest: {weakest[0]} {weakest[1]:.2f})."
            ),
        )

    # --- Phase II: Harmonic Analysis (root cause) -------------------------- #
    def root_cause(
        self,
        *,
        turn_id: str,
        answer: AnswerAsset | None,
        context: RetrievedContextAsset | None,
        feedback: Feedback | None,
        offending_source: str | None = None,
    ) -> SdrRootCauseAnalysis:
        """Trace a flagged answer back to the source that supplied the claim.

        The heuristic is intentionally conservative: it blames the source of the
        top-ranked fact the answer leaned on. It is allowed to be wrong — the
        sandbox + the Philosopher are the safety net that stops a mis-blamed,
        over-broad fix from ever being applied.
        """
        if offending_source is None:
            offending_source = self.offending_source(answer, context)
        causes: list[SdrCausalFactor] = []
        if offending_source:
            causes.append(
                SdrCausalFactor(
                    description=(
                        f"The answer was grounded on content from '{offending_source}', "
                        "which the user flagged as incorrect."
                    ),
                    locus="Archivist source validation",
                    evidence=self._evidence_for(offending_source, context),
                )
            )
            recommended = (
                f"Increase validation strictness for source '{offending_source}': "
                "distrust it as factual ground truth."
            )
        else:
            causes.append(
                SdrCausalFactor(
                    description="A negative outcome with no single attributable source.",
                    locus="unattributed",
                    evidence=feedback.note if feedback else "",
                )
            )
            recommended = "Manual review required — no single source could be attributed."

        summary = (
            feedback.note
            or (feedback and f"User rated turn {turn_id} as {feedback.rating}.")
            or "Dissonance detected."
        )
        return SdrRootCauseAnalysis(
            turn_id=turn_id,
            dissonance_summary=summary,
            root_causes=causes,
            recommended_action=recommended,
            confidence=SdrConfidenceScore(score=0.8 if offending_source else 0.3),
            metadata=SdrMetadataBlock(source_uid=NEXUS_MIND_UID, owning_model_uid=NEXUS_MIND_UID),
        )

    # --- index helpers ----------------------------------------------------- #
    @staticmethod
    def _efficiency(choreography: SdrChoreographyLog | None) -> float:
        if choreography is None:
            return 1.0
        if choreography.status in _UNHEALTHY_STATUSES:
            return 0.3
        if choreography.hop_count <= 0:
            return 1.0
        return _clamp(_BASELINE_HOPS / max(choreography.hop_count, _BASELINE_HOPS))

    @staticmethod
    def _fidelity(answer: AnswerAsset | None, feedback: Feedback | None) -> float:
        if feedback is not None:
            return 0.0 if feedback.is_negative else 1.0
        if answer is not None:
            return _clamp(answer.confidence.score)
        return 0.9

    @staticmethod
    def _coordination(choreography: SdrChoreographyLog | None) -> float:
        if choreography is None:
            return 1.0
        return 0.4 if choreography.status in _UNHEALTHY_STATUSES else 1.0

    @staticmethod
    def _alignment(ethical_report: SdrEthicalAnalysisReport | None) -> float:
        if ethical_report is None:
            return 1.0
        if ethical_report.verdict == "REJECTED":
            return 0.0
        return 0.7 if ethical_report.flags else 1.0

    @staticmethod
    def offending_source(
        answer: AnswerAsset | None, context: RetrievedContextAsset | None
    ) -> str | None:
        # Prefer the source of the top retrieved fact the answer leaned on.
        if context is not None and context.facts:
            return context.facts[0].data_source
        if answer is not None and answer.sources:
            return answer.sources[0]
        if context is not None and context.passages:
            return context.passages[0].data_source
        return None

    @staticmethod
    def _evidence_for(source: str, context: RetrievedContextAsset | None) -> str:
        if context is not None:
            for fact in context.facts:
                if fact.data_source == source:
                    return f'"{fact.subject} {fact.predicate} {fact.object}" — {fact.evidence}'
        return f"Answer cited source '{source}'."
