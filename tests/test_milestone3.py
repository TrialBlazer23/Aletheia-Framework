"""Milestone 3: the Diagnostician, the circuit breaker, and self-healing.

We prove the immune system: it monitors the whole bus, correlates cascades,
detects a runaway loop and a hung agent, trips the circuit breaker, runs a
recovery cascade, and emits CHOREOGRAPHY_LOG / anomaly telemetry — all while the
rest of the system keeps working.
"""

import asyncio

from aletheia.agents.diagnostician import (
    ABORTED,
    COMPLETE,
    LOOPED,
    OPEN,
    Diagnostician,
)
from aletheia.agents.family import DIAGNOSTICIAN_UID, NEXUS_MIND_UID, PHILOSOPHER_UID
from aletheia.app.qa_system import QASystem
from aletheia.bus.in_process import InProcessBus
from aletheia.demo.diagnostician_demo import run_loop_scenario, run_stall_scenario
from aletheia.diagnostics.circuit_breaker import CircuitBreaker
from aletheia.llm.base import LLMProvider
from aletheia.log.cascade_log import CascadeLog
from aletheia.memory.corpus import Document
from aletheia.protocol.messages import make_event, make_state_change


# --------------------------------------------------------------------------- #
# The circuit breaker
# --------------------------------------------------------------------------- #
def test_breaker_is_healthy_by_default():
    breaker = CircuitBreaker()
    msg = make_event(source_uid="MODEL:X:0x1", event_name="E", data_asset_uid="ASSET:A:0x2")
    assert breaker.is_tripped is False
    assert breaker.blocks(msg) is False


def test_breaker_blocks_only_named_sources():
    breaker = CircuitBreaker()
    breaker.trip_sources(["MODEL:Ping:0x1"], reason="loop")
    blocked = make_event(source_uid="MODEL:Ping:0x1", event_name="E", data_asset_uid="A:B:0x1")
    other = make_event(source_uid="MODEL:Pong:0x2", event_name="E", data_asset_uid="A:B:0x2")
    assert breaker.is_tripped is True
    assert breaker.blocks(blocked) is True
    assert breaker.blocks(other) is False
    assert breaker.trips[0].sources == ("MODEL:Ping:0x1",)


def test_breaker_reset_restores_flow():
    breaker = CircuitBreaker()
    breaker.trip_sources(["MODEL:Ping:0x1"], reason="loop")
    breaker.reset_sources(["MODEL:Ping:0x1"])
    msg = make_event(source_uid="MODEL:Ping:0x1", event_name="E", data_asset_uid="A:B:0x1")
    assert breaker.blocks(msg) is False
    # The audit of interventions survives the reset.
    assert len(breaker.trips) == 1


def test_breaker_global_kill_switch_gates_everything():
    breaker = CircuitBreaker()
    breaker.trip_global(reason="emergency")
    msg = make_event(source_uid="MODEL:Anyone:0x9", event_name="E", data_asset_uid="A:B:0x1")
    assert breaker.blocks(msg) is True


def test_bus_gates_messages_when_breaker_trips():
    async def scenario():
        breaker = CircuitBreaker()
        bus = InProcessBus(circuit_breaker=breaker)
        received = []

        async def sub(msg):
            received.append(msg)

        bus.subscribe(sub)
        breaker.trip_sources(["MODEL:Loud:0x1"], reason="loop")
        await bus.publish(
            make_event(source_uid="MODEL:Loud:0x1", event_name="SPAM", data_asset_uid="A:B:0x1")
        )
        return bus, received

    bus, received = asyncio.run(scenario())
    assert received == []  # delivery was gated
    assert len(bus.gated) == 1
    # Still recorded in the Glass Box — the audit shows the attempt to speak.
    assert len(bus.cascade_log.entries) == 1


# --------------------------------------------------------------------------- #
# Loop detection + containment
# --------------------------------------------------------------------------- #
def test_diagnostician_detects_and_contains_an_infinite_loop():
    clock = {"t": 0.0}
    result = asyncio.run(run_loop_scenario(clock))
    diag = result["diagnostician"]
    breaker = result["breaker"]

    # A LOOP anomaly was raised and the breaker tripped.
    assert [a.anomaly_type for a in diag.anomalies] == ["LOOP"]
    assert diag.anomalies[0].severity == "CRITICAL"
    assert breaker.is_tripped is True
    # The looping agents are now blocked, so the bus gated their next messages —
    # the loop could not run away forever (the process didn't hang).
    assert {"MODEL:Ping:0x0F01", "MODEL:Pong:0x0F02"} <= breaker.blocked_sources
    assert len(result["bus"].gated) >= 1
    # The runaway cascade is marked LOOPED in the telemetry.
    assert any(c.status == LOOPED for c in diag.cascades.values())


def test_loop_anomaly_and_choreography_are_emitted_to_the_glass_box():
    clock = {"t": 0.0}
    result = asyncio.run(run_loop_scenario(clock))
    events = [
        (e["message"]["Header"]["Source-UID"], e["message"]["Body"].get("Event-Name"))
        for e in result["log"].entries
        if e["message"]["Header"]["Message-Type"] == "EVENT"
    ]
    assert (DIAGNOSTICIAN_UID, "ANOMALY_DETECTED") in events
    assert (DIAGNOSTICIAN_UID, "CHOREOGRAPHY_LOG") in events
    # And the containment is announced as a CASCADE_PAUSED state change.
    pauses = [
        e
        for e in result["log"].entries
        if e["message"]["Body"].get("Status-Code") == "CASCADE_PAUSED"
    ]
    assert pauses, "expected a CASCADE_PAUSED state change from the Diagnostician"


# --------------------------------------------------------------------------- #
# Stall / hung-agent detection + recovery
# --------------------------------------------------------------------------- #
def test_diagnostician_detects_a_stalled_cascade_and_recovers():
    clock = {"t": 0.0}
    result = asyncio.run(run_stall_scenario(clock))
    diag = result["diagnostician"]

    assert [a.anomaly_type for a in result["anomalies"]] == ["STALL"]
    assert result["anomalies"][0].severity == "HIGH"
    # The stalled cascade was aborted by the recovery cascade.
    assert any(c.status == ABORTED for c in diag.cascades.values())
    # Recovery released the breaker, so the system stays alive: a healthy worker
    # still completed its work after the stall.
    assert result["breaker"].is_tripped is False
    completed = any(
        hop.label == "WORK_COMPLETE"
        for c in diag.cascades.values()
        for hop in c.hops
    )
    assert completed


def test_stall_emits_recovery_action_to_the_glass_box():
    clock = {"t": 0.0}
    result = asyncio.run(run_stall_scenario(clock))
    statuses = [
        e["message"]["Body"].get("Status-Code")
        for e in result["log"].entries
        if e["message"]["Header"]["Message-Type"] == "STATE_CHANGE"
    ]
    assert "INITIATE_RECOVERY_ACTION" in statuses


def test_check_timeouts_is_quiet_before_the_timeout_elapses():
    clock = {"t": 0.0}
    breaker = CircuitBreaker()
    bus = InProcessBus(circuit_breaker=breaker)
    from aletheia.memory.asset_store import AssetStore

    diag = Diagnostician(
        bus=bus,
        asset_store=AssetStore(),
        circuit_breaker=breaker,
        stall_timeout=30.0,
        now=lambda: clock["t"],
    )
    diag.connect()

    async def scenario():
        await bus.publish(
            make_state_change(
                source_uid="MODEL:W:0x1",
                target_uid="MODEL:N:0x2",
                status_code="TASK_ACCEPTED",
            )
        )

    asyncio.run(scenario())
    clock["t"] = 10.0  # not yet past the 30s stall window
    assert diag.check_timeouts() == []
    clock["t"] = 40.0  # now past it
    assert len(diag.check_timeouts()) == 1


# --------------------------------------------------------------------------- #
# Correlation + telemetry over a real Q&A cascade
# --------------------------------------------------------------------------- #
class _FixedProvider(LLMProvider):
    name = "Fixed"
    is_live = True

    def __init__(self, reply: str):
        self._reply = reply

    def generate(self, *, system, user, max_tokens=2048):
        return self._reply


def _qa_system(reply: str) -> QASystem:
    system = QASystem(llm=_FixedProvider(reply), cascade_log=CascadeLog(path=None))
    system.ingest(
        [Document(id="d", text="Aletheia is a neuro-symbolic system.", metadata={"source": "VISION.md"})]
    )
    return system


def test_diagnostician_correlates_a_qa_turn_into_one_choreography():
    system = _qa_system("Aletheia is a neuro-symbolic, multi-agent system.")
    asyncio.run(system.ask("What is Aletheia?"))
    diag = system.diagnostician

    # The whole Nexus → Archivist → Narrator → Philosopher → Nexus turn is tracked
    # as a single cascade keyed by its turn_id.
    assert len(diag.cascades) == 1
    cascade = next(iter(diag.cascades.values()))
    assert cascade.correlation_id.startswith("TURN:QA:")
    # Every Family member that spoke is recorded as a participant.
    participants = set(cascade.participants)
    assert {NEXUS_MIND_UID, PHILOSOPHER_UID} <= participants
    # A healthy turn is NOT classified as a loop or stall.
    assert cascade.status in (OPEN, COMPLETE)
    assert diag.anomalies == []


def test_diagnostician_is_passive_and_does_not_perturb_a_healthy_cascade():
    """A healthy turn must produce no Diagnostician bus traffic (no extra hops)."""
    system = _qa_system("Aletheia is a neuro-symbolic system.")
    asyncio.run(system.ask("What is Aletheia?"))
    sources = [e["message"]["Header"]["Source-UID"] for e in system.cascade_log.entries]
    assert DIAGNOSTICIAN_UID not in sources  # silent observer when all is well
    # The breaker never tripped on a normal turn.
    assert system.circuit_breaker.is_tripped is False


def test_choreography_log_asset_has_the_expected_shape():
    system = _qa_system("Aletheia is a neuro-symbolic system.")
    asyncio.run(system.ask("What is Aletheia?"))
    diag = system.diagnostician
    cascade = next(iter(diag.cascades.values()))
    log = diag.build_choreography(cascade)

    assert log.correlation_id == cascade.correlation_id
    assert log.hop_count == len(log.hops) == cascade.hop_count
    assert log.hops[0].sequence == 1
    # Serializes to the canonical SDR field names.
    wire = log.model_dump(by_alias=True)
    assert "Correlation_ID" in wire and "Hops" in wire and "SDR_Metadata_Block" in wire


def test_health_report_summarizes_diagnostician_state():
    system = _qa_system("Aletheia is a neuro-symbolic system.")
    asyncio.run(system.ask("What is Aletheia?"))
    health = system.diagnostician.health_report()
    assert health["cascades_tracked"] == 1
    assert health["anomalies"] == 0
    assert health["breaker_tripped"] is False
