"""The Diagnostician (0x00E5) — self-healing / observability (Milestone 3).

The immune system of the Family. Where every other agent *filters* the bus down
to the few messages it cares about, the Diagnostician is the one member whose
job (CLAUDE.md §2) is to watch **all** of it: it taps the raw broadcast stream,
reconstructs every in-flight cascade by a correlation/choreography id, and keeps
a timed CHOREOGRAPHY_LOG of each one.

From that vantage point it does three things:

1. **Detect** loops (a cascade that won't stop) and stalls (a cascade that
   stops making progress — the hung-agent case Milestone 2 surfaced).
2. **Contain** a runaway by tripping the :class:`CircuitBreaker`, which the bus
   consults so the looping agents can no longer propagate — the system stays
   alive while the fault is isolated.
3. **Heal & report** — run a recovery cascade (abort the stuck flow cleanly,
   release the breaker where safe) and emit an ``SDR_Anomaly_Report`` plus the
   finalized CHOREOGRAPHY_LOG so the Resonance Cycle can later learn from it.

Correlation without changing the wire envelope
----------------------------------------------
The choreography id is the cascade's ``turn_id`` when one exists (it already
threads through the SDR asset chain), recovered as follows for a pure bus
observer:

* a **TRIGGER** carries ``turn_id`` in its parameters (and its target will act
  in the same cascade, so we tag the target too);
* an **EVENT** points at an asset whose ``turn_id`` we resolve via the
  AssetStore, falling back to the source agent's current cascade;
* a **STATE_CHANGE** (an ACK / status) is attributed to the cascade of the agent
  it concerns.

Cascades with no ``turn_id`` (e.g. the Milestone 0 handshake) are still tracked,
keyed by the id of the TRIGGER that began them. Healthy cascades produce no bus
traffic from the Diagnostician — observation is passive and never perturbs the
flow it measures; the Diagnostician only speaks when something is wrong.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from aletheia.agents.family import DIAGNOSTICIAN_UID
from aletheia.agents.family_member import FamilyMember
from aletheia.bus.base import MessageBus, Subscription
from aletheia.diagnostics.circuit_breaker import CircuitBreaker
from aletheia.memory.asset_store import AssetStore
from aletheia.protocol.messages import MessageType, SynapseMessage
from aletheia.sdr.primitives import (
    SdrAnomalyReport,
    SdrChoreographyHop,
    SdrChoreographyLog,
    SdrMetadataBlock,
    SdrTextBlock,
)
from aletheia.sil.interest_profile import InterestProfile

# Cascade health states (also the CHOREOGRAPHY_LOG status vocabulary).
OPEN = "OPEN"
COMPLETE = "COMPLETE"
LOOPED = "LOOPED"
STALLED = "STALLED"
ABORTED = "ABORTED"

# A cascade is "done" (no longer at risk of stalling) once we see one of these.
_TERMINAL_EVENTS = {"APPROVED", "REJECTED"}
_TERMINAL_STATUS = {"TASK_COMPLETE"}

# Status codes the Diagnostician emits (CLAUDE.md §3 vocabulary + SCC verbs §5).
STATUS_CASCADE_PAUSED = "CASCADE_PAUSED"  # the circuit breaker tripped
STATUS_RECOVERY = "INITIATE_RECOVERY_ACTION"  # the recovery cascade
STATUS_ALERT = "ISSUE_ALERT"  # a non-blocking anomaly alert


@dataclass
class CascadeState:
    """The Diagnostician's live model of one in-flight cascade."""

    correlation_id: str
    started_at: float
    last_activity: float
    status: str = OPEN
    hops: list[SdrChoreographyHop] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    # signature -> count, for loop detection (same agent re-emitting the same thing)
    signatures: dict[tuple[str, str], int] = field(default_factory=dict)

    @property
    def hop_count(self) -> int:
        return len(self.hops)

    @property
    def is_open(self) -> bool:
        return self.status == OPEN

    def add_participant(self, uid: str) -> None:
        if uid not in self.participants:
            self.participants.append(uid)


class Diagnostician(FamilyMember):
    """The bus-monitoring, self-healing Family member."""

    def __init__(
        self,
        *,
        bus: MessageBus,
        asset_store: AssetStore,
        circuit_breaker: CircuitBreaker | None = None,
        max_hops: int = 40,
        loop_signature_repeat: int = 6,
        stall_timeout: float = 30.0,
        now: Callable[[], float] | None = None,
    ) -> None:
        # The Diagnostician taps the *whole* bus, so its InterestProfile is empty;
        # it overrides connect() to observe the raw stream rather than filter it.
        super().__init__(
            name="Diagnostician",
            uid=DIAGNOSTICIAN_UID,
            bus=bus,
            interest_profile=InterestProfile(),
        )
        self._assets = asset_store
        self._bus = bus
        self.breaker = circuit_breaker
        self._max_hops = max_hops
        self._loop_repeat = loop_signature_repeat
        self._stall_timeout = stall_timeout
        self._now = now or time.monotonic

        self.cascades: dict[str, CascadeState] = {}
        self._agent_cascade: dict[str, str] = {}  # agent UID -> its current cascade
        self.anomalies: list[SdrAnomalyReport] = []
        self._observer: Subscription | None = None

    # --- lifecycle: tap the raw stream instead of the filtered listener ----- #
    def connect(self) -> None:
        if self._observer is None:
            self._observer = self._bus.subscribe(self._observe)

    def disconnect(self) -> None:
        if self._observer is not None:
            self._observer.unsubscribe()
            self._observer = None

    # --- observation -------------------------------------------------------- #
    async def _observe(self, message: SynapseMessage) -> None:
        # Never monitor our own telemetry/alerts — that would be a feedback loop.
        if message.source == self.uid:
            return

        corr = self._correlate(message)
        cascade = self.cascades.get(corr)
        if cascade is None:
            now = self._now()
            cascade = CascadeState(correlation_id=corr, started_at=now, last_activity=now)
            self.cascades[corr] = cascade

        self._record_hop(cascade, message)
        self._agent_cascade[message.source] = corr

        # A TRIGGER hands work to its target; that target will act in this same
        # cascade, so tag it now (its later ACK carries no turn_id of its own).
        if message.type == MessageType.TRIGGER:
            target = message.body.target_uid  # type: ignore[union-attr]
            self._agent_cascade[target] = corr
            cascade.add_participant(target)

        if self._reached_terminal(message):
            if cascade.is_open:
                cascade.status = COMPLETE
            return

        # Loop / runaway detection on every live hop.
        if cascade.is_open and self._looks_like_loop(cascade):
            await self._handle_loop(cascade)

    def _correlate(self, message: SynapseMessage) -> str:
        """Recover the cascade's choreography id for a pure bus observer."""
        body = message.body
        if message.type == MessageType.TRIGGER:
            turn_id = body.parameters.get("turn_id")  # type: ignore[union-attr]
            if turn_id:
                return str(turn_id)
            # A trigger with no turn_id starts its own cascade (keyed by its id).
            return message.header.message_id
        if message.type == MessageType.EVENT:
            asset_uid = body.payload.data_asset_uid  # type: ignore[union-attr]
            turn_id = self._asset_turn_id(asset_uid)
            if turn_id:
                return turn_id
            # Fall back to the cascade the emitting agent is already part of.
            return self._agent_cascade.get(message.source, message.header.message_id)
        # STATE_CHANGE: attribute it to the cascade of the agent it concerns
        # (an ACK targets the originator whose message provoked it), then the
        # emitting agent's own cascade, then a fresh id.
        target = body.target_uid  # type: ignore[union-attr]
        return (
            self._agent_cascade.get(target)
            or self._agent_cascade.get(message.source)
            or message.header.message_id
        )

    def _asset_turn_id(self, asset_uid: str) -> str | None:
        """Resolve an asset's ``turn_id`` if it's in the store and has one."""
        try:
            asset = self._assets.get(asset_uid)
        except KeyError:
            return None
        turn_id = getattr(asset, "turn_id", None)
        return str(turn_id) if turn_id else None

    def _record_hop(self, cascade: CascadeState, message: SynapseMessage) -> None:
        label = self._label(message)
        cascade.hops.append(
            SdrChoreographyHop(
                sequence=cascade.hop_count + 1,
                source_uid=message.source,
                message_type=message.type.value,
                label=label,
                elapsed_seconds=round(self._now() - cascade.started_at, 6),
            )
        )
        cascade.last_activity = self._now()
        cascade.add_participant(message.source)
        sig = (message.source, label)
        cascade.signatures[sig] = cascade.signatures.get(sig, 0) + 1

    @staticmethod
    def _label(message: SynapseMessage) -> str:
        body = message.body
        if message.type == MessageType.EVENT:
            return body.event_name  # type: ignore[union-attr]
        if message.type == MessageType.TRIGGER:
            return body.action_to_trigger  # type: ignore[union-attr]
        return body.status_code  # type: ignore[union-attr]

    @staticmethod
    def _reached_terminal(message: SynapseMessage) -> bool:
        body = message.body
        if message.type == MessageType.EVENT:
            return body.event_name in _TERMINAL_EVENTS  # type: ignore[union-attr]
        if message.type == MessageType.STATE_CHANGE:
            return body.status_code in _TERMINAL_STATUS  # type: ignore[union-attr]
        return False

    def _looks_like_loop(self, cascade: CascadeState) -> bool:
        if cascade.hop_count > self._max_hops:
            return True
        return any(count > self._loop_repeat for count in cascade.signatures.values())

    # --- self-healing: loops ------------------------------------------------ #
    async def _handle_loop(self, cascade: CascadeState) -> None:
        cascade.status = LOOPED
        worst = max(cascade.signatures.items(), key=lambda kv: kv[1])
        evidence = (
            f"{cascade.hop_count} hops; '{worst[0][1]}' from {worst[0][0]} "
            f"repeated {worst[1]}x (max_hops={self._max_hops}, "
            f"repeat_limit={self._loop_repeat})."
        )
        action = "alert-only (no circuit breaker attached)"

        # Contain it: stop the looping participants from propagating further.
        if self.breaker is not None:
            self.breaker.trip_sources(
                cascade.participants,
                reason=f"Loop in cascade {cascade.correlation_id}: {evidence}",
                correlation_id=cascade.correlation_id,
            )
            action = f"CIRCUIT_BREAKER_TRIPPED on {', '.join(cascade.participants)}"
            await self.broadcaster.report_state(
                target_uid=cascade.correlation_id,
                status_code=STATUS_CASCADE_PAUSED,
                reason=f"Runaway cascade contained. {evidence}",
            )

        await self._emit_anomaly(
            cascade,
            anomaly_type="LOOP",
            severity="CRITICAL",
            description="Infinite/runaway cascade detected and contained.",
            evidence=evidence,
            action_taken=action,
        )
        await self._emit_choreography(cascade)

    # --- self-healing: stalls / hung agents --------------------------------- #
    def check_timeouts(self, now: float | None = None) -> list[CascadeState]:
        """Find cascades that have gone quiet without finishing (the hung case).

        Deterministic on purpose: pass ``now`` (or inject a clock) so a stall can
        be exercised in tests/demos without real waiting. Returns the cascades
        newly flagged as stalled.
        """
        moment = now if now is not None else self._now()
        return [
            cascade
            for cascade in list(self.cascades.values())
            if cascade.is_open and (moment - cascade.last_activity) > self._stall_timeout
        ]

    async def sweep_timeouts(self, now: float | None = None) -> list[SdrAnomalyReport]:
        """Detect stalled cascades and run the recovery cascade on each."""
        reports: list[SdrAnomalyReport] = []
        moment = now if now is not None else self._now()
        for cascade in self.check_timeouts(moment):
            reports.append(await self._handle_stall(cascade, moment))
        return reports

    async def _handle_stall(self, cascade: CascadeState, moment: float) -> SdrAnomalyReport:
        idle = round(moment - cascade.last_activity, 3)
        last = cascade.hops[-1].label if cascade.hops else "—"
        evidence = (
            f"No progress for {idle}s after '{last}' "
            f"(stall_timeout={self._stall_timeout}s); "
            f"participants: {', '.join(cascade.participants) or 'unknown'}."
        )
        cascade.status = STALLED
        report = await self._emit_anomaly(
            cascade,
            anomaly_type="STALL",
            severity="HIGH",
            description="Cascade stalled — an agent accepted work but never completed it.",
            evidence=evidence,
            action_taken="RECOVERY_INITIATED",
        )
        await self._recover(cascade, reason=f"Aborting stalled cascade. {evidence}")
        await self._emit_choreography(cascade)
        return report

    async def _recover(self, cascade: CascadeState, *, reason: str) -> None:
        """Abort a stuck cascade cleanly and release any targeted breaker hold."""
        cascade.status = ABORTED
        await self.broadcaster.report_state(
            target_uid=cascade.correlation_id,
            status_code=STATUS_RECOVERY,
            reason=reason,
        )
        # A stall is not the agents' fault the way a loop is — let them serve new
        # work once the stuck cascade is abandoned.
        if self.breaker is not None and cascade.participants:
            self.breaker.reset_sources(cascade.participants)

    # --- telemetry emission ------------------------------------------------- #
    async def _emit_anomaly(
        self,
        cascade: CascadeState,
        *,
        anomaly_type: str,
        severity: str,
        description: str,
        evidence: str,
        action_taken: str,
    ) -> SdrAnomalyReport:
        report = SdrAnomalyReport(
            correlation_id=cascade.correlation_id,
            anomaly_type=anomaly_type,
            severity=severity,
            description=SdrTextBlock(text=description),
            evidence=evidence,
            participants=list(cascade.participants),
            action_taken=action_taken,
            metadata=SdrMetadataBlock(source_uid=self.uid, owning_model_uid=self.uid),
        )
        self.anomalies.append(report)
        self._assets.put(report.synapse_uid, report)
        await self.broadcaster.broadcast_event(
            event_name="ANOMALY_DETECTED",
            data_asset_uid=report.synapse_uid,
            description=f"{anomaly_type} ({severity}) in cascade {cascade.correlation_id}.",
            confidence_score=1.0,  # deterministic detection
        )
        return report

    async def _emit_choreography(self, cascade: CascadeState) -> SdrChoreographyLog:
        log = self.build_choreography(cascade)
        self._assets.put(log.synapse_uid, log)
        await self.broadcaster.broadcast_event(
            event_name="CHOREOGRAPHY_LOG",
            data_asset_uid=log.synapse_uid,
            description=(
                f"Cascade {cascade.correlation_id}: {cascade.status}, "
                f"{cascade.hop_count} hops."
            ),
            confidence_score=1.0,
        )
        return log

    def build_choreography(self, cascade: CascadeState) -> SdrChoreographyLog:
        """Snapshot a cascade as a CHOREOGRAPHY_LOG asset (no bus traffic)."""
        return SdrChoreographyLog(
            correlation_id=cascade.correlation_id,
            status=cascade.status,
            hop_count=cascade.hop_count,
            duration_seconds=round(cascade.last_activity - cascade.started_at, 6),
            participants=list(cascade.participants),
            hops=list(cascade.hops),
            metadata=SdrMetadataBlock(source_uid=self.uid, owning_model_uid=self.uid),
        )

    # --- live status (the /health view) ------------------------------------ #
    def health_report(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        for cascade in self.cascades.values():
            by_status[cascade.status] = by_status.get(cascade.status, 0) + 1
        gated = len(getattr(self._bus, "gated", []))
        delivery_errors = len(getattr(self._bus, "delivery_errors", []))
        return {
            "cascades_tracked": len(self.cascades),
            "by_status": by_status,
            "anomalies": len(self.anomalies),
            "breaker_tripped": bool(self.breaker and self.breaker.is_tripped),
            "gated_messages": gated,
            "delivery_errors": delivery_errors,
        }

    def pretty_health(self) -> str:
        h = self.health_report()
        status = ", ".join(f"{k}:{v}" for k, v in sorted(h["by_status"].items())) or "none"
        lines = [
            f"  cascades tracked : {h['cascades_tracked']}  ({status})",
            f"  anomalies        : {h['anomalies']}",
            f"  circuit breaker  : {'TRIPPED' if h['breaker_tripped'] else 'closed (healthy)'}",
            f"  gated messages   : {h['gated_messages']}",
            f"  delivery errors  : {h['delivery_errors']}",
        ]
        for report in self.anomalies[-5:]:
            lines.append(
                f"    ⚠ {report.anomaly_type} ({report.severity}) "
                f"in {report.correlation_id}: {report.evidence}"
            )
        return "\n".join(lines)
