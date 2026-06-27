"""SDR Tier-1 primitives + the first cascade's composite assets.

Field names follow the SDR conventions (Synapse_UID, SDR_Metadata_Block, ...).
As with Synapse messages, Python uses snake_case while the canonical SDR names
are preserved as aliases so serialized assets read like the spec.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from aletheia.protocol.uids import new_uid


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _SdrModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


# --------------------------------------------------------------------------- #
# Tier 1 — universal primitives
# --------------------------------------------------------------------------- #
class SdrMetadataBlock(_SdrModel):
    """The provenance wrapper every SDR instance carries."""

    source_uid: str = Field(alias="Source_UID")
    owning_model_uid: str = Field(alias="Owning_Model_UID")
    creation_timestamp: datetime = Field(default_factory=_utc_now, alias="Creation_Timestamp")
    version_info: str = Field(default="1.0", alias="Version_Info")
    secrecy_level: str | None = Field(default=None, alias="Secrecy_Level")


class SdrConfidenceScore(_SdrModel):
    score: float = Field(ge=0.0, le=1.0, alias="Score")


class SdrTextBlock(_SdrModel):
    text: str = Field(alias="Text")
    language: str = Field(default="en", alias="Language")


class SdrUidReference(_SdrModel):
    uid: str = Field(alias="UID")


# --------------------------------------------------------------------------- #
# Composite assets used by the Milestone 1 cascade
# (Tier-3 graph/fact types arrive in Milestone 4; these compose Tier-1 pieces.)
# --------------------------------------------------------------------------- #
class SdrSourcePassage(_SdrModel):
    """One retrieved passage, with mandatory source attribution + confidence."""

    text: SdrTextBlock = Field(alias="Text")
    data_source: str = Field(alias="Data_Source")  # e.g. a doc path/heading
    confidence: SdrConfidenceScore = Field(alias="Confidence")


class RetrievedContextAsset(_SdrModel):
    """The Archivist's output: question + grounded context, addressable by UID.

    Milestone 4 makes retrieval *hybrid*: ``passages`` come from vector search and
    ``facts`` come from traversing the knowledge graph. Either may be empty; the
    Narrator uses whichever grounds the answer best, and facts let it answer
    relational questions ("what does X enforce?") with a cited triple.
    """

    synapse_uid: str = Field(default_factory=lambda: new_uid("ASSET", "RETRIEVED_CONTEXT"), alias="Synapse_UID")
    turn_id: str = Field(alias="Turn_ID")
    question: str = Field(alias="Question")
    passages: list[SdrSourcePassage] = Field(default_factory=list, alias="Passages")
    facts: list["SdrFactAssertion"] = Field(default_factory=list, alias="Facts")
    metadata: SdrMetadataBlock = Field(alias="SDR_Metadata_Block")


class AnswerAsset(_SdrModel):
    """The Narrator's output: the grounded answer + the sources it drew on."""

    synapse_uid: str = Field(default_factory=lambda: new_uid("ASSET", "ANSWER"), alias="Synapse_UID")
    turn_id: str = Field(alias="Turn_ID")
    question: str = Field(alias="Question")
    answer: SdrTextBlock = Field(alias="Answer")
    sources: list[str] = Field(default_factory=list, alias="Sources")
    confidence: SdrConfidenceScore = Field(alias="Confidence")
    metadata: SdrMetadataBlock = Field(alias="SDR_Metadata_Block")


class SdrDirectiveViolation(_SdrModel):
    """One cited Prime-Directive violation within an analysis report."""

    rule_name: str = Field(alias="Rule_Name")
    directive_id: str = Field(alias="Directive_ID")
    directive_name: str = Field(alias="Directive_Name")
    severity: str = Field(alias="Severity")
    evidence: str = Field(alias="Evidence")


class SdrEthicalAnalysisReport(_SdrModel):
    """The Philosopher's verdict on an output, with cited directives + reasoning.

    Anti-hallucination by construction: the verdict must cite the specific
    directive(s) and the evidence that triggered it — the Philosopher cannot
    veto (or approve) on vibes.
    """

    synapse_uid: str = Field(
        default_factory=lambda: new_uid("ASSET", "ETHICAL_ANALYSIS"), alias="Synapse_UID"
    )
    turn_id: str = Field(alias="Turn_ID")
    subject_asset_uid: str = Field(alias="Subject_Asset_UID")  # the answer being judged
    verdict: str = Field(alias="Verdict")  # APPROVED | REJECTED
    violations: list[SdrDirectiveViolation] = Field(default_factory=list, alias="Violations")
    flags: list[SdrDirectiveViolation] = Field(default_factory=list, alias="Flags")
    reasoning: SdrTextBlock = Field(alias="Reasoning")
    confidence: SdrConfidenceScore = Field(alias="Confidence")
    escalate_to_human: bool = Field(default=False, alias="Escalate_To_Human")
    metadata: SdrMetadataBlock = Field(alias="SDR_Metadata_Block")


# --------------------------------------------------------------------------- #
# Tier-3 — the Archivist's knowledge-graph assets (Milestone 4)
# The neuro-symbolic heart: deterministically-parsed entities + relations, each
# carrying mandatory source attribution + confidence (the anti-hallucination
# patterns from §6 — no claim without a citation).
# --------------------------------------------------------------------------- #
class SdrKnowledgeGraphElement(_SdrModel):
    """One node in the knowledge graph — an entity with its type + provenance."""

    synapse_uid: str = Field(
        default_factory=lambda: new_uid("ASSET", "KG_ELEMENT"), alias="Synapse_UID"
    )
    name: str = Field(alias="Name")
    entity_type: str = Field(alias="Entity_Type")  # controlled vocab (PERSON, CONCEPT, ...)
    sources: list[str] = Field(default_factory=list, alias="Sources")
    metadata: SdrMetadataBlock = Field(alias="SDR_Metadata_Block")


class SdrFactAssertion(_SdrModel):
    """One relation (subject–predicate–object) the Archivist asserts.

    Anti-hallucination by construction: a fact is meaningless without its
    ``Data_Source`` and the ``Evidence`` sentence it was parsed from, plus a
    quantified confidence. The Narrator may only state facts that carry these.
    """

    synapse_uid: str = Field(
        default_factory=lambda: new_uid("ASSET", "FACT"), alias="Synapse_UID"
    )
    subject: str = Field(alias="Subject")
    predicate: str = Field(alias="Predicate")
    object: str = Field(alias="Object")
    data_source: str = Field(alias="Data_Source")  # where the fact was found
    evidence: str = Field(alias="Evidence")  # the source sentence (the receipt)
    confidence: SdrConfidenceScore = Field(alias="Confidence")
    metadata: SdrMetadataBlock = Field(alias="SDR_Metadata_Block")


# --------------------------------------------------------------------------- #
# Tier-3 — the Diagnostician's observability assets (Milestone 3)
# `SDR_Performance_Log_Entry`, the CHOREOGRAPHY_LOG, and `SDR_Anomaly_Report`.
# --------------------------------------------------------------------------- #
class SdrChoreographyHop(_SdrModel):
    """One observed message in a cascade — a `SDR_Performance_Log_Entry`.

    The Diagnostician records every hop it sees so the whole cascade can be
    replayed and timed. This is the raw material the Resonance Cycle will later
    analyse for "System Harmony".
    """

    sequence: int = Field(alias="Sequence")  # 1-based order within the cascade
    source_uid: str = Field(alias="Source_UID")
    message_type: str = Field(alias="Message_Type")  # EVENT | TRIGGER | STATE_CHANGE
    label: str = Field(alias="Label")  # event name / action / status code
    elapsed_seconds: float = Field(alias="Elapsed_Seconds")  # since cascade start


class SdrChoreographyLog(_SdrModel):
    """The CHOREOGRAPHY_LOG: the Diagnostician's per-cascade telemetry asset.

    A complete, timed trace of one in-flight cascade keyed by its
    correlation/choreography id, with the agents that took part and the final
    health verdict (COMPLETE / STALLED / LOOPED / ABORTED / OPEN).
    """

    synapse_uid: str = Field(
        default_factory=lambda: new_uid("ASSET", "CHOREOGRAPHY_LOG"), alias="Synapse_UID"
    )
    correlation_id: str = Field(alias="Correlation_ID")
    status: str = Field(alias="Status")  # OPEN | COMPLETE | STALLED | LOOPED | ABORTED
    hop_count: int = Field(alias="Hop_Count")
    duration_seconds: float = Field(alias="Duration_Seconds")
    participants: list[str] = Field(default_factory=list, alias="Participants")
    hops: list[SdrChoreographyHop] = Field(default_factory=list, alias="Hops")
    metadata: SdrMetadataBlock = Field(alias="SDR_Metadata_Block")


class SdrAnomalyReport(_SdrModel):
    """`SDR_Anomaly_Report` — what the Diagnostician emits when it detects trouble.

    Cites the affected cascade, the kind of anomaly (LOOP / STALL / …), the
    evidence, who was involved, and the self-healing action taken.
    """

    synapse_uid: str = Field(
        default_factory=lambda: new_uid("ASSET", "ANOMALY_REPORT"), alias="Synapse_UID"
    )
    correlation_id: str = Field(alias="Correlation_ID")
    anomaly_type: str = Field(alias="Anomaly_Type")  # LOOP | STALL | DELIVERY_ERROR
    severity: str = Field(alias="Severity")  # CRITICAL | HIGH | MEDIUM | LOW
    description: SdrTextBlock = Field(alias="Description")
    evidence: str = Field(alias="Evidence")
    participants: list[str] = Field(default_factory=list, alias="Participants")
    action_taken: str = Field(alias="Action_Taken")
    metadata: SdrMetadataBlock = Field(alias="SDR_Metadata_Block")


# RetrievedContextAsset references SdrFactAssertion, which is defined above it in
# source order via a forward reference — resolve it now that both exist.
RetrievedContextAsset.model_rebuild()
