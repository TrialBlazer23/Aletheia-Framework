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
    """The Archivist's output: question + grounded passages, addressable by UID."""

    synapse_uid: str = Field(default_factory=lambda: new_uid("ASSET", "RETRIEVED_CONTEXT"), alias="Synapse_UID")
    turn_id: str = Field(alias="Turn_ID")
    question: str = Field(alias="Question")
    passages: list[SdrSourcePassage] = Field(default_factory=list, alias="Passages")
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
