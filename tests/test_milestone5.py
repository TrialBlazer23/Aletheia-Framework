"""Milestone 5: the Resonance Cycle + the Human Gavel (supervised self-improvement).

We prove the loop and — just as importantly — every safety rail: indices +
dissonance, root-cause analysis, the isolated sandbox, the Philosopher's
verification against the Prime Directives, rate-limiting, snapshot + rollback
(manual and automatic), and the Human Gavel. The capstone is the canonical
RFC-001 satire scenario end to end.
"""

import asyncio

from aletheia.agents.family import ARCHIVIST_UID, NEXUS_MIND_UID
from aletheia.agents.philosopher import Philosopher
from aletheia.app.qa_system import QASystem
from aletheia.bus.in_process import InProcessBus
from aletheia.llm.offline_provider import OfflineProvider
from aletheia.log.cascade_log import CascadeLog
from aletheia.memory.asset_store import AssetStore
from aletheia.memory.corpus import Document
from aletheia.resonance.analytics import Feedback, PerformanceAnalyzer
from aletheia.resonance.engine import (
    APPLIED,
    AUTO_ROLLED_BACK,
    GAVEL_REJECTED,
    NO_DISSONANCE,
    RATE_LIMITED,
    REJECTED_BY_PHILOSOPHER,
    CallbackGavel,
    GavelDecision,
    RateLimiter,
    ResonanceEngine,
)
from aletheia.resonance.policy import OperationalPolicy, PolicyStore
from aletheia.resonance.sandbox import ResonanceSandbox
from aletheia.sdr.primitives import (
    RetrievedContextAsset,
    SdrConfidenceScore,
    SdrFactAssertion,
    SdrMetadataBlock,
    SdrPolicyModificationProposal,
)


# --------------------------------------------------------------------------- #
# The versioned operational policy + store (snapshot / rollback)
# --------------------------------------------------------------------------- #
def test_policy_store_defaults_and_distrust_matching():
    store = PolicyStore(path=None)
    assert store.version == 1
    assert store.current.distrusted_sources == []
    assert store.current.distrusts("anything") is False
    p = OperationalPolicy(distrusted_sources=["satire-news.com"])
    assert p.distrusts("article from SATIRE-NEWS.COM › front page") is True


def test_apply_bumps_version_and_snapshots():
    store = PolicyStore(path=None)
    store.apply(OperationalPolicy(distrusted_sources=["satire-news.com"]), reason="fix")
    assert store.version == 2
    assert store.current.distrusted_sources == ["satire-news.com"]
    assert store.snapshot_count == 1
    assert store.history[-1]["event"] == "APPLY"


def test_empty_distrust_entry_does_not_blind_retrieval():
    # A corrupt/empty entry must not match everything (it's a substring of all).
    policy = OperationalPolicy(distrusted_sources=["", "  "])
    assert policy.distrusts("CLAUDE.md") is False
    assert policy.distrusts("anything at all") is False


def test_rollback_restores_previous_policy():
    store = PolicyStore(path=None)
    store.apply(OperationalPolicy(distrusted_sources=["satire-news.com"]), reason="fix")
    store.rollback(reason="undo")
    assert store.current.distrusted_sources == []
    assert store.version == 1
    assert store.history[-1]["event"] == "ROLLBACK"


def test_policy_persists_to_disk(tmp_path):
    path = tmp_path / "operational_policy.json"
    store = PolicyStore(path=path)
    store.apply(OperationalPolicy(distrusted_sources=["x.com"]), reason="r")
    assert path.exists()
    reloaded = PolicyStore(path=path)
    assert reloaded.current.distrusted_sources == ["x.com"]
    assert reloaded.version == 2


# --------------------------------------------------------------------------- #
# Performance analytics: indices, dissonance, root cause
# --------------------------------------------------------------------------- #
def _context_with_fact(source: str, turn_id: str = "T1") -> RetrievedContextAsset:
    meta = SdrMetadataBlock(source_uid=ARCHIVIST_UID, owning_model_uid=ARCHIVIST_UID)
    fact = SdrFactAssertion(
        subject="Moon", predicate="make of", object="cheese",
        data_source=source, evidence="The Moon is made of cheese.",
        confidence=SdrConfidenceScore(score=1.0), metadata=meta,
    )
    return RetrievedContextAsset(turn_id=turn_id, question="q", facts=[fact], metadata=meta)


def test_negative_feedback_collapses_fidelity_and_triggers_dissonance():
    analyzer = PerformanceAnalyzer()
    indices = analyzer.compute_indices(feedback=Feedback("T1", "INCORRECT"))
    assert indices.fidelity == 0.0
    event = analyzer.detect_dissonance(indices, turn_id="T1")
    assert event is not None and "fidelity" in event.summary


def test_positive_feedback_is_harmonious():
    analyzer = PerformanceAnalyzer()
    indices = analyzer.compute_indices(feedback=Feedback("T1", "CORRECT"))
    assert analyzer.detect_dissonance(indices, turn_id="T1") is None


def test_root_cause_attributes_the_offending_source():
    analyzer = PerformanceAnalyzer()
    ctx = _context_with_fact("satire-news.com")
    rca = analyzer.root_cause(turn_id="T1", answer=None, context=ctx, feedback=Feedback("T1", "INCORRECT"))
    assert "satire-news.com" in rca.recommended_action
    assert rca.root_causes[0].locus == "Archivist source validation"


# --------------------------------------------------------------------------- #
# The isolated Resonance Sandbox
# --------------------------------------------------------------------------- #
def _probe(mapping: dict[str, list[str]]):
    """A read-only retrieval probe: question → sources, filtered by the policy."""
    def retrieve(policy: OperationalPolicy, question: str) -> list[str]:
        return [s for s in mapping.get(question, []) if not policy.distrusts(s)]
    return retrieve


def test_sandbox_confirms_an_effective_clean_fix():
    sandbox = ResonanceSandbox(_probe({"moon?": ["satire-news.com", "VISION.md"], "good?": ["VISION.md"]}))
    result = sandbox.simulate(
        current_policy=OperationalPolicy(),
        candidate_policy=OperationalPolicy(distrusted_sources=["satire-news.com"]),
        failing_question="moon?", offending_source="satire-news.com",
        control_questions=["good?"],
    )
    assert result.fix_effective is True
    assert result.collateral_damage is False


def test_sandbox_flags_collateral_damage_of_an_over_broad_fix():
    sandbox = ResonanceSandbox(_probe({"moon?": ["VISION.md"], "good?": ["VISION.md"]}))
    result = sandbox.simulate(
        current_policy=OperationalPolicy(),
        candidate_policy=OperationalPolicy(distrusted_sources=["VISION.md"]),
        failing_question="moon?", offending_source="VISION.md",
        control_questions=["good?"],
    )
    assert result.fix_effective is True
    assert result.collateral_damage is True
    assert "VISION.md" in result.suppressed_sources


# --------------------------------------------------------------------------- #
# The Philosopher as Runtime Safety Kernel
# --------------------------------------------------------------------------- #
def _philosopher() -> Philosopher:
    return Philosopher(bus=InProcessBus(), asset_store=AssetStore())


def _proposal() -> SdrPolicyModificationProposal:
    return SdrPolicyModificationProposal(
        turn_id="T1", target="Archivist.distrusted_sources",
        change_summary="Distrust 'satire-news.com'.", rationale="r", impact_class="MEDIUM",
        metadata=SdrMetadataBlock(source_uid=NEXUS_MIND_UID, owning_model_uid=NEXUS_MIND_UID),
    )


def test_philosopher_verifies_a_clean_fix():
    from aletheia.resonance.sandbox import SandboxResult

    v = _philosopher().verify_policy_proposal(
        _proposal(), SandboxResult(fix_effective=True, collateral_damage=False, summary="clean")
    )
    assert v.status == "VERIFIED"


def test_philosopher_rejects_over_broad_fix_citing_sanctity():
    from aletheia.resonance.sandbox import SandboxResult

    v = _philosopher().verify_policy_proposal(
        _proposal(),
        SandboxResult(fix_effective=True, collateral_damage=True,
                      suppressed_sources=["VISION.md"], summary="over-broad"),
    )
    assert v.status == "REJECTED"
    assert v.cited_directive == "The Sanctity of Information Flow"


def test_philosopher_rejects_an_ineffective_fix():
    from aletheia.resonance.sandbox import SandboxResult

    v = _philosopher().verify_policy_proposal(
        _proposal(), SandboxResult(fix_effective=False, collateral_damage=False, summary="no-op")
    )
    assert v.status == "REJECTED"


# --------------------------------------------------------------------------- #
# Rate limiter
# --------------------------------------------------------------------------- #
def test_rate_limiter_blocks_after_the_budget_and_prunes_with_time():
    clock = {"t": 0.0}
    rl = RateLimiter(max_changes=2, per_seconds=100.0, now=lambda: clock["t"])
    assert rl.allow() and (rl.record() or True)
    assert rl.allow() and (rl.record() or True)
    assert rl.allow() is False  # budget exhausted
    clock["t"] = 200.0  # window elapsed
    assert rl.allow() is True


# --------------------------------------------------------------------------- #
# The engine: gavel, philosopher veto, rate limit, auto-rollback
# --------------------------------------------------------------------------- #
def _engine(*, gavel, rate_limiter=None, control=("good?",), probe_map=None) -> tuple[ResonanceEngine, PolicyStore]:
    store = PolicyStore(path=None)
    probe_map = probe_map or {"moon?": ["satire-news.com", "VISION.md"], "good?": ["VISION.md"]}
    sandbox = ResonanceSandbox(_probe(probe_map))
    engine = ResonanceEngine(
        policy_store=store, philosopher=_philosopher(), sandbox=sandbox, gavel=gavel,
        rate_limiter=rate_limiter, control_questions=list(control),
    )
    return engine, store


def _run_engine(engine, **kw):
    feedback = Feedback("T1", "INCORRECT")
    ctx = _context_with_fact("satire-news.com")
    return asyncio.run(engine.run_cycle(feedback=feedback, failing_question="moon?", context=ctx, **kw))


def test_engine_applies_change_when_gavel_approves():
    engine, store = _engine(gavel=CallbackGavel(lambda **_: True))
    outcome = _run_engine(engine)
    assert outcome.status == APPLIED
    assert outcome.changed_behaviour is True
    assert store.current.distrusts("satire-news.com")
    assert store.version == 2


def test_engine_stops_at_the_gavel_when_human_rejects():
    engine, store = _engine(gavel=CallbackGavel(lambda **_: GavelDecision(approved=False)))
    outcome = _run_engine(engine)
    assert outcome.status == GAVEL_REJECTED
    assert store.version == 1  # nothing applied
    assert store.current.distrusted_sources == []


def test_engine_rejects_over_broad_proposal_before_the_gavel():
    # The offending source is a legitimate one that control questions also use.
    engine, store = _engine(
        gavel=CallbackGavel(lambda **_: True),
        probe_map={"moon?": ["VISION.md"], "good?": ["VISION.md"]},
    )
    feedback = Feedback("T1", "INCORRECT")
    ctx = _context_with_fact("VISION.md")
    outcome = asyncio.run(engine.run_cycle(feedback=feedback, failing_question="moon?", context=ctx))
    assert outcome.status == REJECTED_BY_PHILOSOPHER
    assert store.version == 1


def test_engine_no_dissonance_on_positive_feedback():
    engine, _ = _engine(gavel=CallbackGavel(lambda **_: True))
    outcome = asyncio.run(
        engine.run_cycle(feedback=Feedback("T1", "CORRECT"), failing_question="moon?",
                         context=_context_with_fact("satire-news.com"))
    )
    assert outcome.status == NO_DISSONANCE


def test_engine_rate_limits_to_prevent_over_optimization():
    rl = RateLimiter(max_changes=0, per_seconds=100.0)  # no budget at all
    engine, store = _engine(gavel=CallbackGavel(lambda **_: True), rate_limiter=rl)
    outcome = _run_engine(engine)
    assert outcome.status == RATE_LIMITED
    assert store.version == 1


def test_engine_auto_rolls_back_when_dissonance_worsens():
    engine, store = _engine(gavel=CallbackGavel(lambda **_: True))
    analyzer = PerformanceAnalyzer()
    # Post-deploy harmony is *worse* than the dissonant baseline → auto-rollback.
    worse = analyzer.compute_indices(feedback=Feedback("T1", "INCORRECT"))
    worse.harmony = 0.1
    outcome = _run_engine(engine, post_deploy_evaluator=lambda: worse)
    assert outcome.status == AUTO_ROLLED_BACK
    assert store.version == 1  # rolled back
    assert store.current.distrusted_sources == []


def test_engine_fails_safe_and_rolls_back_when_post_deploy_check_errors():
    # If we can't confirm the deploy is good, undo it rather than leave it.
    engine, store = _engine(gavel=CallbackGavel(lambda **_: True))

    def boom():
        raise RuntimeError("post-deploy probe blew up")

    outcome = _run_engine(engine, post_deploy_evaluator=boom)
    assert outcome.status == AUTO_ROLLED_BACK
    assert store.version == 1
    assert store.current.distrusted_sources == []


# --------------------------------------------------------------------------- #
# End to end via QASystem — the canonical RFC-001 scenario (the "Done when")
# --------------------------------------------------------------------------- #
def _qa(gavel) -> QASystem:
    system = QASystem(llm=OfflineProvider(), cascade_log=CascadeLog(path=None), gavel=gavel)
    system.ingest([
        Document(id="sat", text="The Moon is made of cheese.", metadata={"source": "satire-news.com"}),
        Document(id="v", text="Aletheia is a neuro-symbolic system.", metadata={"source": "VISION.md"}),
    ])
    return system


def test_full_resonance_scenario_heals_and_rolls_back():
    system = _qa(CallbackGavel(lambda **_: GavelDecision(approved=True, operator="owner")))
    q = "What is the Moon made of?"

    before = asyncio.run(system.ask(q))
    assert "satire-news.com" in before.sources  # the satirical fact is used

    outcome = asyncio.run(
        system.submit_feedback(turn_id=before.turn_id, question=q, rating="INCORRECT")
    )
    assert outcome.status == APPLIED
    assert system.policy.current.distrusts("satire-news.com")

    after = asyncio.run(system.ask(q))
    assert "satire-news.com" not in after.sources  # healed: the source is gone

    system.policy.rollback(reason="test")
    restored = asyncio.run(system.ask(q))
    assert "satire-news.com" in restored.sources  # rollback restored prior behaviour


def test_sandbox_probe_matches_live_retrieval():
    """The sandbox probe must ground on the same sources the live answer would —
    same cap, same filtering — or simulations would mislead the Philosopher."""
    system = _qa(CallbackGavel(lambda **_: True))
    if system.graph is None:
        return  # vector-only; nothing to compare
    q = "What is the Moon made of?"
    before = asyncio.run(system.ask(q))
    context = system._asset_for_turn(before.turn_id, RetrievedContextAsset)
    live_sources = {f.data_source for f in (context.facts if context else [])}
    probe_sources = set(system.archivist.retrieve_sources_under(system.policy.current, q))
    assert probe_sources == live_sources


def test_default_gavel_denies_so_nothing_self_modifies_without_a_yes():
    system = _qa(None)  # default gavel = deny
    q = "What is the Moon made of?"
    before = asyncio.run(system.ask(q))
    outcome = asyncio.run(
        system.submit_feedback(turn_id=before.turn_id, question=q, rating="INCORRECT")
    )
    assert outcome.status == GAVEL_REJECTED
    assert system.policy.version == 1  # untouched


def test_resonance_cycle_is_recorded_in_the_glass_box():
    system = _qa(CallbackGavel(lambda **_: True))
    q = "What is the Moon made of?"
    before = asyncio.run(system.ask(q))
    asyncio.run(system.submit_feedback(turn_id=before.turn_id, question=q, rating="INCORRECT"))
    statuses = [
        e["message"]["Body"].get("Status-Code")
        for e in system.cascade_log.entries
        if e["message"]["Header"]["Message-Type"] == "STATE_CHANGE"
    ]
    assert "DISSONANCE_DETECTED" in statuses
    assert "HUMAN_GAVEL_APPROVED" in statuses
    assert "POLICY_APPLIED" in statuses


# --------------------------------------------------------------------------- #
# SDR shapes
# --------------------------------------------------------------------------- #
def test_resonance_sdr_assets_serialize_to_canonical_names():
    meta = SdrMetadataBlock(source_uid=NEXUS_MIND_UID, owning_model_uid=NEXUS_MIND_UID)
    pmp = SdrPolicyModificationProposal(
        turn_id="T", target="Archivist", change_summary="c", rationale="r",
        impact_class="MEDIUM", metadata=meta,
    )
    wire = pmp.model_dump(by_alias=True)
    for key in ("Turn_ID", "Target", "Change_Summary", "Impact_Class"):
        assert key in wire
