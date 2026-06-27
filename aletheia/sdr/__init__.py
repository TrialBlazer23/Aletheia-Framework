"""Synapse Data Representation (SDR) — the typed data contracts.

Milestone 1 ships the Tier-1 universal primitives plus the two small composite
assets the first cascade needs (retrieved context, generated answer). The full
~79-type catalog (knowledge-graph elements, ethical analysis reports, creative
types, ...) lands in later milestones. Conventions held here:

* every instance carries an ``SDR_Metadata_Block`` (source, timestamp, owner);
* claims carry an ``SDR_Confidence_Score`` (0.0–1.0);
* source attribution is mandatory (anti-hallucination).
"""

from aletheia.sdr.primitives import (
    AnswerAsset,
    RetrievedContextAsset,
    SdrConfidenceScore,
    SdrDirectiveViolation,
    SdrEthicalAnalysisReport,
    SdrMetadataBlock,
    SdrSourcePassage,
    SdrTextBlock,
    SdrUidReference,
)

__all__ = [
    "SdrMetadataBlock",
    "SdrConfidenceScore",
    "SdrTextBlock",
    "SdrUidReference",
    "SdrSourcePassage",
    "RetrievedContextAsset",
    "AnswerAsset",
    "SdrDirectiveViolation",
    "SdrEthicalAnalysisReport",
]
