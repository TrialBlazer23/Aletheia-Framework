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
    # "qa" (answer a question) or "creative" (ground a creative concept). The
    # cascade branches on this at the Narrator — same retrieval, different output.
    mode: str = Field(default="qa", alias="Mode")
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


# --------------------------------------------------------------------------- #
# Tier-3 — the Resonance Cycle assets (Milestone 5, RFC-001 / NSAP-ARCH-003)
# Supervised self-improvement: the system turns its own logged failures into a
# verified, human-approved policy change. Every artifact below is auditable.
# --------------------------------------------------------------------------- #
class SdrPerformanceIndices(_SdrModel):
    """The four normalized "System Harmony" indices (RFC-001 §3.2 weights)."""

    synapse_uid: str = Field(
        default_factory=lambda: new_uid("ASSET", "PERFORMANCE_INDICES"), alias="Synapse_UID"
    )
    turn_id: str = Field(default="", alias="Turn_ID")  # the turn these indices score
    efficiency: float = Field(alias="Efficiency_Index")  # resource cost vs baseline
    fidelity: float = Field(alias="Fidelity_Index")  # output matched the objective
    coordination: float = Field(alias="Coordination_Index")  # clean inter-agent flow
    alignment: float = Field(alias="Alignment_Index")  # constitutional compliance
    harmony: float = Field(alias="System_Harmony")  # weighted aggregate (0.20/0.30/0.20/0.30)
    metadata: SdrMetadataBlock = Field(alias="SDR_Metadata_Block")


class SdrCausalFactor(_SdrModel):
    """One identified cause within a root-cause analysis (`SDR_Causal_Factor`)."""

    description: str = Field(alias="Description")
    locus: str = Field(alias="Locus")  # where in the system (agent / parameter)
    evidence: str = Field(alias="Evidence")  # the cascade-log / asset receipt


class SdrRootCauseAnalysis(_SdrModel):
    """The FAILURE_REPORT (RFC-001 §2.2 / `SDR_Root_Cause_Analysis_Output`).

    Harmonic Analysis traces the Domino Cascade backward from a dissonance event
    to the decision or data point that caused it.
    """

    synapse_uid: str = Field(
        default_factory=lambda: new_uid("ASSET", "ROOT_CAUSE_ANALYSIS"), alias="Synapse_UID"
    )
    turn_id: str = Field(alias="Turn_ID")
    dissonance_summary: str = Field(alias="Dissonance_Summary")
    root_causes: list[SdrCausalFactor] = Field(default_factory=list, alias="Root_Causes")
    recommended_action: str = Field(alias="Recommended_Action")
    confidence: SdrConfidenceScore = Field(alias="Confidence")
    metadata: SdrMetadataBlock = Field(alias="SDR_Metadata_Block")


class SdrPolicyModificationProposal(_SdrModel):
    """A Policy Modification Proposal — the `POLICY_UPDATE` candidate (RFC-001 §2.3).

    The concrete candidate policy it would apply is carried alongside (a typed
    ``OperationalPolicy``); this asset is the auditable *description* of the change.
    """

    synapse_uid: str = Field(
        default_factory=lambda: new_uid("ASSET", "POLICY_PROPOSAL"), alias="Synapse_UID"
    )
    turn_id: str = Field(alias="Turn_ID")
    target: str = Field(alias="Target")  # agent / parameter being adjusted
    change_summary: str = Field(alias="Change_Summary")
    rationale: str = Field(alias="Rationale")
    impact_class: str = Field(alias="Impact_Class")  # LOW | MEDIUM | HIGH | CRITICAL
    metadata: SdrMetadataBlock = Field(alias="SDR_Metadata_Block")


class SdrVerificationResult(_SdrModel):
    """The Runtime Safety Kernel's verdict on a proposal (RFC-001 §3.3).

    A proposal is VERIFIED only if it clears the Prime Directives *and* its
    sandbox simulation shows it fixes the fault without collateral harm.
    """

    synapse_uid: str = Field(
        default_factory=lambda: new_uid("ASSET", "VERIFICATION_RESULT"), alias="Synapse_UID"
    )
    turn_id: str = Field(default="", alias="Turn_ID")  # the turn whose fix this judges
    proposal_uid: str = Field(alias="Proposal_UID")
    status: str = Field(alias="Status")  # VERIFIED | REJECTED
    cited_directive: str | None = Field(default=None, alias="Cited_Directive")
    reasoning: SdrTextBlock = Field(alias="Reasoning")
    sandbox_summary: str = Field(alias="Sandbox_Summary")
    confidence: SdrConfidenceScore = Field(alias="Confidence")
    metadata: SdrMetadataBlock = Field(alias="SDR_Metadata_Block")


# --------------------------------------------------------------------------- #
# Tier-3 — the Visionary's creative assets (Milestone 6)
# Structured visual/auditory design briefs — the creative SDR types brought
# online. Field names follow the Synapse_Data_Representation specs (RGB color,
# visual concept brief, color palette, soundscape, music composition).
# --------------------------------------------------------------------------- #
class SdrRgbColorValue(_SdrModel):
    """A color in the RGB additive model (`SDR_RGB_Color_Value`)."""

    red: int = Field(ge=0, le=255, alias="Red_Value")
    green: int = Field(ge=0, le=255, alias="Green_Value")
    blue: int = Field(ge=0, le=255, alias="Blue_Value")
    alpha: float = Field(default=1.0, ge=0.0, le=1.0, alias="Alpha_Channel_Value")

    @property
    def hex(self) -> str:
        return f"#{self.red:02X}{self.green:02X}{self.blue:02X}"


class SdrColorDefinition(_SdrModel):
    """A named color with its RGB value and role (`SDR_Color_Definition`)."""

    name: str = Field(alias="Color_Name")
    rgb: SdrRgbColorValue = Field(alias="RGB_Value")
    role: str = Field(default="primary", alias="Role")  # primary | accent | neutral


class SdrColorPaletteDefinition(_SdrModel):
    """A color palette (`SDR_Color_Palette_Definition`)."""

    synapse_uid: str = Field(default_factory=lambda: new_uid("ASSET", "COLOR_PALETTE"), alias="Synapse_UID")
    name: str = Field(alias="Palette_Name")
    description: str = Field(default="", alias="Palette_Description")
    colors: list[SdrColorDefinition] = Field(default_factory=list, alias="Colors")
    harmony_rule: str = Field(default="", alias="Color_Harmony_Rule")


class SdrVisualConceptBrief(_SdrModel):
    """A brief for visual/concept art (`SDR_Visual_Concept_Brief`)."""

    synapse_uid: str = Field(default_factory=lambda: new_uid("ASSET", "VISUAL_BRIEF"), alias="Synapse_UID")
    title: str = Field(alias="Brief_Title")
    subject_description: SdrTextBlock = Field(alias="Subject_Description")
    visual_styles: list[str] = Field(default_factory=list, alias="Visual_Style_References")
    color_palette: SdrColorPaletteDefinition | None = Field(default=None, alias="Color_Palette")
    mood_and_atmosphere: str = Field(alias="Mood_And_Atmosphere_Target")
    key_elements: list[str] = Field(default_factory=list, alias="Key_Elements_To_Include")
    things_to_avoid: list[str] = Field(default_factory=list, alias="Things_To_Avoid")
    intended_usage: str = Field(default="", alias="Intended_Usage_Context")


class SdrSoundscapeBrief(_SdrModel):
    """A brief for an immersive soundscape (`SDR_Soundscape_Brief`)."""

    synapse_uid: str = Field(default_factory=lambda: new_uid("ASSET", "SOUNDSCAPE_BRIEF"), alias="Synapse_UID")
    overall_atmosphere_goal: str = Field(alias="Overall_Atmosphere_Goal")
    ambient_noise_profile: str = Field(default="", alias="Ambient_Noise_Profile")
    key_sound_effects: list[str] = Field(default_factory=list, alias="Key_Sound_Effects")
    musical_integration_notes: str = Field(default="", alias="Musical_Integration_Notes")
    technical_delivery_specs: str = Field(default="", alias="Technical_Delivery_Specs")


class SdrMusicCompositionBrief(_SdrModel):
    """A brief for thematic music (`SDR_Music_Composition_Brief`)."""

    synapse_uid: str = Field(default_factory=lambda: new_uid("ASSET", "MUSIC_BRIEF"), alias="Synapse_UID")
    title_or_purpose: str = Field(alias="Composition_Title_Or_Purpose")
    genre_style_suggestions: list[str] = Field(default_factory=list, alias="Genre_Style_Suggestions")
    tempo_description: str = Field(default="", alias="Tempo_Description")
    key_modality: str = Field(default="", alias="Key_Modality_Suggestions")
    instrumentation_palette: list[str] = Field(default_factory=list, alias="Instrumentation_Palette")
    emotional_arc_target: str = Field(alias="Emotional_Arc_Target")
    estimated_duration: str = Field(default="", alias="Estimated_Duration")


class ConceptAsset(_SdrModel):
    """The Narrator's *creative* output: a grounded narrative concept.

    The creative-cascade analogue of ``AnswerAsset`` — generation only, judgment
    is the Philosopher's job — that the Visionary turns into design assets.
    """

    synapse_uid: str = Field(default_factory=lambda: new_uid("ASSET", "CONCEPT"), alias="Synapse_UID")
    turn_id: str = Field(alias="Turn_ID")
    request: str = Field(alias="Request")
    concept: SdrTextBlock = Field(alias="Concept")
    sources: list[str] = Field(default_factory=list, alias="Sources")
    confidence: SdrConfidenceScore = Field(alias="Confidence")
    metadata: SdrMetadataBlock = Field(alias="SDR_Metadata_Block")


class CreativeAsset(_SdrModel):
    """The Visionary's deliverable: a bundle of design briefs for a concept.

    One addressable asset gathering the visual concept, color palette, soundscape,
    and music briefs the Visionary generated — the creative cascade's output,
    still safety-checked by the Philosopher before it reaches the user.
    """

    synapse_uid: str = Field(default_factory=lambda: new_uid("ASSET", "CREATIVE_PACKAGE"), alias="Synapse_UID")
    turn_id: str = Field(alias="Turn_ID")
    request: str = Field(alias="Request")
    title: str = Field(alias="Title")
    concept: SdrTextBlock = Field(alias="Concept")
    visual_brief: SdrVisualConceptBrief = Field(alias="Visual_Concept_Brief")
    soundscape_brief: SdrSoundscapeBrief = Field(alias="Soundscape_Brief")
    music_brief: SdrMusicCompositionBrief = Field(alias="Music_Composition_Brief")
    sources: list[str] = Field(default_factory=list, alias="Sources")
    confidence: SdrConfidenceScore = Field(alias="Confidence")
    metadata: SdrMetadataBlock = Field(alias="SDR_Metadata_Block")

    def review_text(self) -> str:
        """Flat text the Philosopher validates before release."""
        vb = self.visual_brief
        parts = [
            self.title,
            self.concept.text,
            vb.subject_description.text,
            vb.mood_and_atmosphere,
            " ".join(vb.key_elements),
            self.soundscape_brief.overall_atmosphere_goal,
            " ".join(self.soundscape_brief.key_sound_effects),
            self.music_brief.emotional_arc_target,
        ]
        return "\n".join(p for p in parts if p)


# RetrievedContextAsset references SdrFactAssertion, which is defined above it in
# source order via a forward reference — resolve it now that both exist.
RetrievedContextAsset.model_rebuild()
