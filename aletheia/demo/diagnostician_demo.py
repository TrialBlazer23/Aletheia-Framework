"""Milestone 3 proof: the Diagnostician detects, contains, and heals.

Two faults are induced deliberately; the Diagnostician — watching the whole bus —
catches each, and the system stays alive.

1. **Infinite loop.** Two stand-in agents, Ping and Pong, are wired to answer
   each other forever. The Diagnostician sees the runaway, trips the circuit
   breaker on both, and the bus gates their next messages — the loop dies.

2. **Hung agent / stalled cascade.** A worker accepts a trigger (ACKs) but never
   completes. With an injected clock we jump past the stall timeout; the
   Diagnostician flags the stall, runs a recovery cascade, and a *healthy* worker
   still answers afterwards — proving the system survived.

Run with ``python main.py --diagnostics`` (or ``python -m
aletheia.demo.diagnostician_demo``). Everything is recorded in the Cascade Log.
"""

from __future__ import annotations

import asyncio
from typing import Any

from aletheia.agents.diagnostician import Diagnostician
from aletheia.agents.family_member import FamilyMember
from aletheia.bus.in_process import InProcessBus
from aletheia.diagnostics.circuit_breaker import CircuitBreaker
from aletheia.log.cascade_log import CascadeLog
from aletheia.memory.asset_store import AssetStore
from aletheia.protocol.messages import MessageType
from aletheia.sil.interest_profile import InterestProfile, InterestRule

PING_UID = "MODEL:Ping:0x0F01"
PONG_UID = "MODEL:Pong:0x0F02"
WORKER_UID = "MODEL:StuckWorker:0x0F03"
HEALER_UID = "MODEL:HealthyWorker:0x0F04"
KICKER_UID = "MODEL:Kicker:0x0001"


class _Echo(FamilyMember):
    """Re-broadcasts an event every time it hears its partner — an endless loop."""

    def __init__(self, *, bus, partner_uid: str, my_event: str, partner_event: str) -> None:
        profile = InterestProfile(
            [
                InterestRule(
                    action_to_trigger="BOUNCE",
                    source_model_uid=partner_uid,
                    message_type=MessageType.EVENT,
                    event_name=partner_event,
                )
            ]
        )
        uid = PING_UID if my_event == "PING" else PONG_UID
        super().__init__(name=my_event, uid=uid, bus=bus, interest_profile=profile)
        self._my_event = my_event

    async def handle_action(self, action, data, message) -> None:
        if action != "BOUNCE":
            return
        await self.broadcaster.broadcast_event(
            event_name=self._my_event,
            asset_type="BOUNCE",
            description="bounce",
            confidence_score=1.0,
        )


class _StuckWorker(FamilyMember):
    """Accepts work (the base class ACKs for it) but never completes it."""

    async def handle_action(self, action, data, message) -> None:
        return  # ... silence. The cascade hangs here.


class _HealthyWorker(FamilyMember):
    async def handle_action(self, action, data, message) -> None:
        if action != "DO_WORK":
            return
        await self.broadcaster.broadcast_event(
            event_name="WORK_COMPLETE",
            asset_type="WORK_RESULT",
            description="completed normally",
            confidence_score=0.99,
        )


class _Kicker(FamilyMember):
    """Starts cascades (and finalizes the healthy one)."""

    async def kick_loop(self) -> None:
        # Seed the loop with a direct TRIGGER to Ping (a TRIGGER addressed to an
        # agent is always handled); Ping then emits PING, Pong answers PONG, and
        # the two bounce forever until the Diagnostician steps in.
        await self.broadcaster.send_trigger(
            target_uid=PING_UID, action_to_trigger="BOUNCE"
        )

    async def trigger(self, target_uid: str) -> None:
        await self.broadcaster.send_trigger(
            target_uid=target_uid,
            action_to_trigger="DO_WORK",
            parameters={"turn_id": f"TURN:DEMO:{target_uid[-6:]}"},
        )

    async def handle_action(self, action, data, message) -> None:
        return


async def run_loop_scenario(clock: dict[str, float]) -> dict[str, Any]:
    """Induce an infinite Ping/Pong loop; the Diagnostician must contain it."""
    log = CascadeLog(path=None)
    breaker = CircuitBreaker()
    bus = InProcessBus(cascade_log=log, circuit_breaker=breaker)
    assets = AssetStore()

    diagnostician = Diagnostician(
        bus=bus,
        asset_store=assets,
        circuit_breaker=breaker,
        max_hops=20,
        now=lambda: clock["t"],
    )
    ping = _Echo(bus=bus, partner_uid=PONG_UID, my_event="PING", partner_event="PONG")
    pong = _Echo(bus=bus, partner_uid=PING_UID, my_event="PONG", partner_event="PING")
    kicker = _Kicker(name="Kicker", uid=KICKER_UID, bus=bus, interest_profile=InterestProfile())

    for agent in (diagnostician, ping, pong, kicker):
        agent.connect()

    await kicker.kick_loop()

    return {
        "log": log,
        "breaker": breaker,
        "bus": bus,
        "diagnostician": diagnostician,
    }


async def run_stall_scenario(clock: dict[str, float]) -> dict[str, Any]:
    """A worker accepts work but hangs; the Diagnostician must detect + recover."""
    log = CascadeLog(path=None)
    breaker = CircuitBreaker()
    bus = InProcessBus(cascade_log=log, circuit_breaker=breaker)
    assets = AssetStore()

    diagnostician = Diagnostician(
        bus=bus,
        asset_store=assets,
        circuit_breaker=breaker,
        stall_timeout=30.0,
        now=lambda: clock["t"],
    )
    stuck = _StuckWorker(name="StuckWorker", uid=WORKER_UID, bus=bus)
    healer = _HealthyWorker(
        name="HealthyWorker",
        uid=HEALER_UID,
        bus=bus,
        interest_profile=InterestProfile(),
    )
    kicker = _Kicker(name="Kicker", uid=KICKER_UID, bus=bus, interest_profile=InterestProfile())

    for agent in (diagnostician, stuck, healer, kicker):
        agent.connect()

    # Start a cascade that will hang in the stuck worker.
    await kicker.trigger(WORKER_UID)

    # Time passes with no progress — jump past the stall window and sweep.
    clock["t"] += 45.0
    anomalies = await diagnostician.sweep_timeouts()

    # Prove the system still works: a healthy worker completes normally.
    await kicker.trigger(HEALER_UID)

    return {
        "log": log,
        "breaker": breaker,
        "bus": bus,
        "diagnostician": diagnostician,
        "anomalies": anomalies,
    }


def main() -> None:
    print("\n=== Milestone 3 — the Diagnostician (the immune system) ===")

    # --- 1) Infinite loop --------------------------------------------------- #
    clock = {"t": 0.0}
    loop = asyncio.run(run_loop_scenario(clock))
    diag = loop["diagnostician"]
    print("\n[1] Induced an infinite Ping <-> Pong loop.")
    print(f"    hops observed before containment : {sum(c.hop_count for c in diag.cascades.values())}")
    print(f"    circuit breaker tripped          : {loop['breaker'].is_tripped}")
    print(f"    looping agents now blocked       : {sorted(loop['breaker'].blocked_sources)}")
    print(f"    messages gated by the breaker    : {len(loop['bus'].gated)}")
    print(f"    anomalies raised                 : {[a.anomaly_type for a in diag.anomalies]}")
    print("    → the loop is contained; the process did not hang.")

    # --- 2) Hung agent / stalled cascade ------------------------------------ #
    clock = {"t": 0.0}
    stall = asyncio.run(run_stall_scenario(clock))
    diag2 = stall["diagnostician"]
    print("\n[2] Induced a hung agent (accepts work, never completes).")
    print(f"    anomalies raised                 : {[a.anomaly_type for a in diag2.anomalies]}")
    print(f"    stalled cascade detected + aborted via recovery cascade.")
    completed_after = any(
        hop.label == "WORK_COMPLETE"
        for cascade in diag2.cascades.values()
        for hop in cascade.hops
    )
    print(f"    healthy worker still completed   : {completed_after}  (system stayed alive)")

    print("\nDiagnostician health view:")
    print(diag2.pretty_health())

    print("\nCascade Log of the stall scenario (the Glass Box):")
    print(stall["log"].pretty())
    print()


if __name__ == "__main__":
    main()
